import pytest
import stripe
from unittest.mock import patch
from sqlalchemy import insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from app.core.database import engine
from app.models import (
    UserModel,
    MovieModel,
    CertificationModel,
    DirectorModel,
    StarModel,
    GenreModel,
    OrdersModel,
    OrderItemModel, PaymentModel
)
from app.models.accounts import UserGroupEnum, UserGroupModel
from app.models.order import StatusEnum as OrderStatusEnum
from app.models.payments import StatusEnum as PaymentStatusEnum
from app.security.password import hash_password
from app.tests.test_accounts import jwt_manager

pytestmark = pytest.mark.asyncio


class TestPayments():
    async def create_user_token(self):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email="user@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": user_id
            }
        )
        return user_id, {"Authorization": f"Bearer {jwt_access_token}"}

    async def create_admin_token(self):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=2
                ).returning(UserModel.id)
            )
            admin_id = result.scalar_one()
            jwt_access_token = jwt_manager.create_access_token(
                {
                    "user_id": admin_id
                }
            )
            return admin_id, {"Authorization": f"Bearer {jwt_access_token}"}

    async def create_order(self, user_id, status=OrderStatusEnum.PENDING):
        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=status
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            return order.id

    async def create_movie(self):
        async with AsyncSession(engine) as session:
            genre = GenreModel(name="Drama")
            star = StarModel(name="Actor")
            director = DirectorModel(name="Director")
            certification = CertificationModel(name="PG-13")

            movie = MovieModel(
                name="Test1 Film",
                year=2024,
                time=120,
                imdb=7.5,
                votes=1000,
                meta_score=70.0,
                gross=1000000.0,
                description="Example movie",
                price=10.5,
                certification=certification,
                genres=[genre],
                stars=[star],
                directors=[director],
            )

            session.add(movie)
            await session.flush()
            await session.commit()
            await session.refresh(movie)
            return movie.id

    @staticmethod
    async def mock_send_email(to_email: str, subject: str, body: str) -> None:
        print(f"Mock send email to {to_email} with subject {subject}")


class TestPaymentsCreate(TestPayments):
    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_success(self, mock_create, test_app):
        stripe.api_key = "dummy"
        mock_create.return_value = type("obj", (), {"id": "pi_test_123"})
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 201

    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_user_not_found(
            self,
            mock_create,
            test_app
    ):
        stripe.api_key = "dummy"
        mock_create.return_value = type("obj", (), {"id": "pi_test_123"})
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

            await session.execute(
                delete(UserModel).where(UserModel.id == user_id)
            )
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "User not found."}

    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_order_not_found(
            self,
            mock_create,
            test_app
    ):
        stripe.api_key = "dummy"
        mock_create.return_value = type("obj", (), {"id": "pi_test_123"})
        user_id, headers = await self.create_user_token()
        order_id = 9999
        await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}

    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_payment_already_paid(
            self,
            mock_create,
            test_app
    ):
        stripe.api_key = "dummy"
        mock_create.return_value = type("obj", (), {"id": "pi_test_123"})
        user_id, headers = await self.create_user_token()

        order_id = await self.create_order(
            user_id,
            status=OrderStatusEnum.PAID
        )
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Payment is already paid"}

    async def test_create_payment_stripe_not_configured(self, test_app):
        stripe.api_key = None
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Payment service is not configured. Please try later."
        }

    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_stripe_invalid_method(
            self,
            mock_create,
            test_app
    ):
        stripe.api_key = "dummy"
        mock_create.side_effect = stripe.InvalidRequestError(
            "Invalid payment",
            param=None
        )
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Payment method not available. "
                      "Try a different payment method."
        }

    @patch("app.routes.payments.stripe.PaymentIntent.create")
    async def test_create_payment_process_error(self, mock_create, test_app):
        stripe.api_key = "dummy"
        mock_create.side_effect = stripe.StripeError("Payment error")
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order_item = OrderItemModel(
                order_id=order_id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/",
                json={
                    "order_id": order_id,
                },
                headers=headers,
            )

        assert response.status_code == 502
        assert response.json() == {
            "detail": "Payment processing error. Please try again later."
        }


class TestPaymentsCreateWebhook(TestPayments):
    @patch("app.routes.payments.stripe.Webhook.construct_event")
    async def test_create_payment_webhook_success(
            self,
            mock_event,
            monkeypatch,
            test_app
    ):
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)

        mock_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123"}}
        }
        async with AsyncSession(engine) as session:
            payment = PaymentModel(
                user_id=user_id,
                order_id=order_id,
                amount=100,
                external_payment_id="pi_test_123",
                status=PaymentStatusEnum.CANCELED
            )
            session.add(payment)
            await session.commit()

        monkeypatch.setattr(
            "app.core.notifications.emails.EmailSender.send_success_payment",
            TestPayments.mock_send_email
        )
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/webhook",
                content=b"{}",
                headers={"stripe-signature": "dummy"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

    @patch("app.routes.payments.stripe.Webhook.construct_event")
    async def test_create_payment_webhook_invalid_payload(
            self,
            mock_event,
            test_app
    ):
        mock_event.side_effect = ValueError("Invalid payload")

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/webhook",
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid payload"}

    @patch("app.routes.payments.stripe.Webhook.construct_event")
    async def test_create_payment_webhook_invalid_signature(
            self,
            mock_event,
            test_app
    ):
        mock_event.side_effect = stripe.SignatureVerificationError(
            "Invalid signature",
            sig_header="dummy"
        )

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/payment/webhook",
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid signature"}


class TestPaymentGet(TestPayments):
    async def test_payment_get_success(self, test_app):
        user_id, headers = await self.create_user_token()
        order_id = await self.create_order(user_id)
        async with AsyncSession(engine) as session:
            payment = PaymentModel(
                user_id=user_id,
                order_id=order_id,
                amount=100,
            )
            session.add(payment)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/payment/", headers=headers)

        assert response.status_code == 200

    async def test_payment_get_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/payment/", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "No payments found"}


class TestPaymentGetAdmin(TestPayments):
    async def test_payment_get_admin_success(self, test_app):
        admin_id, headers_admin = await self.create_admin_token()
        user_id, headers_user = await self.create_user_token()
        order_id = await self.create_order(user_id)
        async with AsyncSession(engine) as session:
            payment = PaymentModel(
                user_id=user_id,
                order_id=order_id,
                amount=100,
            )
            session.add(payment)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/payment/admin/",
                headers=headers_admin
            )

        assert response.status_code == 200

    async def test_payment_get_admin_not_found(self, test_app):
        admin_id, headers = await self.create_admin_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/payment/admin/",
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "No payments found"}
