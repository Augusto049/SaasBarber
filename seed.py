from datetime import datetime, timedelta
from app.database import SessionLocal, engine, Base
from app.models import (
    Barbershop, User, Service, Barber, Product, SubscriptionPlan, Subscription,
    Appointment, FinancialRecord, ProductSale
)
from app.auth import hash_password

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Verifica se já existe barbearia
    existing = db.query(Barbershop).filter(Barbershop.slug == "dom-augusto").first()
    if existing:
        print("Banco de dados já possui dados iniciais.")
        db.close()
        return

    print("Populando banco de dados com dados realistas da Barbearia...")

    # 1. Barbearia
    barbershop = Barbershop(
        name="Barbearia Dom Augusto",
        slug="dom-augusto",
        phone="(11) 98765-4321",
        address="Av. Paulista, 1000 - Bela Vista, São Paulo - SP",
        description="Especialistas em cortes modernos, fade clássico, toalha quente e barba alinhada.",
        logo_url="/static/img/dom-augusto-logo.svg",
        banner_url="/static/img/hero-banner.svg",
        mercado_pago_access_token="", # Vazio para utilizar simulador automático ou preencher com token real
        mercado_pago_public_key=""
    )
    db.add(barbershop)
    db.flush()

    # 2. Usuário Administrador
    admin = User(
        email="admin@barbearia.com",
        hashed_password=hash_password("123456"),
        full_name="Augusto Barbeiro (Dono)",
        role="admin",
        barbershop_id=barbershop.id
    )
    db.add(admin)

    # 3. Barbeiros da Equipe
    barber1 = Barber(
        barbershop_id=barbershop.id,
        name="Lucas Navalha de Ouro",
        phone="(11) 98111-1111",
        email="lucas@barbearia.com",
        avatar_url="/static/img/avatar-lucas.svg",
        commission_percent=50.0,
        product_commission_percent=10.0
    )
    barber2 = Barber(
        barbershop_id=barbershop.id,
        name="Rafael Fade Master",
        phone="(11) 98222-2222",
        email="rafael@barbearia.com",
        avatar_url="/static/img/avatar-rafael.svg",
        commission_percent=50.0,
        product_commission_percent=10.0
    )
    barber3 = Barber(
        barbershop_id=barbershop.id,
        name="Matheus Vintage",
        phone="(11) 98333-3333",
        email="matheus@barbearia.com",
        avatar_url="/static/img/avatar-matheus.svg",
        commission_percent=50.0,
        product_commission_percent=10.0
    )
    db.add_all([barber1, barber2, barber3])
    db.flush()

    # 4. Serviços & Preços
    s1 = Service(barbershop_id=barbershop.id, name="Corte Degradê / Fade", price=45.0, duration_minutes=35, description="Corte moderno com acabamento na navalha e lavagem.")
    s2 = Service(barbershop_id=barbershop.id, name="Barba Terapia com Toalha Quente", price=35.0, duration_minutes=30, description="Alinhamento com navalhete, óleo hidratante e toalha quente relaxante.")
    s3 = Service(barbershop_id=barbershop.id, name="Sobrancelha na Navalha", price=15.0, duration_minutes=15, description="Desenho e limpeza precisa com navalhete descartável.")
    s4 = Service(barbershop_id=barbershop.id, name="Combo Cabelo + Barba Completo", price=75.0, duration_minutes=60, description="Nosso pacote completo com corte, barba, lavagem e finalização premium.")
    s5 = Service(barbershop_id=barbershop.id, name="Nevou / Platinado", price=120.0, duration_minutes=90, description="Descoloração global e matização com produtos anti-quebra.")
    db.add_all([s1, s2, s3, s4, s5])
    db.flush()

    # 5. Produtos em Estoque
    p1 = Product(barbershop_id=barbershop.id, name="Pomada Matte Efeito Seco 120g", cost_price=14.0, sale_price=38.0, stock_quantity=18, description="Fixação alta e sem brilho.")
    p2 = Product(barbershop_id=barbershop.id, name="Óleo Hidratante de Barba 30ml", cost_price=12.0, sale_price=32.0, stock_quantity=12, description="Com óleos de argan e jojoba.")
    p3 = Product(barbershop_id=barbershop.id, name="Shampoo Fortalecedor Mentolado 250ml", cost_price=16.0, sale_price=42.0, stock_quantity=7, description="Refrescante e anti-oleosidade.")
    p4 = Product(barbershop_id=barbershop.id, name="Cerveja Artesanal IPA 500ml", cost_price=7.0, sale_price=16.0, stock_quantity=24, description="Cerveja bem gelada para o cliente.")
    db.add_all([p1, p2, p3, p4])
    db.flush()

    # 6. Planos de Assinatura (Clube estilo Netflix / Amazon)
    plan1 = SubscriptionPlan(
        barbershop_id=barbershop.id,
        name="Clube VIP Cortes Ilimitados",
        price=89.0,
        billing_period="monthly",
        included_cuts_per_month=999,
        included_services_text="Cortes de cabelo ilimitados no mês + 1 Cerveja ou água por visita",
        description="Pague uma única vez no mês e venha manter o corte sempre perfeito."
    )
    plan2 = SubscriptionPlan(
        barbershop_id=barbershop.id,
        name="Clube Black (Cabelo + Barba Ilimitados)",
        price=139.0,
        billing_period="monthly",
        included_cuts_per_month=999,
        included_services_text="Cortes de cabelo e barba ilimitados + 10% off em qualquer produto",
        description="Acesso livre a corte e barba o mês inteiro."
    )
    db.add_all([plan1, plan2])
    db.flush()

    # 7. Assinantes Ativos
    sub1 = Subscription(
        barbershop_id=barbershop.id,
        plan_id=plan1.id,
        customer_name="Carlos Eduardo Silveira",
        customer_email="carlos.silveira@email.com",
        customer_phone="(11) 97777-1111",
        status="active",
        start_date=datetime.utcnow() - timedelta(days=12),
        next_billing_date=datetime.utcnow() + timedelta(days=18),
        cuts_used_this_month=2
    )
    sub2 = Subscription(
        barbershop_id=barbershop.id,
        plan_id=plan2.id,
        customer_name="Bruno Henrique Alves",
        customer_email="bruno.alves@email.com",
        customer_phone="(11) 97777-2222",
        status="active",
        start_date=datetime.utcnow() - timedelta(days=5),
        next_billing_date=datetime.utcnow() + timedelta(days=25),
        cuts_used_this_month=1
    )
    db.add_all([sub1, sub2])

    # 8. Agendamentos de Exemplo (Hoje)
    now = datetime.now()
    apt1 = Appointment(
        barbershop_id=barbershop.id,
        barber_id=barber1.id,
        service_id=s1.id,
        customer_name="Thiago Menezes",
        customer_phone="(11) 98888-1111",
        customer_email="thiago@email.com",
        date_time=now.replace(hour=10, minute=0, second=0),
        status="completed",
        is_paid_in_advance=True,
        payment_status="approved",
        payment_method="mp_pix",
        total_price=s1.price,
        barber_commission_amount=round(s1.price * (barber1.commission_percent / 100.0), 2),
        notes="Pagamento antecipado via Mercado Pago PIX"
    )

    apt2 = Appointment(
        barbershop_id=barbershop.id,
        barber_id=barber2.id,
        service_id=s4.id,
        customer_name="Carlos Eduardo Silveira",
        customer_phone="(11) 97777-1111",
        customer_email="carlos.silveira@email.com",
        date_time=now.replace(hour=14, minute=30, second=0),
        status="confirmed",
        is_paid_in_advance=False,
        payment_status="subscription",
        payment_method="subscription",
        total_price=0.0,
        barber_commission_amount=20.0,
        notes="Cliente do Clube VIP"
    )

    apt3 = Appointment(
        barbershop_id=barbershop.id,
        barber_id=barber3.id,
        service_id=s2.id,
        customer_name="Guilherme Rocha",
        customer_phone="(11) 98888-3333",
        customer_email="guilherme@email.com",
        date_time=now.replace(hour=16, minute=0, second=0),
        status="confirmed",
        is_paid_in_advance=False,
        payment_status="pending",
        payment_method="in_person",
        total_price=s2.price,
        barber_commission_amount=round(s2.price * (barber3.commission_percent / 100.0), 2)
    )
    db.add_all([apt1, apt2, apt3])

    # 9. Registros Financeiros (Receitas e Despesas)
    fin1 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="income",
        category="service",
        description="Atendimento: Corte Degradê (Thiago Menezes)",
        amount=45.0,
        payment_method="mercado_pago",
        barber_id=barber1.id,
        date=now.replace(hour=10, minute=30)
    )
    fin2 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="income",
        category="subscription",
        description="Assinatura Mensal Clube VIP (Carlos Eduardo)",
        amount=89.0,
        payment_method="mercado_pago",
        date=now - timedelta(days=12)
    )
    fin3 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="income",
        category="subscription",
        description="Assinatura Mensal Clube Black (Bruno Henrique)",
        amount=139.0,
        payment_method="mercado_pago",
        date=now - timedelta(days=5)
    )
    fin4 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="expense",
        category="rent",
        description="Aluguel do Ponto Comercial Barbearia",
        amount=1200.0,
        payment_method="pix",
        date=now - timedelta(days=6)
    )
    fin5 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="expense",
        category="supplies",
        description="Compra de Lâminas descartáveis e toalhas",
        amount=180.0,
        payment_method="pix",
        date=now - timedelta(days=3)
    )
    fin6 = FinancialRecord(
        barbershop_id=barbershop.id,
        type="commission_payout",
        category="commission",
        description="Repasse Semanal de Comissões - Lucas Navalha",
        amount=350.0,
        payment_method="pix",
        barber_id=barber1.id,
        date=now - timedelta(days=2)
    )
    db.add_all([fin1, fin2, fin3, fin4, fin5, fin6])

    db.commit()
    db.close()
    print("Banco de dados populado com sucesso!")

if __name__ == "__main__":
    seed_database()
