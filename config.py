import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "BarberSaaS - Gestão Inteligente para Barbearias")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-before-deploy")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./barbershop.db")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")

    ENV: str = os.getenv("ENV", "development")
    MERCADO_PAGO_WEBHOOK_SECRET: str = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET", "")

    WHATSAPP_API_URL: str = os.getenv(
        "WHATSAPP_API_URL", "https://api.seuroteadorwpp.com/send-message"
    )
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")

    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_PASSWORD: str = os.getenv("GMAIL_PASSWORD", "")


settings = Settings()