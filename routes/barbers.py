from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Barber, Appointment, FinancialRecord
from app.auth import get_current_user

router = APIRouter(prefix="/barbers", tags=["barbers"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_barbers(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    barbers = db.query(Barber).filter(
        Barber.barbershop_id == barbershop.id
    ).order_by(Barber.name.asc()).all()

    # Calcular comissões pendentes por barbeiro
    barbers_data = []
    for barber in barbers:
        total_earned = db.query(func.coalesce(func.sum(Appointment.barber_commission_amount), 0.0)).filter(
            Appointment.barber_id == barber.id,
            Appointment.status == "completed"
        ).scalar() or 0.0

        total_paid = db.query(func.coalesce(func.sum(FinancialRecord.amount), 0.0)).filter(
            FinancialRecord.barber_id == barber.id,
            FinancialRecord.type == "commission_payout"
        ).scalar() or 0.0

        balance = max(0.0, total_earned - total_paid)
        barbers_data.append({
            "barber": barber,
            "total_earned": total_earned,
            "total_paid": total_paid,
            "balance": balance
        })

    return templates.TemplateResponse(
        request=request,
        name="barbers/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "barbers_data": barbers_data
        }
    )

@router.post("/new")
async def create_barber(
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    commission_percent: float = Form(50.0),
    product_commission_percent: float = Form(10.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barber = Barber(
        barbershop_id=current_user.barbershop_id,
        name=name.strip(),
        phone=phone.strip(),
        email=email.strip(),
        commission_percent=float(commission_percent),
        product_commission_percent=float(product_commission_percent)
    )
    db.add(barber)
    db.commit()
    return RedirectResponse(url="/barbers", status_code=status.HTTP_302_FOUND)

@router.post("/{barber_id}/edit")
async def edit_barber(
    barber_id: int,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    commission_percent: float = Form(...),
    product_commission_percent: float = Form(...),
    is_active: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barber = db.query(Barber).filter(
        Barber.id == barber_id,
        Barber.barbershop_id == current_user.barbershop_id
    ).first()
    if not barber:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")

    barber.name = name.strip()
    barber.phone = phone.strip()
    barber.email = email.strip()
    barber.commission_percent = float(commission_percent)
    barber.product_commission_percent = float(product_commission_percent)
    barber.is_active = is_active
    db.commit()

    return RedirectResponse(url="/barbers", status_code=status.HTTP_302_FOUND)

@router.post("/{barber_id}/delete")
async def delete_barber(
    barber_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barber = db.query(Barber).filter(
        Barber.id == barber_id,
        Barber.barbershop_id == current_user.barbershop_id
    ).first()
    if barber:
        db.delete(barber)
        db.commit()
    return RedirectResponse(url="/barbers", status_code=status.HTTP_302_FOUND)
