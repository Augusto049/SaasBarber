from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Product, ProductSale, Barber, FinancialRecord
from app.auth import get_current_user

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def list_products(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barbershop = current_user.barbershop
    products = db.query(Product).filter(
        Product.barbershop_id == barbershop.id
    ).order_by(Product.name.asc()).all()

    barbers = db.query(Barber).filter(
        Barber.barbershop_id == barbershop.id,
        Barber.is_active == True
    ).order_by(Barber.name.asc()).all()

    recent_sales = db.query(ProductSale).filter(
        ProductSale.barbershop_id == barbershop.id
    ).order_by(ProductSale.created_at.desc()).limit(10).all()
    active_products = [product for product in products if product.is_active]
    archived_notice = request.query_params.get("archived") == "true"

    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={
            "user": current_user,
            "barbershop": barbershop,
            "products": products,
            "active_products": active_products,
            "archived_notice": archived_notice,
            "barbers": barbers,
            "recent_sales": recent_sales
        }
    )

@router.post("/new")
async def create_product(
    name: str = Form(...),
    cost_price: float = Form(0.0),
    sale_price: float = Form(...),
    stock_quantity: int = Form(0),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = Product(
        barbershop_id=current_user.barbershop_id,
        name=name.strip(),
        cost_price=float(cost_price),
        sale_price=float(sale_price),
        stock_quantity=int(stock_quantity),
        description=description.strip()
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/products", status_code=status.HTTP_302_FOUND)

@router.post("/{product_id}/edit")
async def edit_product(
    product_id: int,
    name: str = Form(...),
    cost_price: float = Form(0.0),
    sale_price: float = Form(...),
    stock_quantity: int = Form(0),
    description: str = Form(""),
    is_active: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.barbershop_id == current_user.barbershop_id
    ).first()
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    product.name = name.strip()
    product.cost_price = float(cost_price)
    product.sale_price = float(sale_price)
    product.stock_quantity = int(stock_quantity)
    product.description = description.strip()
    product.is_active = is_active
    db.commit()

    return RedirectResponse(url="/products", status_code=status.HTTP_302_FOUND)

@router.post("/sell")
async def sell_product(
    product_id: int = Form(...),
    quantity: int = Form(1),
    barber_id: int = Form(0),
    payment_method: str = Form("cash"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.barbershop_id == current_user.barbershop_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    quantity = max(1, int(quantity))
    total_price = float(product.sale_price * quantity)

    # Comissão para o barbeiro se selecionado
    barber_commission = 0.0
    actual_barber_id = None
    if barber_id > 0:
        barber = db.query(Barber).filter(
            Barber.id == barber_id,
            Barber.barbershop_id == current_user.barbershop_id
        ).first()
        if barber:
            actual_barber_id = barber.id
            barber_commission = round(total_price * (barber.product_commission_percent / 100.0), 2)

    # Baixa no estoque
    product.stock_quantity = max(0, product.stock_quantity - quantity)

    # Registrar venda
    sale = ProductSale(
        barbershop_id=current_user.barbershop_id,
        product_id=product.id,
        barber_id=actual_barber_id,
        quantity=quantity,
        unit_price=product.sale_price,
        total_price=total_price,
        barber_commission_amount=barber_commission
    )
    db.add(sale)

    # Registrar receita no financeiro
    fin = FinancialRecord(
        barbershop_id=current_user.barbershop_id,
        type="income",
        category="product_sale",
        description=f"Venda de {quantity}x {product.name}",
        amount=total_price,
        payment_method=payment_method,
        barber_id=actual_barber_id
    )
    db.add(fin)
    db.commit()

    return RedirectResponse(url="/products", status_code=status.HTTP_302_FOUND)

@router.post("/{product_id}/delete")
async def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.barbershop_id == current_user.barbershop_id
    ).first()
    if product:
        if product.sales:
            product.is_active = False
            db.commit()
            return RedirectResponse(
                url="/products?archived=true",
                status_code=status.HTTP_302_FOUND,
            )

        db.delete(product)
        db.commit()
    return RedirectResponse(url="/products", status_code=status.HTTP_302_FOUND)
