from datetime import datetime, date
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, FinancialRecord, Barber, Appointment
from app.auth import get_current_user

router = APIRouter(prefix="/finances", tags=["finances"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def finances_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop

    # Total de Receitas
    total_income = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "income"
    ).scalar() or 0.0

    # Total de Despesas Operacionais
    total_expenses = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "expense"
    ).scalar() or 0.0

    # Total de Comissões já pagas aos barbeiros
    total_commissions_paid = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
        FinancialRecord.barbershop_id == barbershop.id,
        FinancialRecord.type == "commission_payout"
    ).scalar() or 0.0

    # Lucro Líquido = Receitas - Despesas - Comissões Pagas
    net_profit = total_income - total_expenses - total_commissions_paid

    # Resumo por barbeiro
    barbers = db.query(Barber).filter(
        Barber.barbershop_id == barbershop.id
    ).all()

    barber_summaries = []
    total_pending_commissions = 0.0
    for barber in barbers:
        earned = db.query(func.coalesce(func.sum(Appointment.barber_commission_amount), 0.0)).filter(
            Appointment.barber_id == barber.id,
            Appointment.status == "completed"
        ).scalar() or 0.0

        paid = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
            FinancialRecord.barber_id == barber.id,
            FinancialRecord.type == "commission_payout"
        ).scalar() or 0.0

        balance = max(0.0, earned - paid)
        total_pending_commissions += balance
        barber_summaries.append({
            "barber": barber,
            "earned": earned,
            "paid": paid,
            "balance": balance
        })

    # Registros financeiros recentes
    records = db.query(FinancialRecord).filter(
        FinancialRecord.barbershop_id == barbershop.id
    ).order_by(FinancialRecord.date.desc()).limit(50).all()

    return templates.TemplateResponse(
        request=request,
        name="finances/index.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_commissions_paid": total_commissions_paid,
            "total_pending_commissions": total_pending_commissions,
            "net_profit": net_profit,
            "barber_summaries": barber_summaries,
            "records": records,
            "barbers": barbers
        }
    )

@router.post("/expense/new")
async def create_expense(
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form("rent"), # rent, supplies, utilities, other
    payment_method: str = Form("pix"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fin = FinancialRecord(
        barbershop_id=current_user.barbershop_id,
        type="expense",
        category=category,
        description=description.strip(),
        amount=float(amount),
        payment_method=payment_method,
        date=datetime.now()
    )
    db.add(fin)
    db.commit()
    return RedirectResponse(url="/finances", status_code=status.HTTP_302_FOUND)

@router.post("/commission/payout")
async def payout_commission(
    barber_id: int = Form(...),
    amount: float = Form(...),
    payment_method: str = Form("pix"),
    notes: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barber = db.query(Barber).filter(
        Barber.id == barber_id,
        Barber.barbershop_id == current_user.barbershop_id
    ).first()
    if not barber:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")

    description = f"Repasse de comissão para {barber.name}"
    if notes.strip():
        description += f" ({notes.strip()})"

    fin = FinancialRecord(
        barbershop_id=current_user.barbershop_id,
        type="commission_payout",
        category="commission",
        description=description,
        amount=float(amount),
        payment_method=payment_method,
        barber_id=barber.id,
        date=datetime.now()
    )
    db.add(fin)
    db.commit()
    return RedirectResponse(url="/finances", status_code=status.HTTP_302_FOUND)
