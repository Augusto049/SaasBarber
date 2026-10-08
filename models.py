# app/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Time, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Barbershop(Base):
    __tablename__ = "barbershops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    banner_url = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    # Credenciais isoladas do Mercado Pago para cada Barbearia
    mercado_pago_access_token = Column(String(255), nullable=True)
    mercado_pago_public_key = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    users = relationship("User", back_populates="barbershop", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="barbershop", cascade="all, delete-orphan")
    barbers = relationship("Barber", back_populates="barbershop", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="barbershop", cascade="all, delete-orphan")
    subscription_plans = relationship("SubscriptionPlan", back_populates="barbershop", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="barbershop", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="barbershop", cascade="all, delete-orphan")
    financial_records = relationship("FinancialRecord", back_populates="barbershop", cascade="all, delete-orphan")
    product_sales = relationship("ProductSale", back_populates="barbershop", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="barbershop", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="barbershop", cascade="all, delete-orphan")
    business_hours = relationship("BusinessHour", back_populates="barbershop", cascade="all, delete-orphan")


class BusinessHour(Base):
    __tablename__ = "business_hours"
    __table_args__ = (UniqueConstraint("barbershop_id", "weekday", name="uq_business_hours_shop_weekday"),)

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False)
    period_1_start = Column(Time, nullable=True)
    period_1_end = Column(Time, nullable=True)
    period_2_start = Column(Time, nullable=True)
    period_2_end = Column(Time, nullable=True)

    barbershop = relationship("Barbershop", back_populates="business_hours")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default="admin")  # 'admin', 'barber'
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")


class Barber(Base):
    __tablename__ = "barbers"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    commission_percent = Column(Float, default=50.0)  # ex: 50% em serviços
    product_commission_percent = Column(Float, default=10.0)  # ex: 10% em produtos
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="barbers")
    appointments = relationship("Appointment", back_populates="barber")
    sales = relationship("ProductSale", back_populates="barber")
    financial_records = relationship("FinancialRecord", back_populates="barber")
    reviews = relationship("Review", back_populates="barber")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False, default=35.0)
    duration_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    cost_price = Column(Float, default=0.0)
    sale_price = Column(Float, nullable=False, default=30.0)
    stock_quantity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="products")
    sales = relationship("ProductSale", back_populates="product")


class ProductSale(Base):
    __tablename__ = "product_sales"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    barber_id = Column(Integer, ForeignKey("barbers.id"), nullable=True)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    barber_commission_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="product_sales")
    product = relationship("Product", back_populates="sales")
    barber = relationship("Barber", back_populates="sales")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False, default=89.0)
    billing_period = Column(String(20), default="monthly")
    included_cuts_per_month = Column(Integer, default=999)
    included_services_text = Column(String(255), default="Cortes de cabelo ilimitados no mês")
    mp_preapproval_plan_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="subscription_plans")
    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(150), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    status = Column(String(20), default="active")
    start_date = Column(DateTime, default=datetime.utcnow)
    next_billing_date = Column(DateTime, nullable=True)
    mp_preapproval_id = Column(String(100), nullable=True)
    cuts_used_this_month = Column(Integer, default=0)

    barbershop = relationship("Barbershop", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    barber_id = Column(Integer, ForeignKey("barbers.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(150), nullable=True)
    
    date_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="scheduled")
    
    # Pagamentos e Antecipação
    is_paid_in_advance = Column(Boolean, default=False)
    payment_status = Column(String(30), default="pending")
    payment_method = Column(String(40), default="in_person")
    
    total_price = Column(Float, nullable=False, default=0.0)
    barber_commission_amount = Column(Float, default=0.0)
    
    # Mercado Pago Tracking
    mp_preference_id = Column(String(150), nullable=True)
    mp_payment_id = Column(String(100), nullable=True)
    mp_init_point = Column(String(500), nullable=True)
    
    # Notificações e Lembretes
    reminder_sent = Column(Boolean, default=False)
    review_requested = Column(Boolean, default=False)
    review_token = Column(String(64), unique=True, index=True, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="appointments")
    barber = relationship("Barber", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    review = relationship("Review", back_populates="appointment", uselist=False)


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    type = Column(String(20), nullable=False)  # 'income', 'expense', 'commission_payout'
    category = Column(String(40), nullable=False)  # 'service', 'product_sale', 'subscription', 'rent', etc.
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    
    barber_id = Column(Integer, ForeignKey("barbers.id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    payment_method = Column(String(40), default="cash")
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="financial_records")
    barber = relationship("Barber", back_populates="financial_records")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    barber_id = Column(Integer, ForeignKey("barbers.id"), nullable=True)
    
    customer_name = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=False, default=5)
    comment = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    barbershop = relationship("Barbershop", back_populates="reviews")
    barber = relationship("Barber", back_populates="reviews")
    appointment = relationship("Appointment", back_populates="review")


class AuditLog(Base):
    """Trilha de auditoria para ações administrativas, logins e eventos do webhook (Requisito LGPD)."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    barbershop_id = Column(Integer, ForeignKey("barbershops.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # Ex: 'LOGIN_SUCCESS', 'SECURITY_ALERT_INVALID_WEBHOOK'
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    barbershop = relationship("Barbershop", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")