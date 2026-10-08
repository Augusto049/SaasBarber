import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    Barbershop, Service, Barber, Appointment, SubscriptionPlan, Subscription, FinancialRecord, Review,
    BusinessHour
)
from app.services.mp_service import MercadoPagoService
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService
from app.services.whatsapp_service import WhatsAppService
from app.config import settings

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/b/{slug}", response_class=HTMLResponse)
async def public_barbershop_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    barbershop = db.query(Barbershop).filter(Barbershop.slug == slug).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    services = db.query(Service).filter(
        Service.barbershop_id == barbershop.id,
        Service.is_active == True
    ).order_by(Service.price.asc()).all()

    barbers = db.query(Barber).filter(
        Barber.barbershop_id == barbershop.id,
        Barber.is_active == True
    ).order_by(Barber.name.asc()).all()

    business_hours = db.query(BusinessHour).filter(
        BusinessHour.barbershop_id == barbershop.id
    ).all()
    schedule_data = None
    if business_hours:
        schedule_data = {}
        for row in business_hours:
            periods = []
            for start, end in (
                (row.period_1_start, row.period_1_end),
                (row.period_2_start, row.period_2_end),
            ):
                if start and end:
                    periods.append([start.strftime("%H:%M"), end.strftime("%H:%M")])
            schedule_data[str((row.weekday + 1) % 7)] = periods

    service_durations = {
        str(service.id): service.duration_minutes or 30
        for service in services
    }

    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.barbershop_id == barbershop.id,
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.price.asc()).all()

    # Avaliações de 0 a 5 estrelas
    reviews = db.query(Review).filter(
        Review.barbershop_id == barbershop.id,
        Review.is_approved == True
    ).order_by(Review.created_at.desc()).all()

    avg_rating = db.query(func.coalesce(func.avg(Review.rating), 5.0)).filter(
        Review.barbershop_id == barbershop.id,
        Review.is_approved == True
    ).scalar() or 5.0

    subscribed = request.query_params.get("subscribed") == "true"
    booked = request.query_params.get("booked") == "true"
    apt_id = request.query_params.get("apt_id")

    whatsapp_confirm_url = None
    recent_apt = None
    if booked and apt_id:
        recent_apt = db.query(Appointment).filter(Appointment.id == int(apt_id)).first()
        if recent_apt:
            msg = NotificationService.format_booking_confirmation(recent_apt, barbershop)
            whatsapp_confirm_url = NotificationService.get_whatsapp_url(recent_apt.customer_phone, msg)

    return templates.TemplateResponse(
        request=request,
        name="public/barbershop.html",
        context={
            "barbershop": barbershop,
            "services": services,
            "barbers": barbers,
            "schedule_data": schedule_data,
            "service_durations": service_durations,
            "plans": plans,
            "reviews": reviews,
            "avg_rating": round(float(avg_rating), 1),
            "review_count": len(reviews),
            "subscribed": subscribed,
            "booked": booked,
            "recent_apt": recent_apt,
            "whatsapp_confirm_url": whatsapp_confirm_url
        }
    )

