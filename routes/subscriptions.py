from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, SubscriptionPlan, Subscription, FinancialRecord
from app.auth import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_subscriptions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    show_archived = request.query_params.get("show_archived") == "true"

    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.barbershop_id == barbershop.id,
        SubscriptionPlan.is_active.is_(not show_archived),
    ).order_by(SubscriptionPlan.price.asc()).all()
    active_plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.barbershop_id == barbershop.id,
        SubscriptionPlan.is_active.is_(True),
    ).order_by(SubscriptionPlan.price.asc()).all()
    archived_count = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.barbershop_id == barbershop.id,
        SubscriptionPlan.is_active.is_(False),
    ).count()

    subscribers = db.query(Subscription).filter(
        Subscription.barbershop_id == barbershop.id
    ).order_by(Subscription.start_date.desc()).all()

    # Recorrência mensal estimada (MRR)
    mrr = sum(sub.plan.price for sub in subscribers if sub.status == "active" and sub.plan)

    return templates.TemplateResponse(
        request=request,
        name="subscriptions/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "plans": plans,
            "active_plans": active_plans,
            "show_archived": show_archived,
            "archived_count": archived_count,
            "archived_notice": request.query_params.get("archived") == "true",
            "deleted_notice": request.query_params.get("deleted") == "true",
            "subscribers": subscribers,
            "mrr": mrr
        }
    )

@router.post("/plans/new")
async def create_plan(
    name: str = Form(...),
    price: float = Form(...),
    included_cuts_per_month: int = Form(999), # 999 = ilimitado
    included_services_text: str = Form("Cortes de cabelo ilimitados"),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plan = SubscriptionPlan(
        barbershop_id=current_user.barbershop_id,
        name=name.strip(),
        price=float(price),
        included_cuts_per_month=int(included_cuts_per_month),
        included_services_text=included_services_text.strip(),
        description=description.strip()
    )
    db.add(plan)
    db.commit()
    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)


@router.post("/plans/{plan_id}/delete")
async def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.barbershop_id == current_user.barbershop_id
    ).first()
    if plan:
        if plan.subscriptions:
            plan.is_active = False
            db.commit()
            return RedirectResponse(
                url="/subscriptions?archived=true",
                status_code=status.HTTP_302_FOUND,
            )

        db.delete(plan)
        db.commit()
        return RedirectResponse(
            url="/subscriptions?deleted=true",
            status_code=status.HTTP_302_FOUND,
        )

    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)

@router.post("/plans/{plan_id}/edit")
async def edit_plan(
    plan_id: int,
    name: str = Form(...),
    price: float = Form(...),
    included_cuts_per_month: int = Form(...),
    included_services_text: str = Form(...),
    description: str = Form(""),
    is_active: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.barbershop_id == current_user.barbershop_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    plan.name = name.strip()
    plan.price = float(price)
    plan.included_cuts_per_month = int(included_cuts_per_month)
    plan.included_services_text = included_services_text.strip()
    plan.description = description.strip()
    plan.is_active = is_active
    db.commit()

    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)

@router.post("/subscribers/new")
async def create_subscriber_manual(
    plan_id: int = Form(...),
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    register_payment: bool = Form(True),
    payment_method: str = Form("pix"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.barbershop_id == current_user.barbershop_id,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    sub = Subscription(
        barbershop_id=current_user.barbershop_id,
        plan_id=plan.id,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip().lower(),
        customer_phone=customer_phone.strip(),
        status="active",
        start_date=datetime.now(),
        next_billing_date=datetime.now() + timedelta(days=30),
        cuts_used_this_month=0
    )
    db.add(sub)

    # Registrar receita da mensalidade no financeiro se solicitado
    if register_payment:
        fin = FinancialRecord(
            barbershop_id=current_user.barbershop_id,
            type="income",
            category="subscription",
            description=f"Mensalidade do Clube - {plan.name} ({customer_name.strip()})",
            amount=plan.price,
            payment_method=payment_method
        )
        db.add(fin)

    db.commit()
    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)

@router.post("/{sub_id}/use-cut")
async def use_subscription_cut(
    sub_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(
        Subscription.id == sub_id,
        Subscription.barbershop_id == current_user.barbershop_id
    ).first()
    if sub and sub.status == "active":
        sub.cuts_used_this_month += 1
        db.commit()
    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)

@router.post("/{sub_id}/toggle-status")
async def toggle_subscription_status(
    sub_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(
        Subscription.id == sub_id,
        Subscription.barbershop_id == current_user.barbershop_id
    ).first()
    if sub:
        sub.status = "canceled" if sub.status == "active" else "active"
        db.commit()
    return RedirectResponse(url="/subscriptions", status_code=status.HTTP_302_FOUND)
