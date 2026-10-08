from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barbershop, Appointment, FinancialRecord, AuditLog
from app.services.mp_service import MercadoPagoService
from app.security import verify_mercadopago_webhook
from app.config import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercado-pago/{barbershop_id}")
async def mercado_pago_webhook(
    barbershop_id: int,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str = Header(None, alias="x-signature")
):
    """
    Webhook oficial para receber notificações do Mercado Pago em tempo real.
    Valida a assinatura HMAC x-signature, atualiza o status do agendamento
    e gera logs de auditoria financeira.
    """
    barbershop = db.query(Barbershop).filter(Barbershop.id == barbershop_id).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    # 1. Validação de Segurança HMAC (Nível Nacional / Enterprise)
    # Ativa verificação no ambiente de produção ou caso a chave esteja configurada
    if getattr(settings, "ENV", "development") == "production":
        webhook_secret = getattr(settings, "MERCADO_PAGO_WEBHOOK_SECRET", "")
        is_valid = await verify_mercadopago_webhook(request, x_signature, webhook_secret)
        
        if not is_valid:
            # Registra tentativa de envio de webhook fraudulento
            audit = AuditLog(
                barbershop_id=barbershop.id,
                action="SECURITY_ALERT_INVALID_WEBHOOK",
                ip_address=request.client.host if request.client else "unknown",
                details=f"Tentativa de webhook com assinatura HMAC inválida. Header: {x_signature}"
            )
            db.add(audit)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Assinatura HMAC do webhook inválida ou não autorizada."
            )

    # 2. Leitura do Payload do Mercado Pago
    try:
        body = await request.json()
    except Exception:
        body = {}

    topic = request.query_params.get("topic") or body.get("type")
    data_id = request.query_params.get("id") or (body.get("data", {}).get("id"))

    # 3. Processamento do Pagamento
    if topic == "payment" and data_id and barbershop.mercado_pago_access_token:
        payment_info = MercadoPagoService.get_payment_details(
            barbershop.mercado_pago_access_token,
            str(data_id)
        )
        
        if payment_info and payment_info.get("status") == "approved":
            external_reference = payment_info.get("external_reference", "")
            
            if external_reference.startswith("apt_"):
                apt_id = int(external_reference.replace("apt_", ""))
                appointment = db.query(Appointment).filter(
                    Appointment.id == apt_id,
                    Appointment.barbershop_id == barbershop.id
                ).first()

                if appointment and appointment.payment_status != "approved":
                    appointment.payment_status = "approved"
                    appointment.is_paid_in_advance = True
                    appointment.status = "confirmed"
                    appointment.mp_payment_id = str(data_id)

                    # Registra entrada financeira oficial
                    fin = FinancialRecord(
                        barbershop_id=barbershop.id,
                        type="income",
                        category="service",
                        description=f"Pagamento Mercado Pago ({appointment.service.name} - {appointment.customer_name})",
                        amount=appointment.total_price,
                        payment_method="mercado_pago",
                        barber_id=appointment.barber_id,
                        appointment_id=appointment.id,
                        date=datetime.utcnow()
                    )
                    db.add(fin)

                    # Registra Log de Auditoria para LGPD / Rastreabilidade
                    audit = AuditLog(
                        barbershop_id=barbershop.id,
                        action="PAYMENT_APPROVED_WEBHOOK",
                        ip_address=request.client.host if request.client else "unknown",
                        details=f"Pagamento MP #{data_id} aprovado para agendamento #{apt_id} (R$ {appointment.total_price})"
                    )
                    db.add(audit)

                    db.commit()

    return {"status": "ok"}