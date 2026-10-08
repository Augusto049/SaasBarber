from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Appointment, Barber, Service, FinancialRecord, Subscription
from app.auth import get_current_user

router = APIRouter(prefix="/appointments", tags=["appointments"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_appointments(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop

    appointments = db.query(Appointment).filter(
        Appointment.barbershop_id == barbershop.id
    ).order_by(Appointment.date_time.desc()).all()

    barbers = db.query(Barber).filter(
        Barber.barbershop_id == barbershop.id,
        Barber.is_active == True
    ).order_by(Barber.name.asc()).all()

    services = db.query(Service).filter(
        Service.barbershop_id == barbershop.id,
        Service.is_active == True
    ).order_by(Service.name.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="appointments/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "appointments": appointments,
            "barbers": barbers,
            "services": services
        }
    )

@router.post("/new")
async def create_appointment(
    barber_id: int = Form(...),
    service_id: int = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: str = Form(""),
    date_str: str = Form(...), # format: "YYYY-MM-DDTHH:MM"
    payment_method: str = Form("in_person"),
    is_subscription_client: bool = Form(False),
    notes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barber = db.query(Barber).filter(
        Barber.id == barber_id,
        Barber.barbershop_id == current_user.barbershop_id
    ).first()
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.barbershop_id == current_user.barbershop_id
    ).first()

    if not barber or not service:
        raise HTTPException(status_code=400, detail="Barbeiro ou serviço inválido.")

    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        dt = datetime.now()

    price = 0.0 if is_subscription_client else service.price
    commission = round(price * (barber.commission_percent / 100.0), 2)

    appointment = Appointment(
        barbershop_id=current_user.barbershop_id,
        barber_id=barber.id,
        service_id=service.id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        customer_email=customer_email.strip(),
        date_time=dt,
        status="confirmed",
        is_paid_in_advance=False,
        payment_status="subscription" if is_subscription_client else "pending",
        payment_method="subscription" if is_subscription_client else payment_method,
        total_price=price,
        barber_commission_amount=commission,
        notes=notes.strip()
    )
    db.add(appointment)
    db.commit()

    return RedirectResponse(url="/appointments", status_code=status.HTTP_302_FOUND)

@router.post("/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: int,
    payment_method: str = Form("cash"), # cash, pix, card_in_person, subscription
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.barbershop_id == current_user.barbershop_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    appointment.status = "completed"
    
    # Se ainda não foi pago antecipado pelo Mercado Pago
    if not appointment.is_paid_in_advance and appointment.payment_status != "subscription":
        appointment.payment_status = "approved"
        appointment.payment_method = payment_method

        # Registrar entrada no financeiro se valor > 0
        if appointment.total_price > 0:
            fin = FinancialRecord(
                barbershop_id=current_user.barbershop_id,
                type="income",
                category="service",
                description=f"Atendimento: {appointment.service.name} ({appointment.customer_name})",
                amount=appointment.total_price,
                payment_method=payment_method,
                barber_id=appointment.barber_id,
                appointment_id=appointment.id
            )
            db.add(fin)

    db.commit()
    return RedirectResponse(url="/appointments", status_code=status.HTTP_302_FOUND)

@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.barbershop_id == current_user.barbershop_id
    ).first()
    if appointment:
        appointment.status = "canceled"
        db.commit()
    return RedirectResponse(url="/appointments", status_code=status.HTTP_302_FOUND)
