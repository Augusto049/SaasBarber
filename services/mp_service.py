import mercadopago
from typing import Optional, Dict, Any
from app.config import settings

class MercadoPagoService:
    @staticmethod
    def get_client(access_token: Optional[str]):
        if not access_token:
            return None
        try:
            return mercadopago.SDK(access_token)
        except Exception:
            return None

    @classmethod
    def create_appointment_preference(
        cls,
        access_token: Optional[str],
        barbershop_name: str,
        barbershop_slug: str,
        service_name: str,
        service_price: float,
        barber_name: str,
        appointment_id: int,
        customer_name: str,
        customer_email: Optional[str],
        customer_phone: str,
        base_url: str
    ) -> Dict[str, Any]:
        """
        Cria uma preferência de pagamento seguro no Mercado Pago (Checkout Pro).
        O cliente é redirecionado para o ambiente seguro do Mercado Pago para pagar com PIX ou Cartão.
        Nenhum dado sensível de cartão trafega no nosso servidor.
        """
        # Se a barbearia ainda não configurou o token real, criamos um link de simulação realista para testes locais
        if not access_token or access_token.strip() == "" or access_token.startswith("TEST-EXEMPLO"):
            return {
                "id": f"simulated_pref_{appointment_id}",
                "init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "sandbox_init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "is_simulated": True
            }

        sdk = cls.get_client(access_token)
        if not sdk:
            return {
                "id": f"simulated_pref_{appointment_id}",
                "init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "sandbox_init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "is_simulated": True
            }

        preference_data = {
            "items": [
                {
                    "id": str(appointment_id),
                    "title": f"{barbershop_name} - {service_name}",
                    "description": f"Serviço com o barbeiro {barber_name}",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(service_price)
                }
            ],
            "payer": {
                "name": customer_name,
                "email": customer_email if customer_email and "@" in customer_email else "cliente@barbearia.com",
                "phone": {
                    "number": customer_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                }
            },
            "back_urls": {
                "success": f"{base_url}/checkout/success?appointment_id={appointment_id}",
                "failure": f"{base_url}/checkout/failure?appointment_id={appointment_id}",
                "pending": f"{base_url}/checkout/pending?appointment_id={appointment_id}"
            },
            "auto_return": "approved",
            "external_reference": f"apt_{appointment_id}",
            "statement_descriptor": barbershop_name[:15]
        }

        try:
            preference_response = sdk.preference().create(preference_data)
            pref = preference_response.get("response", {})
            return {
                "id": pref.get("id"),
                "init_point": pref.get("init_point"),
                "sandbox_init_point": pref.get("sandbox_init_point"),
                "is_simulated": False
            }
        except Exception as e:
            # Fallback seguro para simulação se credencial for inválida
            return {
                "id": f"simulated_pref_{appointment_id}",
                "init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "sandbox_init_point": f"{base_url}/checkout/simulate?appointment_id={appointment_id}",
                "is_simulated": True,
                "error": str(e)
            }

    @classmethod
    def create_subscription_preference(
        cls,
        access_token: Optional[str],
        barbershop_name: str,
        plan_id: int,
        plan_name: str,
        plan_price: float,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        base_url: str
    ) -> Dict[str, Any]:
        """
        Cria um checkout para assinatura mensal (estilo Netflix / Amazon Prime) no Mercado Pago.
        """
        if not access_token or access_token.strip() == "" or access_token.startswith("TEST-EXEMPLO"):
            return {
                "id": f"simulated_sub_pref_{plan_id}",
                "init_point": f"{base_url}/checkout/simulate-subscription?plan_id={plan_id}&email={customer_email}&name={customer_name}&phone={customer_phone}",
                "is_simulated": True
            }

        sdk = cls.get_client(access_token)
        if not sdk:
            return {
                "id": f"simulated_sub_pref_{plan_id}",
                "init_point": f"{base_url}/checkout/simulate-subscription?plan_id={plan_id}&email={customer_email}&name={customer_name}&phone={customer_phone}",
                "is_simulated": True
            }

        # Criação de preferência recorrente/assinatura
        preapproval_data = {
            "reason": f"Assinatura Mensal {barbershop_name} - {plan_name}",
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": float(plan_price),
                "currency_id": "BRL"
            },
            "payer_email": customer_email if customer_email and "@" in customer_email else "cliente@barbearia.com",
            "back_url": f"{base_url}/checkout/subscription-success?plan_id={plan_id}&email={customer_email}&name={customer_name}&phone={customer_phone}",
            "external_reference": f"sub_plan_{plan_id}"
        }

        try:
            res = sdk.preapproval().create(preapproval_data)
            resp_data = res.get("response", {})
            return {
                "id": resp_data.get("id"),
                "init_point": resp_data.get("init_point"),
                "is_simulated": False
            }
        except Exception:
            # Fallback para checkout direto
            return {
                "id": f"simulated_sub_pref_{plan_id}",
                "init_point": f"{base_url}/checkout/simulate-subscription?plan_id={plan_id}&email={customer_email}&name={customer_name}&phone={customer_phone}",
                "is_simulated": True
            }

    @classmethod
    def get_payment_details(cls, access_token: str, payment_id: str) -> Optional[Dict[str, Any]]:
        sdk = cls.get_client(access_token)
        if not sdk:
            return None
        try:
            res = sdk.payment().get(payment_id)
            return res.get("response", {})
        except Exception:
            return None
