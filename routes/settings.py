from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import time
from app.database import get_db
from app.models import User, Barbershop, BusinessHour
from app.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="app/templates")
WEEKDAYS = [
    (0, "Segunda-feira"),
    (1, "Terça-feira"),
    (2, "Quarta-feira"),
    (3, "Quinta-feira"),
    (4, "Sexta-feira"),
    (5, "Sábado"),
    (6, "Domingo"),
]


def _settings_context(current_user, db, success_msg=None, error_msg=None, schedule_rows=None):
    if schedule_rows is None:
        existing = {
            row.weekday: row
            for row in db.query(BusinessHour).filter(
                BusinessHour.barbershop_id == current_user.barbershop_id
            ).all()
        }
        schedule_rows = [
            {
                "weekday": weekday,
                "label": label,
                "period_1_start": existing[weekday].period_1_start.strftime("%H:%M") if weekday in existing and existing[weekday].period_1_start else "",
                "period_1_end": existing[weekday].period_1_end.strftime("%H:%M") if weekday in existing and existing[weekday].period_1_end else "",
                "period_2_start": existing[weekday].period_2_start.strftime("%H:%M") if weekday in existing and existing[weekday].period_2_start else "",
                "period_2_end": existing[weekday].period_2_end.strftime("%H:%M") if weekday in existing and existing[weekday].period_2_end else "",
            }
            for weekday, label in WEEKDAYS
        ]

    return {
        "user": current_user,
        "barbershop": current_user.barbershop,
        "schedule_rows": schedule_rows,
        "success_msg": success_msg,
        "error_msg": error_msg,
    }


def _parse_schedule_rows(schedule_rows):
    parsed_rows = []
    for row in schedule_rows:
        parsed = {"weekday": row["weekday"]}
        for period in (1, 2):
            start_value = row[f"period_{period}_start"]
            end_value = row[f"period_{period}_end"]
            if bool(start_value) != bool(end_value):
                return None, f"Informe início e fim do período {period} de {row['label']}, ou deixe ambos vazios."
            try:
                start_time = time.fromisoformat(start_value) if start_value else None
                end_time = time.fromisoformat(end_value) if end_value else None
            except ValueError:
                return None, f"O horário informado para {row['label']} é inválido."
            if start_time and start_time >= end_time:
                return None, f"O período {period} de {row['label']} precisa terminar depois do início."
            parsed[f"period_{period}_start"] = start_time
            parsed[f"period_{period}_end"] = end_time

        if (parsed["period_1_end"] and parsed["period_2_start"]
                and parsed["period_2_start"] < parsed["period_1_end"]):
            return None, f"O segundo período de {row['label']} deve começar após o primeiro."
        parsed_rows.append(parsed)

    return parsed_rows, None

@router.get("", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    return templates.TemplateResponse(
        request=request,
        name="settings/index.html",
        context=_settings_context(current_user, db)
    )


@router.post("/business-hours")
async def update_business_hours(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    form = await request.form()
    schedule_rows = [
        {
            "weekday": weekday,
            "label": label,
            **{
                f"period_{period}_{boundary}": str(form.get(f"period_{period}_{boundary}_{weekday}", "")).strip()
                for period in (1, 2)
                for boundary in ("start", "end")
            },
        }
        for weekday, label in WEEKDAYS
    ]
    parsed_rows, error_msg = _parse_schedule_rows(schedule_rows)
    if error_msg:
        return templates.TemplateResponse(
            request=request,
            name="settings/index.html",
            context=_settings_context(
                current_user, db, error_msg=error_msg, schedule_rows=schedule_rows
            ),
            status_code=400,
        )

    existing = {
        row.weekday: row
        for row in db.query(BusinessHour).filter(
            BusinessHour.barbershop_id == current_user.barbershop_id
        ).all()
    }
    for values in parsed_rows:
        schedule = existing.get(values["weekday"])
        if schedule is None:
            schedule = BusinessHour(
                barbershop_id=current_user.barbershop_id,
                weekday=values["weekday"],
            )
            db.add(schedule)
        for field in (
            "period_1_start", "period_1_end", "period_2_start", "period_2_end"
        ):
            setattr(schedule, field, values[field])

    db.commit()
    return templates.TemplateResponse(
        request=request,
        name="settings/index.html",
        context=_settings_context(
            current_user, db,
            success_msg="Horários de funcionamento salvos com sucesso!",
            schedule_rows=schedule_rows,
        ),
    )

@router.post("/update")
async def update_barbershop(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    phone: str = Form(""),
    address: str = Form(""),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop

    # Valida se slug já está em uso por outra barbearia
    slug_clean = slug.strip().lower().replace(" ", "-")
    existing = db.query(Barbershop).filter(
        Barbershop.slug == slug_clean,
        Barbershop.id != barbershop.id
    ).first()

    if existing:
        return templates.TemplateResponse(
            request=request,
            name="settings/index.html",
            context=_settings_context(
                current_user, db,
                error_msg="Este link/slug já está sendo utilizado por outra barbearia."
            )
        )

    barbershop.name = name.strip()
    barbershop.slug = slug_clean
    barbershop.phone = phone.strip()
    barbershop.address = address.strip()
    barbershop.description = description.strip()
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="settings/index.html",
        context=_settings_context(
            current_user, db,
            success_msg="Dados da barbearia atualizados com sucesso!"
        )
    )

@router.post("/mercado-pago")
async def update_mercado_pago(
    request: Request,
    access_token: str = Form(""),
    public_key: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    barbershop.mercado_pago_access_token = access_token.strip()
    barbershop.mercado_pago_public_key = public_key.strip()
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="settings/index.html",
        context=_settings_context(
            current_user, db,
            success_msg="Credenciais do Mercado Pago salvas com sucesso! Seus pagamentos e assinaturas já estão conectados à sua conta bancária."
        )
    )
