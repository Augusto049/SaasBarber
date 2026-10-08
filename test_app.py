import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, SessionLocal
from app.models import Barbershop, User, Service, Barber, Appointment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

class TestBarberSaaS(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, follow_redirects=False)

    def test_01_public_barbershop_page(self):
        response = self.client.get("/b/dom-augusto")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Barbearia Dom Augusto", response.text)
        self.assertIn("Corte Degradê", response.text)
        self.assertIn("Clube de Assinatura", response.text)

    def test_02_login_and_dashboard(self):
        # Tentativa de acesso sem autenticação redireciona
        res = self.client.get("/dashboard")
        self.assertIn(res.status_code, [302, 307])

        # Login com credenciais válidas
        login_res = self.client.post("/login", data={
            "email": "admin@barbearia.com",
            "password": "123456"
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertIn("barber_session", login_res.cookies)

        # Acesso ao dashboard com o cookie
        dashboard_res = self.client.get("/dashboard", cookies=login_res.cookies)
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertIn("Faturamento", dashboard_res.text)

    def test_02b_api_login_json_success(self):
        login_res = self.client.post(
            "/api/login",
            json={"email": "admin@barbearia.com", "senha": "123456"}
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("barber_session", login_res.cookies)
        self.assertEqual(login_res.json().get("redirect"), "/dashboard")

    def test_03_services_management(self):
        login_res = self.client.post("/login", data={"email": "admin@barbearia.com", "password": "123456"})
        cookies = login_res.cookies

        # Listar serviços
        res = self.client.get("/services", cookies=cookies)
        self.assertEqual(res.status_code, 200)

        # Criar novo serviço com valor configurado pelo dono
        create_res = self.client.post("/services/new", data={
            "name": "Barba Lenhador com Hidratação",
            "price": "49.90",
            "duration_minutes": "35",
            "description": "Tratamento completo para barbas longas"
        }, cookies=cookies)
        self.assertEqual(create_res.status_code, 302)

        # Verificar se aparece na listagem
        res2 = self.client.get("/services", cookies=cookies)
        self.assertIn("Barba Lenhador", res2.text)

    def test_04_subscriptions_netflix_style(self):
        login_res = self.client.post("/login", data={"email": "admin@barbearia.com", "password": "123456"})
        cookies = login_res.cookies

        # Listar planos de assinatura
        res = self.client.get("/subscriptions", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Clube VIP Cortes Ilimitados", res.text)
        self.assertIn("89", res.text)

        # Criar novo plano de assinatura com preço configurado pelo dono
        new_plan_res = self.client.post("/subscriptions/plans/new", data={
            "name": "Clube Premium Barba & Cabelo",
            "price": "119.00",
            "included_cuts_per_month": "999",
            "included_services_text": "Cortes e Barbas Ilimitados + 1 Café Espresso",
            "description": "Ideal para quem cuida da aparência toda semana"
        }, cookies=cookies)
        self.assertEqual(new_plan_res.status_code, 302)

    def test_05_finances_and_cash_flow(self):
        login_res = self.client.post("/login", data={"email": "admin@barbearia.com", "password": "123456"})
        cookies = login_res.cookies

        res = self.client.get("/finances", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Entradas", res.text)
        self.assertIn("Despesas", res.text)

        # Registrar nova despesa
        expense_res = self.client.post("/finances/expense/new", data={
            "description": "Conta de Energia Elétrica",
            "amount": "230.50",
            "category": "utilities",
            "payment_method": "pix"
        }, cookies=cookies)
        self.assertEqual(expense_res.status_code, 302)

    def test_06_mercado_pago_public_booking_and_checkout(self):
        # Simula agendamento com antecipação online pelo cliente
        book_res = self.client.post("/b/dom-augusto/book", data={
            "service_id": 1,
            "barber_id": 1,
            "customer_name": "Marcos Teste",
            "customer_phone": "(11) 99999-1234",
            "customer_email": "marcos@teste.com",
            "date_str": "2026-10-15T14:00",
            "pay_online": "true"
        })
        # Redireciona para o checkout do Mercado Pago
        self.assertEqual(book_res.status_code, 302)
        location = book_res.headers.get("Location")
        self.assertIn("/checkout/", location)

    def test_06b_booking_sends_real_email_confirmation(self):
        with patch("app.services.email_service.EmailService.send_booking_confirmation") as mock_send:
            mock_send.return_value = True

            res = self.client.post("/b/dom-augusto/book", data={
                "service_id": 1,
                "barber_id": 1,
                "customer_name": "Marcos Teste",
                "customer_phone": "(11) 99999-1234",
                "customer_email": "marcos@teste.com",
                "date_str": "2026-10-15T14:00",
                "pay_online": "false"
            })

            self.assertIn(res.status_code, [200, 302])
            mock_send.assert_called_once()
            self.assertEqual(mock_send.call_args.kwargs["to_email"], "marcos@teste.com")

    def test_06c_one_hour_reminder_sends_email_once(self):
        from app.main import check_and_send_email_reminders

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()
        try:
            barbershop = Barbershop(name="Teste", slug="teste-lembrete")
            db.add(barbershop)
            db.flush()
            service = Service(barbershop_id=barbershop.id, name="Corte teste", price=35.0)
            barber = Barber(barbershop_id=barbershop.id, name="Profissional teste")
            db.add_all([service, barber])
            db.flush()
            appointment = Appointment(
                barbershop_id=barbershop.id,
                service_id=service.id,
                barber_id=barber.id,
                customer_name="Lembrete Teste",
                customer_phone="11999991234",
                customer_email="lembrete@teste.com",
                date_time=datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None) + timedelta(minutes=60),
                status="confirmed",
                total_price=service.price,
                reminder_sent=False,
            )
            db.add(appointment)
            db.commit()

            with patch("app.main.SessionLocal", TestSession), patch(
                "app.main.EmailService.send_booking_reminder", return_value=True
            ) as mock_send:
                check_and_send_email_reminders()

            db.refresh(appointment)
            self.assertTrue(appointment.reminder_sent)
            mock_send.assert_called_once()
            self.assertEqual(mock_send.call_args.kwargs["to_email"], "lembrete@teste.com")
        finally:
            db.close()
            test_engine.dispose()

    def test_06d_reminder_email_uses_requested_message(self):
        from app.services.email_service import EmailService

        with patch("app.services.email_service.EmailService.send_email", return_value=True) as mock_send:
            EmailService.send_booking_reminder(
                customer_name="Lucas",
                to_email="lucas@teste.com",
                service_name="Corte",
                time_str="14:00",
            )

        html = mock_send.call_args.args[2]
        self.assertIn("Olá <strong>Lucas</strong>, falta 1 hora para o seu atendimento!", html)

    def test_07_business_hours_accept_two_friday_periods(self):
        from app.routes.settings import WEEKDAYS, _parse_schedule_rows

        rows = [
            {
                "weekday": weekday,
                "label": label,
                "period_1_start": "",
                "period_1_end": "",
                "period_2_start": "",
                "period_2_end": "",
            }
            for weekday, label in WEEKDAYS
        ]
        friday = rows[4]
        friday.update({
            "period_1_start": "09:00",
            "period_1_end": "12:00",
            "period_2_start": "13:30",
            "period_2_end": "16:00",
        })

        parsed, error = _parse_schedule_rows(rows)

        self.assertIsNone(error)
        self.assertEqual(parsed[4]["period_1_start"].strftime("%H:%M"), "09:00")
        self.assertEqual(parsed[4]["period_1_end"].strftime("%H:%M"), "12:00")
        self.assertEqual(parsed[4]["period_2_start"].strftime("%H:%M"), "13:30")
        self.assertEqual(parsed[4]["period_2_end"].strftime("%H:%M"), "16:00")

    def test_08_business_hours_reject_overlapping_periods(self):
        from app.routes.settings import WEEKDAYS, _parse_schedule_rows

        rows = [
            {
                "weekday": weekday,
                "label": label,
                "period_1_start": "",
                "period_1_end": "",
                "period_2_start": "",
                "period_2_end": "",
            }
            for weekday, label in WEEKDAYS
        ]
        rows[4].update({
            "period_1_start": "09:00",
            "period_1_end": "12:00",
            "period_2_start": "11:30",
            "period_2_end": "16:00",
        })

        parsed, error = _parse_schedule_rows(rows)

        self.assertIsNone(parsed)
        self.assertIn("segundo período", error)

    def test_09_business_hours_control_public_booking(self):
        from app.auth import get_current_user
        from app.database import get_db
        from app.models import BusinessHour

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()
        previous_db_override = app.dependency_overrides.get(get_db)
        previous_user_override = app.dependency_overrides.get(get_current_user)

        try:
            barbershop = Barbershop(name="Teste Horários", slug="teste-horarios")
            db.add(barbershop)
            db.flush()
            user = User(
                email="dono@teste-horarios.com",
                hashed_password="unused",
                full_name="Dono Teste",
                barbershop_id=barbershop.id,
            )
            service = Service(
                barbershop_id=barbershop.id,
                name="Corte teste",
                price=35.0,
                duration_minutes=30,
            )
            barber = Barber(barbershop_id=barbershop.id, name="Profissional teste")
            db.add_all([user, service, barber])
            db.commit()

            def override_get_db():
                yield db

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[get_current_user] = lambda: user
            client = TestClient(app, follow_redirects=False)

            schedule_form = {}
            for weekday in range(7):
                for period in (1, 2):
                    schedule_form[f"period_{period}_start_{weekday}"] = ""
                    schedule_form[f"period_{period}_end_{weekday}"] = ""
            schedule_form.update({
                "period_1_start_4": "09:00",
                "period_1_end_4": "12:00",
                "period_2_start_4": "13:30",
                "period_2_end_4": "16:00",
            })

            save_response = client.post("/settings/business-hours", data=schedule_form)
            self.assertEqual(save_response.status_code, 200)
            self.assertEqual(db.query(BusinessHour).count(), 7)

            public_response = client.get("/b/teste-horarios")
            self.assertEqual(public_response.status_code, 200)
            self.assertIn('"5": [["09:00", "12:00"], ["13:30", "16:00"]]', public_response.text)

            days_until_friday = (4 - datetime.now().weekday()) % 7 or 7
            friday = (datetime.now() + timedelta(days=days_until_friday)).date().isoformat()
            booking_data = {
                "service_id": str(service.id),
                "barber_id": str(barber.id),
                "customer_name": "Cliente Teste",
                "customer_phone": "11999991234",
                "pay_online": "false",
            }
            with patch("app.routes.public.WhatsAppService.send_booking_confirmation"):
                outside_response = client.post(
                    "/b/teste-horarios/book",
                    data={**booking_data, "date_str": f"{friday}T12:00"},
                )
                inside_response = client.post(
                    "/b/teste-horarios/book",
                    data={**booking_data, "date_str": f"{friday}T11:30"},
                )

            self.assertEqual(outside_response.status_code, 400)
            self.assertEqual(inside_response.status_code, 302)
        finally:
            if previous_db_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_db_override
            if previous_user_override is None:
                app.dependency_overrides.pop(get_current_user, None)
            else:
                app.dependency_overrides[get_current_user] = previous_user_override
            db.close()
            test_engine.dispose()

    def test_10_service_delete_preserves_appointment_history(self):
        import asyncio
        from app.auth import get_current_user
        from app.database import get_db
        from app.routes.services import delete_service

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()
        previous_db_override = app.dependency_overrides.get(get_db)
        previous_user_override = app.dependency_overrides.get(get_current_user)
        try:
            barbershop = Barbershop(name="Teste Serviços", slug="teste-servicos-delete")
            db.add(barbershop)
            db.flush()
            user = User(
                email="dono@teste-servicos.com",
                hashed_password="unused",
                full_name="Dono Teste",
                barbershop_id=barbershop.id,
            )
            barber = Barber(barbershop_id=barbershop.id, name="Profissional teste")
            used_service = Service(
                barbershop_id=barbershop.id,
                name="Serviço vinculado",
                price=35.0,
            )
            unused_service = Service(
                barbershop_id=barbershop.id,
                name="Serviço sem uso",
                price=30.0,
            )
            db.add_all([user, barber, used_service, unused_service])
            db.flush()
            appointment = Appointment(
                barbershop_id=barbershop.id,
                barber_id=barber.id,
                service_id=used_service.id,
                customer_name="Cliente histórico",
                customer_phone="11999991234",
                date_time=datetime.now() + timedelta(days=1),
                total_price=used_service.price,
            )
            db.add(appointment)
            db.commit()

            archived_response = asyncio.run(
                delete_service(used_service.id, current_user=user, db=db)
            )
            db.refresh(used_service)
            self.assertEqual(archived_response.status_code, 302)
            self.assertFalse(used_service.is_active)
            self.assertEqual(appointment.service_id, used_service.id)

            def override_get_db():
                yield db

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[get_current_user] = lambda: user
            client = TestClient(app, follow_redirects=False)
            active_services_page = client.get("/services")
            archived_services_page = client.get("/services?show_archived=true")
            self.assertNotIn("Serviço vinculado", active_services_page.text)
            self.assertIn("Serviço vinculado", archived_services_page.text)

            deleted_response = asyncio.run(
                delete_service(unused_service.id, current_user=user, db=db)
            )
            self.assertEqual(deleted_response.status_code, 302)
            self.assertIsNone(db.get(Service, unused_service.id))
        finally:
            if previous_db_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_db_override
            if previous_user_override is None:
                app.dependency_overrides.pop(get_current_user, None)
            else:
                app.dependency_overrides[get_current_user] = previous_user_override
            db.close()
            test_engine.dispose()

    def test_11_product_delete_preserves_sales_history(self):
        import asyncio
        from app.models import Product, ProductSale
        from app.routes.products import delete_product

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()
        try:
            barbershop = Barbershop(name="Teste Produtos", slug="teste-produtos-delete")
            db.add(barbershop)
            db.flush()
            user = User(
                email="dono@teste-produtos.com",
                hashed_password="unused",
                full_name="Dono Teste",
                barbershop_id=barbershop.id,
            )
            sold_product = Product(
                barbershop_id=barbershop.id,
                name="Produto vendido",
                sale_price=35.0,
            )
            unused_product = Product(
                barbershop_id=barbershop.id,
                name="Produto sem venda",
                sale_price=30.0,
            )
            db.add_all([user, sold_product, unused_product])
            db.flush()
            sale = ProductSale(
                barbershop_id=barbershop.id,
                product_id=sold_product.id,
                quantity=1,
                unit_price=sold_product.sale_price,
                total_price=sold_product.sale_price,
            )
            db.add(sale)
            db.commit()

            archived_response = asyncio.run(
                delete_product(sold_product.id, current_user=user, db=db)
            )
            db.refresh(sold_product)
            self.assertEqual(archived_response.status_code, 302)
            self.assertFalse(sold_product.is_active)
            self.assertEqual(sale.product_id, sold_product.id)

            deleted_response = asyncio.run(
                delete_product(unused_product.id, current_user=user, db=db)
            )
            self.assertEqual(deleted_response.status_code, 302)
            self.assertIsNone(db.get(Product, unused_product.id))
        finally:
            db.close()
            test_engine.dispose()

    def test_12_scheduler_starts_and_registers_minute_job(self):
        from app.main import app

        with TestClient(app):
            scheduler = app.state.scheduler
            self.assertTrue(scheduler.running)
            self.assertEqual(len(scheduler.get_jobs()), 1)
            self.assertEqual(scheduler.get_job("email_appointment_reminders").trigger.interval.total_seconds(), 60)

    def test_13_subscription_plans_can_be_deleted_or_archived(self):
        import asyncio
        from app.models import Subscription, SubscriptionPlan
        from app.routes.subscriptions import delete_plan, edit_plan

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=test_engine)
        TestSession = sessionmaker(bind=test_engine)
        db = TestSession()
        try:
            barbershop = Barbershop(name="Teste Planos", slug="teste-planos-delete")
            db.add(barbershop)
            db.flush()
            user = User(
                email="dono@teste-planos.com",
                hashed_password="unused",
                full_name="Dono Teste",
                barbershop_id=barbershop.id,
            )
            plan_with_subscriber = SubscriptionPlan(
                barbershop_id=barbershop.id,
                name="Plano com assinante",
                price=89.0,
            )
            unused_plan = SubscriptionPlan(
                barbershop_id=barbershop.id,
                name="Plano sem assinante",
                price=59.0,
            )
            db.add_all([user, plan_with_subscriber, unused_plan])
            db.flush()
            subscriber = Subscription(
                barbershop_id=barbershop.id,
                plan_id=plan_with_subscriber.id,
                customer_name="Cliente Teste",
                customer_email="cliente@teste.com",
            )
            db.add(subscriber)
            db.commit()

            archived_response = asyncio.run(
                delete_plan(plan_with_subscriber.id, current_user=user, db=db)
            )
            db.refresh(plan_with_subscriber)
            self.assertEqual(archived_response.status_code, 302)
            self.assertFalse(plan_with_subscriber.is_active)
            self.assertEqual(subscriber.plan_id, plan_with_subscriber.id)

            edit_response = asyncio.run(edit_plan(
                plan_with_subscriber.id,
                name=plan_with_subscriber.name,
                price=plan_with_subscriber.price,
                included_cuts_per_month=plan_with_subscriber.included_cuts_per_month,
                included_services_text=plan_with_subscriber.included_services_text,
                description=plan_with_subscriber.description or "",
                is_active=True,
                current_user=user,
                db=db,
            ))
            db.refresh(plan_with_subscriber)
            self.assertEqual(edit_response.status_code, 302)
            self.assertTrue(plan_with_subscriber.is_active)

            deleted_response = asyncio.run(
                delete_plan(unused_plan.id, current_user=user, db=db)
            )
            self.assertEqual(deleted_response.status_code, 302)
            self.assertIsNone(db.get(SubscriptionPlan, unused_plan.id))
        finally:
            db.close()
            test_engine.dispose()

if __name__ == "__main__":
    unittest.main()
