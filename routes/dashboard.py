from datetime import datetime, date, time
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    User, Barbershop, Appointment, FinancialRecord, Subscription, Service, Barber, Product
)
from app.auth import get_current_user

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    today = date.today()
    start_of_today = datetime.combine(today, time.min)
    end_of_today = datetime.combine(today, time.max)
    start_of_month = datetime(today.year, today.month, 1)

    # 1. Faturamento de Hoje
    today_income = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "income",
        FinancialRecord.date >= start_of_today,
        FinancialRecord.date <= end_of_today
    ).scalar() or 0.0

    # 2. Faturamento do Mês
    month_income = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "income",
        FinancialRecord.date >= start_of_month
    ).scalar() or 0.0

    # 3. Despesas do Mês
    month_expenses = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "expense",
        FinancialRecord.date >= start_of_month
    ).scalar() or 0.0

    # 4. Comissões a pagar / acumuladas no mês
    total_commissions_generated = db.query(func.coalesce(func.sum(Appointment.barber_commission_amount), 0.0)).filter(
        Appointment.barbershop_id == barbershop.id,
        Appointment.status == "completed",
        Appointment.date_time >= start_of_month
    ).scalar() or 0.0

    commissions_already_paid = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "commission_payout",
        FinancialRecord.date >= start_of_month
    ).scalar() or 0.0

    commissions_pending = max(0.0, total_commissions_generated - commissions_already_paid)

    # 5. Agendamentos de Hoje
    today_appointments = db.query(Appointment).filter(
        Appointment.barbershop_id == barbershop.id,
        Appointment.date_time >= start_of_today,
        Appointment.date_time <= end_of_today
    ).order_by(Appointment.date_time.asc()).all()

    # 6. Assinantes Ativos do Clube
    active_subscriptions_count = db.query(Subscription).filter(
        Subscription.barbershop_id == barbershop.id,
        Subscription.status == "active"
    ).count()

    # Recorrência mensal estimada (MRR)
    mrr_total = sum(s.plan.price for s in db.query(Subscription).filter(
        Subscription.barbershop_id == barbershop.id,
        Subscription.status == "active"
    ).all() if s.plan)

    # 7. Últimas movimentações financeiras
    recent_transactions = db.query(FinancialRecord).filter(
        FinancialRecord.barbershop_id == barbershop.id
    ).order_by(FinancialRecord.date.desc()).limit(8).all()

    # Contagens gerais
    total_barbers = db.query(Barber).filter(Barber.barbershop_id == barbershop.id, Barber.is_active == True).count()
    total_services = db.query(Service).filter(Service.barbershop_id == barbershop.id, Service.is_active == True).count()
    total_products = db.query(Product).filter(Product.barbershop_id == barbershop.id, Product.is_active == True).count()

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "today_income": today_income,
            "month_income": month_income,
            "month_expenses": month_expenses,
            "net_profit": month_income - month_expenses - commissions_already_paid,
            "commissions_pending": commissions_pending,
            "today_appointments": today_appointments,
            "active_subscriptions_count": active_subscriptions_count,
            "mrr_total": mrr_total,
            "recent_transactions": recent_transactions,
            "total_barbers": total_barbers,
            "total_services": total_services,
            "total_products": total_products
        }
    )
