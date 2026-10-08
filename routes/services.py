from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Service
from app.auth import get_current_user

router = APIRouter(prefix="/services", tags=["services"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_services(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    show_archived = request.query_params.get("show_archived") == "true"
    services = db.query(Service).filter(
        Service.barbershop_id == barbershop.id,
        Service.is_active.is_(not show_archived),
    ).order_by(Service.price.desc()).all()
    archived_count = db.query(Service).filter(
        Service.barbershop_id == barbershop.id,
        Service.is_active.is_(False),
    ).count()
    archived_notice = request.query_params.get("archived") == "true"

    return templates.TemplateResponse(
        request=request,
        name="services/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "services": services,
            "show_archived": show_archived,
            "archived_count": archived_count,
            "archived_notice": archived_notice,
        }
    )

@router.post("/new")
async def create_service(
    name: str = Form(...),
    price: float = Form(...),
    duration_minutes: int = Form(30),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = Service(
        barbershop_id=current_user.barbershop_id,
        name=name.strip(),
        price=float(price),
        duration_minutes=int(duration_minutes),
        description=description.strip()
    )
    db.add(service)
    db.commit()
    return RedirectResponse(url="/services", status_code=status.HTTP_302_FOUND)

@router.post("/{service_id}/edit")
async def edit_service(
    service_id: int,
    name: str = Form(...),
    price: float = Form(...),
    duration_minutes: int = Form(...),
    description: str = Form(""),
    is_active: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.barbershop_id == current_user.barbershop_id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")

    service.name = name.strip()
    service.price = float(price)
    service.duration_minutes = int(duration_minutes)
    service.description = description.strip()
    service.is_active = is_active
    db.commit()

    return RedirectResponse(url="/services", status_code=status.HTTP_302_FOUND)

@router.post("/{service_id}/delete")
async def delete_service(
    service_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.barbershop_id == current_user.barbershop_id
    ).first()
    if service:
        if service.appointments:
            service.is_active = False
            db.commit()
            return RedirectResponse(
                url="/services?archived=true",
                status_code=status.HTTP_302_FOUND,
            )

        db.delete(service)
        db.commit()
    return RedirectResponse(url="/services", status_code=status.HTTP_302_FOUND)
