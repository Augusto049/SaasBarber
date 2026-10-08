from fastapi import APIRouter, Depends, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Review
from app.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["reviews"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_reviews(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop

    reviews = db.query(Review).filter(
        Review.barbershop_id == barbershop.id
    ).order_by(Review.created_at.desc()).all()

    # Média de estrelas
    avg_rating = db.query(func.coalesce(func.avg(Review.rating), 5.0)).filter(
        Review.barbershop_id == barbershop.id,
        Review.is_approved == True
    ).scalar() or 5.0

    total_reviews = len(reviews)
    five_stars = sum(1 for r in reviews if r.rating == 5)

    return templates.TemplateResponse(
        request=request,
        name="reviews/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "reviews": reviews,
            "avg_rating": round(float(avg_rating), 1),
            "total_reviews": total_reviews,
            "five_stars": five_stars
        }
    )

@router.post("/{review_id}/toggle")
async def toggle_review_approval(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.barbershop_id == current_user.barbershop_id
    ).first()
    if review:
        review.is_approved = not review.is_approved
        db.commit()
    return RedirectResponse(url="/reviews", status_code=status.HTTP_302_FOUND)

@router.post("/{review_id}/delete")
async def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.barbershop_id == current_user.barbershop_id
    ).first()
    if review:
        db.delete(review)
        db.commit()
    return RedirectResponse(url="/reviews", status_code=status.HTTP_302_FOUND)
