import urllib.parse
import uuid
from typing import Optional, Dict, Any
from app.config import settings

class NotificationService:
    @staticmethod
    def clean_phone(phone: str) -> str:
        """Limpa o telefone deixando apenas dígitos com DDI 55."""
        digits = "".join(filter(str.isdigit, phone or ""))
        if not digits.startswith("55") and len(digits) in [10, 11]:
            digits = "55" + digits
        return digits

    @classmethod
    def get_whatsapp_url(cls, phone: str, message: str) -> str:
        """Gera URL direta para disparo via WhatsApp Web / App."""
        clean = cls.clean_phone(phone)
        encoded_text = urllib.parse.quote(message)
        return f"https://api.whatsapp.com/send?phone={clean}&text={encoded_text}"

    @classmethod
    def format_booking_confirmation(cls, appointment, barbershop) -> str:
        data_formatada = appointment.date_time.strftime('%d/%m/%Y')
        hora_formatada = appointment.date_time.strftime('%H:%M')
        
        pagamento_info = "Pago Antecipado (Mercado Pago)" if (appointment.is_paid_in_advance or appointment.payment_status == 'approved') else "Pagar no Local"

        msg = (
            f"💈 *CONFIRMAÇÃO DE AGENDAMENTO — {barbershop.name.upper()}*\n\n"
            f"Olá, *{appointment.customer_name}*! 👋\n"
            f"Seu horário foi agendado com sucesso!\n\n"
            f"📅 *Data:* {data_formatada}\n"
            f"⏰ *Horário:* {hora_formatada}\n"
            f"✂️ *Serviço:* {appointment.service.name}\n"
            f"💈 *Profissional:* {appointment.barber.name}\n"
            f"💵 *Valor:* R$ {appointment.total_price:.2f}".replace('.', ',') + f" ({pagamento_info})\n"
        )
        if barbershop.address:
            msg += f"📍 *Endereço:* {barbershop.address}\n"
            
        msg += "\nTe esperamos! Se precisar remarcar, responda esta mensagem. 💈👊"
        return msg

    @classmethod
    def format_reminder_1h(cls, appointment, barbershop) -> str:
        hora_formatada = appointment.date_time.strftime('%H:%M')
        msg = (
            f"⏰ *LEMBRETE — SEU HORÁRIO É EM 1 HORA!* 💈\n\n"
            f"Olá, *{appointment.customer_name}*!\n"
            f"Passando para avisar que seu atendimento na *{barbershop.name}* está marcado para hoje às *{hora_formatada}*.\n\n"
            f"✂️ *Serviço:* {appointment.service.name}\n"
            f"💈 *Barbeiro:* {appointment.barber.name}\n"
        )
        if barbershop.address:
            msg += f"📍 *Local:* {barbershop.address}\n"
            
        msg += "\nJá estamos preparando sua cadeira na régua! Até já! ✂️🔥"
        return msg

    @classmethod
    def format_review_request(cls, appointment, barbershop, review_url: str) -> str:
        msg = (
            f"⭐ *O QUE ACHOU DO SEU CORTE? — {barbershop.name.upper()}*\n\n"
            f"Olá, *{appointment.customer_name}*! Esperamos que tenha curtido o resultado com o barbeiro *{appointment.barber.name}*! 💈\n\n"
            f"Sua avaliação é muito importante para nós. Dê sua nota de 0 a 5 estrelas e conte como foi sua experiência:\n\n"
            f"👉 *Avalie aqui em 20 segundos:* {review_url}\n\n"
            f"Sua avaliação aparecerá no site da nossa barbearia. Muito obrigado pela preferência! 👊🔥"
        )
        return msg

    @classmethod
    def send_simulated_email(cls, to_email: Optional[str], subject: str, body: str) -> bool:
        """Simulação e log de envio de e-mail limpo."""
        if not to_email or "@" not in to_email:
            return False
        print(f"[E-MAIL ENVIADO] Para: {to_email} | Assunto: {subject}")
        return True