@router.post("/b/{slug}/book")
async def public_book_appointment(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service_id: int = Form(...),
    barber_id: int = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: str = Form(""),
    date_str: str = Form(...), # YYYY-MM-DDTHH:MM
    pay_online: bool = Form(False),
    db: Session = Depends(get_db)
):
    barbershop = db.query(Barbershop).filter(Barbershop.slug == slug).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    service = db.query(Service).filter(
        Service.id == service_id,
        Service.barbershop_id == barbershop.id
    ).first()
    barber = db.query(Barber).filter(
        Barber.id == barber_id,
        Barber.barbershop_id == barbershop.id
    ).first()

    if not service or not barber:
        raise HTTPException(status_code=400, detail="Serviço ou barbeiro inválido.")

    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        dt = datetime.now() + timedelta(hours=2)

    configured_hours = db.query(BusinessHour).filter(
        BusinessHour.barbershop_id == barbershop.id
    ).all()
    if configured_hours:
        weekday_hours = next(
            (row for row in configured_hours if row.weekday == dt.weekday()),
            None,
        )
        appointment_end = dt + timedelta(minutes=service.duration_minutes or 30)
        periods = [
            (weekday_hours.period_1_start, weekday_hours.period_1_end),
            (weekday_hours.period_2_start, weekday_hours.period_2_end),
        ] if weekday_hours else []
        if not any(
            start and end and start <= dt.time()
            and appointment_end.date() == dt.date()
            and appointment_end.time() <= end
            for start, end in periods
        ):
            raise HTTPException(
                status_code=400,
                detail="Este horário está fora do funcionamento da barbearia.",
            )

    commission = round(service.price * (barber.commission_percent / 100.0), 2)

    appointment = Appointment(
        barbershop_id=barbershop.id,
        barber_id=barber.id,
        service_id=service.id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        customer_email=customer_email.strip(),
        date_time=dt,
        status="scheduled" if pay_online else "confirmed",
        is_paid_in_advance=False,
        payment_status="pending",
        payment_method="mp_online" if pay_online else "in_person",
        total_price=service.price,
        barber_commission_amount=commission,
        review_token=uuid.uuid4().hex[:16],
        notes="Agendado pelo portal público"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # Dispara mensagem de confirmação no WhatsApp em segundo plano
    formatted_date = appointment.date_time.strftime("%d/%m/%Y")
    formatted_time = appointment.date_time.strftime("%H:%M")
    background_tasks.add_task(
        WhatsAppService.send_booking_confirmation,
        customer_name=appointment.customer_name,
        phone=appointment.customer_phone,
        service_name=service.name,
        barber_name=barber.name,
        date_str=formatted_date,
        time_str=formatted_time
    )

    # Dispara e-mail de confirmação se o cliente informou
    if appointment.customer_email:
        sent = EmailService.send_booking_confirmation(
            customer_name=appointment.customer_name,
            to_email=appointment.customer_email,
            service_name=service.name,
            barber_name=barber.name,
            date_str=formatted_date,
            time_str=formatted_time,
        )

        if not sent:
            NotificationService.send_simulated_email(
                to_email=appointment.customer_email,
                subject=f"Confirmação de Agendamento - {barbershop.name}",
                body=NotificationService.format_booking_confirmation(appointment, barbershop)
            )

    # Se escolheu pagar antecipado pelo Mercado Pago
    if pay_online:
        base_url = str(request.base_url).rstrip("/")
        mp_data = MercadoPagoService.create_appointment_preference(
            access_token=barbershop.mercado_pago_access_token,
            barbershop_name=barbershop.name,
            barbershop_slug=barbershop.slug,
            service_name=service.name,
            service_price=service.price,
            barber_name=barber.name,
            appointment_id=appointment.id,
            customer_name=customer_name.strip(),
            customer_email=customer_email.strip(),
            customer_phone=customer_phone.strip(),
            base_url=base_url
        )
        appointment.mp_preference_id = mp_data.get("id")
        appointment.mp_init_point = mp_data.get("init_point")
        db.commit()

        # Redireciona para o checkout do Mercado Pago
        return RedirectResponse(url=appointment.mp_init_point, status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url=f"/b/{slug}?booked=true&apt_id={appointment.id}", status_code=status.HTTP_302_FOUND)

@router.post("/b/{slug}/subscribe")
async def public_subscribe_plan(
    slug: str,
    request: Request,
    plan_id: int = Form(...),
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    db: Session = Depends(get_db)
):
    barbershop = db.query(Barbershop).filter(Barbershop.slug == slug).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.barbershop_id == barbershop.id,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(status_code=400, detail="Plano não encontrado.")

    base_url = str(request.base_url).rstrip("/")
    mp_res = MercadoPagoService.create_subscription_preference(
        access_token=barbershop.mercado_pago_access_token,
        barbershop_name=barbershop.name,
        plan_id=plan.id,
        plan_name=plan.name,
        plan_price=plan.price,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip(),
        customer_phone=customer_phone.strip(),
        base_url=base_url
    )

    init_point = mp_res.get("init_point")
    return RedirectResponse(url=init_point, status_code=status.HTTP_302_FOUND)


# --- TELAS DE CHECKOUT MERCADO PAGO E SIMULAÇÃO SEGURA ---

@router.get("/checkout/simulate", response_class=HTMLResponse)
async def checkout_simulate(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    return templates.TemplateResponse(
        request=request,
        name="public/simulate_checkout.html",
        context={
            "appointment": appointment,
            "barbershop": appointment.barbershop
        }
    )

@router.post("/checkout/simulate/confirm")
async def checkout_simulate_confirm(
    appointment_id: int = Form(...),
    payment_method: str = Form("pix"),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    appointment.is_paid_in_advance = True
    appointment.payment_status = "approved"
    appointment.status = "confirmed"
    appointment.payment_method = f"mp_{payment_method}"

    # Registra no fluxo financeiro da barbearia
    fin = FinancialRecord(
        barbershop_id=appointment.barbershop_id,
        type="income",
        category="service",
        description=f"Pagamento Antecipado MP ({payment_method.upper()}): {appointment.service.name} ({appointment.customer_name})",
        amount=appointment.total_price,
        payment_method=f"mp_{payment_method}",
        barber_id=appointment.barber_id,
        appointment_id=appointment.id
    )
    db.add(fin)
    db.commit()

    return RedirectResponse(
        url=f"/checkout/success?appointment_id={appointment.id}",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/checkout/simulate-subscription", response_class=HTMLResponse)
async def checkout_simulate_subscription(
    plan_id: int,
    email: str,
    name: str,
    phone: str,
    request: Request,
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    return templates.TemplateResponse(
        request=request,
        name="public/simulate_subscription.html",
        context={
            "plan": plan,
            "barbershop": plan.barbershop,
            "name": name,
            "email": email,
            "phone": phone
        }
    )

@router.post("/checkout/simulate-subscription/confirm")
async def checkout_simulate_subscription_confirm(
    plan_id: int = Form(...),
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    payment_method: str = Form("card"),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    # Cria ou ativa assinatura
    sub = Subscription(
        barbershop_id=plan.barbershop_id,
        plan_id=plan.id,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip().lower(),
        customer_phone=customer_phone.strip(),
        status="active",
        start_date=datetime.now(),
        next_billing_date=datetime.now() + timedelta(days=30),
        mp_preapproval_id=f"mp_sub_sim_{datetime.now().timestamp()}",
        cuts_used_this_month=0
    )
    db.add(sub)

    # Registra a receita recorrente
    fin = FinancialRecord(
        barbershop_id=plan.barbershop_id,
        type="income",
        category="subscription",
        description=f"Assinatura Mensal Clube ({plan.name}): {customer_name.strip()}",
        amount=plan.price,
        payment_method=f"mp_{payment_method}"
    )
    db.add(fin)
    db.commit()

    return RedirectResponse(
        url=f"/b/{plan.barbershop.slug}?subscribed=true",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    return templates.TemplateResponse(
        request=request,
        name="public/checkout_success.html",
        context={
            "appointment": appointment
        }
    )

@router.get("/checkout/failure", response_class=HTMLResponse)
async def checkout_failure(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    return templates.TemplateResponse(
        request=request,
        name="public/checkout_failure.html",
        context={
            "appointment": appointment
        }
    )

# --- ROTAS DE AVALIAÇÃO DE 0 A 5 ESTRELAS ---

@router.get("/b/{slug}/avaliar/{token}", response_class=HTMLResponse)
async def review_page(
    slug: str,
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    barbershop = db.query(Barbershop).filter(Barbershop.slug == slug).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    appointment = db.query(Appointment).filter(
        Appointment.review_token == token,
        Appointment.barbershop_id == barbershop.id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Link de avaliação inválido ou expirado.")

    # Verifica se já avaliou
    existing_review = db.query(Review).filter(Review.appointment_id == appointment.id).first()

    return templates.TemplateResponse(
        request=request,
        name="public/review_form.html",
        context={
            "barbershop": barbershop,
            "appointment": appointment,
            "existing_review": existing_review,
            "token": token
        }
    )

@router.post("/b/{slug}/avaliar/{token}", response_class=HTMLResponse)
async def submit_review(
    slug: str,
    token: str,
    request: Request,
    rating: int = Form(5), # 0 a 5
    comment: str = Form(""),
    db: Session = Depends(get_db)
):
    barbershop = db.query(Barbershop).filter(Barbershop.slug == slug).first()
    if not barbershop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.")

    appointment = db.query(Appointment).filter(
        Appointment.review_token == token,
        Appointment.barbershop_id == barbershop.id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    # Se já existir avaliação, atualiza, senão cria
    review = db.query(Review).filter(Review.appointment_id == appointment.id).first()
    rating_val = max(0, min(5, int(rating)))

    if review:
        review.rating = rating_val
        review.comment = comment.strip()
    else:
        review = Review(
            barbershop_id=barbershop.id,
            appointment_id=appointment.id,
            barber_id=appointment.barber_id,
            customer_name=appointment.customer_name,
            rating=rating_val,
            comment=comment.strip(),
            is_approved=True # Publica automaticamente no site
        )
        db.add(review)

    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="public/review_success.html",
        context={
            "barbershop": barbershop,
            "review": review
        }
    )