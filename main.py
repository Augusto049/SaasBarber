import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Appointment
from app.security import limiter
from app.services.email_service import EmailService
from app.routes import (
    auth, dashboard, services, barbers, products, appointments,
    subscriptions, finances, settings as settings_routes, public, webhooks
)

logger = logging.getLogger("uvicorn.error")
BUSINESS_TIMEZONE = ZoneInfo(settings.TIMEZONE)

# Criação das tabelas no banco de dados SQLite/Postgres
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="SaaS completo para barbearias: serviços, comissões, produtos, finanças, planos de assinatura e pagamentos com Mercado Pago",
    version="1.0.0"
)

# Configuração do Rate Limiter (Proteção de Borda contra Brute Force / DDoS)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Função do Scheduler para Lembretes por E-mail via Gmail (1 hora antes)
def check_and_send_email_reminders():
    db = SessionLocal()
    try:
        now = datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)
        start_window = now + timedelta(minutes=55)
        end_window = now + timedelta(minutes=65)

        upcoming_appointments = db.query(Appointment).filter(
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.reminder_sent.is_(False),
            Appointment.date_time >= start_window,
            Appointment.date_time <= end_window
        ).all()

        if upcoming_appointments:
            logger.info("Encontrados %s agendamento(s) para lembrete por e-mail.", len(upcoming_appointments))

        for apt in upcoming_appointments:
            if not apt.customer_email:
                logger.warning("Agendamento %s sem e-mail; lembrete não enviado.", apt.id)
                continue

            time_str = apt.date_time.strftime("%H:%M")
            service_name = apt.service.name if apt.service else "Atendimento"
            success = EmailService.send_booking_reminder(
                customer_name=apt.customer_name,
                to_email=apt.customer_email,
                service_name=service_name,
                time_str=time_str
            )

            if success:
                apt.reminder_sent = True
                db.commit()
                logger.info("Lembrete por e-mail enviado para o agendamento %s.", apt.id)
            else:
                logger.error("Falha ao enviar lembrete por e-mail do agendamento %s.", apt.id)

    except Exception as e:
        logger.exception("Erro no job de lembretes por e-mail: %s", e)
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()
    app.state.scheduler = scheduler
    scheduler.add_job(
        check_and_send_email_reminders,
        "interval",
        minutes=1,
        id="email_appointment_reminders",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info("Agendador de lembretes iniciado; fuso horário: %s.", settings.TIMEZONE)


@app.on_event("shutdown")
def stop_scheduler():
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


# Arquivos estáticos (Montado antes dos middlewares para carregamento instantâneo de CSS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Middleware para injeção de Headers HTTP Nacionais/Enterprise de Segurança (OWASP)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Previne injeção de scripts maliciosos cross-site (XSS)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Bloqueia exibição dentro de <iframe> não autorizados (Anti-Clickjacking)
    response.headers["X-Frame-Options"] = "DENY"
    
    # Impede alteração de tipo MIME exceto para arquivos estáticos válidos
    if not request.url.path.startswith("/static"):
        response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Força navegação estrita por HTTPS por 1 ano
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Controla o envio de informações de cabeçalho de referência
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response


# Inclusão dos roteadores
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(services.router)
app.include_router(barbers.router)
app.include_router(products.router)
app.include_router(appointments.router)
app.include_router(subscriptions.router)
app.include_router(finances.router)
app.include_router(settings_routes.router)
app.include_router(public.router)
app.include_router(webhooks.router)


@app.get("/")
async def root(request: Request):
    # Se já tiver cookie de sessão, vai pro dashboard, senão pro login
    if request.cookies.get("barber_session"):
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")