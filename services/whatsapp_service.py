# app/services/whatsapp_service.py
import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    @staticmethod
    def send_message(phone_number: str, message: str) -> bool:
        """
        Envia uma mensagem de texto no WhatsApp para o número cadastrado.
        Limpa caracteres não numéricos e formata com o código do país (DDI 55).
        """
        # Limpa o número mantendo apenas dígitos
        clean_phone = "".join(filter(str.isdigit, phone_number or ""))
        if not clean_phone:
            return False

        # Adiciona DDI 55 do Brasil se não estiver presente
        if len(clean_phone) in [10, 11]:
            clean_phone = f"55{clean_phone}"

        # Exemplo utilizando endpoint genérico da sua API de WhatsApp escolhida
        # (Ajuste os campos 'url', 'headers' e 'payload' de acordo com seu provedor)
        api_url = getattr(settings, "WHATSAPP_API_URL", "")
        api_token = getattr(settings, "WHATSAPP_API_TOKEN", "")

        if not api_url or not api_token:
            logger.warning("Configurações da API de WhatsApp não foram preenchidas no .env")
            return False

        try:
            payload = {
                "number": clean_phone,
                "message": message
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_token}"
            }
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem via WhatsApp: {e}")
            return False

    @staticmethod
    def send_booking_confirmation(customer_name: str, phone: str, service_name: str, barber_name: str, date_str: str, time_str: str):
        """Dispara mensagem de confirmação imediata no momento do agendamento."""
        msg = (
            f"💈 *Agendamento Confirmado!*\n\n"
            f"Olá, *{customer_name}*! Seu horário foi reservado com sucesso.\n\n"
            f"✂️ *Serviço:* {service_name}\n"
            f"👤 *Profissional:* {barber_name}\n"
            f"📅 *Data:* {date_str}\n"
            f"⏰ *Horário:* {time_str}\n\n"
            f"Agradecemos a preferência! Te aguardamos na barbearia."
        )
        return WhatsAppService.send_message(phone, msg)

    @staticmethod
    def send_booking_reminder(customer_name: str, phone: str, service_name: str, time_str: str):
        """Dispara lembrete 1 hora antes do atendimento."""
        msg = (
            f"⏰ *Lembrete de Agendamento!*\n\n"
            f"Olá, *{customer_name}*! Passando para lembrar que seu atendimento é daqui a pouco.\n\n"
            f"✂️ *Serviço:* {service_name}\n"
            f"⏰ *Horário:* {time_str} (daqui a ~1 hora)\n\n"
            f"Caso precise remarcar, entre em contato conosco o quanto antes."
        )
        return WhatsAppService.send_message(phone, msg)