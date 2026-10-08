# app/services/email_service.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """
        Envia um e-mail formatado em HTML utilizando o servidor SMTP do Gmail.
        """
        if not to_email or not settings.GMAIL_USER or not settings.GMAIL_PASSWORD:
            logger.warning("Configurações do Gmail SMTP não foram preenchidas no .env ou config.py")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.APP_NAME} <{settings.GMAIL_USER}>"
            msg["To"] = to_email

            msg.attach(MIMEText(html_content, "html"))

            # Ligação segura ao servidor do Gmail via TLS (Porta 587)
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.GMAIL_USER, settings.GMAIL_PASSWORD)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail via Gmail SMTP: {e}")
            return False

    @staticmethod
    def send_booking_confirmation(customer_name: str, to_email: str, service_name: str, barber_name: str, date_str: str, time_str: str):
        """Dispara e-mail de confirmação imediata no momento do agendamento."""
        subject = "💈 Agendamento Confirmado!"
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #eee; border-radius: 8px;">
            <h2 style="color: #2563eb; margin-bottom: 10px;">Agendamento Confirmado!</h2>
            <p>Olá, <strong>{customer_name}</strong>!</p>
            <p>O seu horário foi reservado com sucesso. Confira os detalhes do seu atendimento:</p>
            <ul style="background-color: #f8fafc; padding: 15px 25px; border-radius: 6px; list-style: none; line-height: 1.8;">
                <li><strong>✂️ Serviço:</strong> {service_name}</li>
                <li><strong>👤 Profissional:</strong> {barber_name}</li>
                <li><strong>📅 Data:</strong> {date_str}</li>
                <li><strong>⏰ Horário:</strong> {time_str}</li>
            </ul>
            <p style="margin-top: 15px;">Agradecemos a preferência! Te aguardamos na barbearia.</p>
        </div>
        """
        return EmailService.send_email(to_email, subject, html)

    @staticmethod
    def send_booking_reminder(customer_name: str, to_email: str, service_name: str, time_str: str):
        """Dispara e-mail de lembrete 1 hora antes do atendimento."""
        subject = "⏰ Lembrete de Agendamento!"
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: auto; border: 1px solid #eee; border-radius: 8px;">
            <h2 style="color: #d97706; margin-bottom: 10px;">Lembrete de Atendimento</h2>
            <p>Olá <strong>{customer_name}</strong>, falta 1 hora para o seu atendimento!</p>
            <p>Seu atendimento de <strong>{service_name}</strong> está marcado para hoje às <strong>{time_str}</strong>.</p>
            <p>Caso precise de algum ajuste ou remarcação, entre em contacto connosco o quanto antes.</p>
            <p style="margin-top: 15px;">Até breve!</p>
        </div>
        """
        return EmailService.send_email(to_email, subject, html)