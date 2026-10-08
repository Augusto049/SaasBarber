import re
from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Barbershop
from app.auth import (
    hash_password, verify_password, create_access_token, get_current_user_optional
)
from app.security import (
    rate_limit_store, validate_password_strength, PasswordStrengthError,
    create_audit_log, get_client_ip, sanitize_input, limiter
)
from app.config import settings

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

# Máximo de tentativas de login antes de bloquear
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutos

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="auth/login.html", context={"error": None})


@router.post("/login", response_class=HTMLResponse)
@router.post("/api/login", response_class=HTMLResponse)
@limiter.limit("5/minute")  # Proteção de borda do slowapi contra brute force
async def login(
    request: Request,
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    db: Session = Depends(get_db)
):
    is_json = request.headers.get("content-type", "").lower().startswith("application/json")

    if is_json:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        email = payload.get("email") or payload.get("username")
        password = payload.get("password") or payload.get("senha")

    ip = get_client_ip(request)
    email = (email or "").strip().lower()
    password = password or ""

    def login_response_error(message: str, status_code: int = status.HTTP_400_BAD_REQUEST, extra: dict | None = None):
        payload = {"success": False, "message": message}
        if extra:
            payload.update(extra)
        if is_json:
            return JSONResponse(status_code=status_code, content=payload)
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": message},
            status_code=status_code
        )

    # ── Verificar bloqueio por IP e email ──
    lock_key_email = f"login_fail_email:{email}"
    lock_key_ip = f"login_fail_ip:{ip}"

    if rate_limit_store.is_locked(lock_key_email):
        mins = rate_limit_store.remaining_lockout(lock_key_email) // 60
        message = f"Conta temporariamente bloqueada. Tente novamente em {mins} minutos."
        return login_response_error(message, status.HTTP_429_TOO_MANY_REQUESTS)

    if rate_limit_store.is_locked(lock_key_ip):
        mins = rate_limit_store.remaining_lockout(lock_key_ip) // 60
        message = f"Muitas tentativas deste dispositivo. Aguarde {mins} minutos."
        return login_response_error(message, status.HTTP_429_TOO_MANY_REQUESTS)

    # ── Verificar credenciais ──
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.hashed_password):
        # Registrar tentativa falha
        rate_limit_store.record_login_attempt(lock_key_email)
        rate_limit_store.record_login_attempt(lock_key_ip)

        attempts_email = rate_limit_store.get_failed_attempts(lock_key_email, LOCKOUT_SECONDS)
        if attempts_email >= MAX_LOGIN_ATTEMPTS:
            rate_limit_store.lock_key(lock_key_email, LOCKOUT_SECONDS)
            rate_limit_store.lock_key(lock_key_ip, LOCKOUT_SECONDS)
            create_audit_log(db, None, None, "login_blocked",
                             f"Conta bloqueada por excesso de tentativas: {email}", ip)
            message = "Conta bloqueada por excesso de tentativas. Tente em 15 minutos."
            return login_response_error(message, status.HTTP_429_TOO_MANY_REQUESTS)

        remaining = MAX_LOGIN_ATTEMPTS - attempts_email
        message = f"E-mail ou senha incorretos. {remaining} tentativa(s) restante(s)."
        return login_response_error(message, status.HTTP_400_BAD_REQUEST)

    if not user.is_active:
        message = "Esta conta está desativada. Entre em contato com o suporte."
        return login_response_error(message, status.HTTP_400_BAD_REQUEST)

    # ── Login bem-sucedido: limpa tentativas ──
    rate_limit_store.unlock_key(lock_key_email)
    rate_limit_store.unlock_key(lock_key_ip)

    # Audit log
    create_audit_log(db, user.id, user.barbershop_id, "login",
                     f"Login bem-sucedido: {email}", ip)

    # Define flag secure dinamicamente dependendo do ambiente
    is_production = getattr(settings, "ENV", "development") == "production"

    # Cria token e cookie seguro
    access_token = create_access_token(data={"sub": str(user.id)})

    if is_json:
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Login realizado com sucesso.", "redirect": "/dashboard"}
        )
    else:
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    response.set_cookie(
        key="barber_session",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="strict",
        secure=is_production
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user_optional(request, db)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="auth/register.html", context={"error": None})


@router.post("/register", response_class=HTMLResponse)
@router.post("/api/register", response_class=HTMLResponse)
@limiter.limit("3/hour")  # Limita criação excessiva de contas por hora por IP
async def register(
    request: Request,
    barbershop_name: str | None = Form(default=None),
    full_name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    phone: str | None = Form(default=""),
    db: Session = Depends(get_db)
):
    is_json = request.headers.get("content-type", "").lower().startswith("application/json")

    if is_json:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        barbershop_name = payload.get("barbershop_name") or payload.get("shop_name") or payload.get("nome_barbearia") or payload.get("barbearia")
        full_name = payload.get("full_name") or payload.get("nome") or payload.get("name")
        email = payload.get("email")
        password = payload.get("password") or payload.get("senha")
        phone = payload.get("phone") or payload.get("telefone") or ""

    ip = get_client_ip(request)
    email = (email or "").strip().lower()
    password = password or ""
    barbershop_name = barbershop_name or ""
    full_name = full_name or ""
    phone = phone or ""

    def register_response_error(message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        if is_json:
            return JSONResponse(status_code=status_code, content={"success": False, "message": message})
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": message},
            status_code=status_code
        )

    # ── Validar força da senha ──
    try:
        validate_password_strength(password)
    except PasswordStrengthError as e:
        return register_response_error(e.message, status.HTTP_400_BAD_REQUEST)

    # ── Sanitizar entradas ──
    barbershop_name = sanitize_input(barbershop_name, 100)
    full_name = sanitize_input(full_name, 100)
    phone = sanitize_input(phone, 20)

    if not barbershop_name or not full_name or not email or not password:
        return register_response_error("Preencha todos os campos obrigatórios.", status.HTTP_400_BAD_REQUEST)

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return register_response_error("Já existe uma conta com este e-mail.", status.HTTP_400_BAD_REQUEST)

    # Gerar slug único para a barbearia
    base_slug = slugify(barbershop_name)
    slug = base_slug
    counter = 1
    while db.query(Barbershop).filter(Barbershop.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    barbershop = Barbershop(
        name=barbershop_name.strip(),
        slug=slug,
        phone=phone.strip(),
        address="Definir endereço nas configurações"
    )
    db.add(barbershop)
    db.flush()

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role="admin",
        barbershop_id=barbershop.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    create_audit_log(db, user.id, barbershop.id, "register",
                     f"Nova barbearia registrada: {barbershop_name} ({email})", ip)

    is_production = getattr(settings, "ENV", "development") == "production"

    if is_json:
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Conta criada com sucesso.", "redirect": "/login"}
        )
    else:
        # Auto-login
        access_token = create_access_token(data={"sub": str(user.id)})
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="barber_session",
            value=access_token,
            httponly=True,
            max_age=60 * 60 * 24 * 7,
            samesite="strict",
            secure=is_production
        )
        return response

    return response


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        ip = get_client_ip(request)
        create_audit_log(db, user.id, user.barbershop_id, "logout",
                         f"Logout: {user.email}", ip)
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("barber_session")
    return response