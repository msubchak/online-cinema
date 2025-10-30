import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from app.core.database import engine
from app.models import (
    CartModel,
    UserModel,
    MovieModel,
    CertificationModel,
    DirectorModel,
    StarModel,
    GenreModel,
    CartItemModel,
    OrdersModel,
    OrderItemModel
)
from app.models.accounts import UserGroupEnum, UserGroupModel
from app.models.order import StatusEnum
from app.security.password import hash_password
from app.tests.test_accounts import jwt_manager

pytestmark = pytest.mark.asyncio


class TestOrder():
    async def create_user_token(self):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email="moder@example.com",
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

    async def create_cart(self, user_id):
        async with AsyncSession(engine) as session:
            cart = CartModel(user_id=user_id)
            session.add(cart)
            await session.commit()
            await session.refresh(cart)
            return cart.id

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

    async def create_admin_token(self):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            result = await conn.execute(
                insert(UserModel).values(
                    email="moder@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=2
                ).returning(UserModel.id)
            )
            admin_id = result.scalar_one()
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": admin_id
            }
        )
        return admin_id, {"Authorization": f"Bearer {jwt_access_token}"}


class TestOrderCreate(TestOrder):
    async def test_create_order_success(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 201

    async def test_create_order_cart_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "Cart is empty or not found"}

    async def test_create_order_cart_empty(self, test_app):
        user_id, headers = await self.create_user_token()
        await self.create_cart(user_id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "Cart is empty or not found"}

    async def test_create_order_movie_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = 9999

        async with AsyncSession(engine) as session:
            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_create_order_movie_purchased(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PAID,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 400
        assert "detail" in response.json()

    async def test_create_order_movie_pending(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PENDING,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/order/", headers=headers)

        assert response.status_code == 400
        assert "detail" in response.json()


class TestOrderPay(TestOrder):
    async def test_order_pay_success(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PENDING,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/pay",
                headers=headers
            )

        assert response.status_code == 200
        assert "message" in response.json()

    async def test_order_pay_order_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        order_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/pay",
                headers=headers
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_order_pay_order_status_paid(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PAID,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/pay",
                headers=headers
            )

        assert response.status_code == 400
        assert "detail" in response.json()


class TestOrderCancel(TestOrder):
    async def test_order_cancel_success(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PENDING,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/cancel",
                headers=headers
            )

        assert response.status_code == 200
        assert "detail" in response.json()

    async def test_order_cancel_order_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        order_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/cancel",
                headers=headers
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_order_cancel_order_status_canceled(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.CANCELED,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/cancel",
                headers=headers
            )

        assert response.status_code == 400
        assert "detail" in response.json()

    async def test_order_cancel_order_status_paid(self, test_app):
        user_id, headers = await self.create_user_token()
        cart_id = await self.create_cart(user_id)
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=user_id,
                status=StatusEnum.PAID,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            order_id = order.id

            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie_id,
                price_at_order=10.5,
            )
            session.add(order_item)
            await session.commit()

            cart_item = CartItemModel(cart_id=cart_id, movie_id=movie_id)
            session.add(cart_item)
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/order/{order_id}/cancel",
                headers=headers
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Paid orders cannot be canceled directly"}


class TestOrderAdminGet(TestOrder):
    async def test_order_get_for_admin_success(self, test_app):
        admin_id, headers = await self.create_admin_token()

        async with AsyncSession(engine) as session:
            order = OrdersModel(
                user_id=admin_id,
                status=StatusEnum.PAID,
                total_amount=10.5,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/order/admin/", headers=headers)

        assert response.status_code == 200

    async def test_order_get_for_admin_not_found(self, test_app):
        admin_id, headers = await self.create_admin_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/order/admin/", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "No orders found matching the specified filters."}
