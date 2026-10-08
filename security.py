import hmac
import hashlib
import time
import re
import html
from typing import Dict, Tuple
from fastapi import Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

# Limitador de requisições baseado no IP do cliente (slowapi)
limiter = Limiter(key_func=get_remote_address)


class RateLimitStore:
    """
    Armazenamento em memória para controlar tentativas de login falhadas e bloqueios temporários.
    """
    def __init__(self):
        self.failed_attempts: Dict[str, list] = {}
        self.lockouts: Dict[str, float] = {}

    def is_locked(self, key: str) -> bool:
        if key in self.lockouts:
            if time.time() < self.lockouts[key]:
                return True
            else:
                del self.lockouts[key]
        return False

    def remaining_lockout(self, key: str) -> int:
        if key in self.lockouts:
            remaining = int(self.lockouts[key] - time.time())
            return max(0, remaining)
        return 0

    def record_login_attempt(self, key: str):
        now = time.time()
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []
        self.failed_attempts[key].append(now)

    def get_failed_attempts(self, key: str, window_seconds: int = 900) -> int:
        now = time.time()
        if key in self.failed_attempts:
            # Filtra apenas tentativas dentro da janela de tempo (padrão 15 min)
            self.failed_attempts[key] = [
                t for t in self.failed_attempts[key] if now - t < window_seconds
            ]
            return len(self.failed_attempts[key])
        return 0

    def lock_key(self, key: str, lockout_seconds: int = 900):
        self.lockouts[key] = time.time() + lockout_seconds

    def unlock_key(self, key: str):
        self.failed_attempts.pop(key, None)
        self.lockouts.pop(key, None)


# Instância global importada pelo auth.py
rate_limit_store = RateLimitStore()


class PasswordStrengthError(Exception):
    def __init__(self, message: str):
        self.message = message


def validate_password_strength(password: str):
    """
    Valida os critérios mínimos de segurança da palavra-passe.
    """
    if len(password) < 8:
        raise PasswordStrengthError("A palavra-passe deve ter pelo menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        raise PasswordStrengthError("A palavra-passe deve conter pelo menos uma letra maiúscula.")
    if not re.search(r"[a-z]", password):
        raise PasswordStrengthError("A palavra-passe deve conter pelo menos uma letra minúscula.")
    if not re.search(r"[0-9]", password):
        raise PasswordStrengthError("A palavra-passe deve conter pelo menos um número.")


def sanitize_input(text: str, max_length: int = 255) -> str:
    """
    Limpa e sanitiza entradas de texto para prevenir XSS e injeções.
    """
    if not text:
        return ""
    text = html.escape(text.strip())
    return text[:max_length]


def get_client_ip(request: Request) -> str:
    """
    Obtém o IP real do cliente mesmo atrás de proxies/Cloudflare.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def create_audit_log(db: Session, user_id: int, barbershop_id: int, action: str, details: str, ip_address: str):
    """
    Regista eventos na tabela de auditoria (LGPD / Segurança).
    """
    from app.models import AuditLog
    audit = AuditLog(
        user_id=user_id,
        barbershop_id=barbershop_id,
        action=action,
        details=details,
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()


async def verify_mercadopago_webhook(request: Request, x_signature: str, secret_token: str) -> bool:
    """
    Valida a assinatura x-signature do Mercado Pago.
    """
    if not x_signature or not secret_token:
        return False

    try:
        parts = {}
        for item in x_signature.split(','):
            if '=' in item:
                k, v = item.split('=', 1)
                parts[k.strip()] = v.strip()

        ts = parts.get('ts')
        v1 = parts.get('v1')

        if not ts or not v1:
            return False

        data_id = request.query_params.get("data.id") or request.query_params.get("id") or ""
        x_request_id = request.headers.get("x-request-id", "")
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        generated_signature = hmac.new(
            secret_token.encode('utf-8'),
            manifest.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(generated_signature, v1)
    except Exception:
        return False