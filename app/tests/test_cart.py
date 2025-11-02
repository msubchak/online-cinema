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
from app.security.password import hash_password
from app.tests.test_accounts import jwt_manager

pytestmark = pytest.mark.asyncio


class TestCart():
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


class TestCartGet(TestCart):
    async def test_get_cart_success(self, test_app):
        user_id, headers = await self.create_user_token()
        await self.create_cart(user_id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/cart/", headers=headers)

        assert response.status_code == 200

    async def test_get_cart_not_found(self, test_app):
        user_id, headers = await self.create_user_token()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/cart/", headers=headers)

        assert response.status_code == 404
        assert "detail" in response.json()


class TestCartCreate(TestCart):
    async def test_create_cart_success(self, test_app):
        user_id, headers = await self.create_user_token()
        await self.create_cart(user_id)
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/cart/?movie_id={movie_id}",
                headers=headers
            )

        assert response.status_code == 201
        assert response.json() == {
            "detail": "Movie added to the cart successfully"
        }

    async def test_create_cart_movie_id_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        movie_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/cart/?movie_id={movie_id}",
                headers=headers
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_create_cart_movie_already_in_cart(self, test_app):
        user_id, headers = await self.create_user_token()
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            cart = CartModel(user_id=user_id)
            session.add(cart)
            await session.commit()
            await session.refresh(cart)

            cart_item = CartItemModel(
                cart_id=cart.id,
                movie_id=movie_id,
            )
            session.add(cart_item)
            await session.commit()
            await session.refresh(cart_item)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/cart/?movie_id={movie_id}",
                headers=headers
            )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "This movie is already present in your cart."
        }

    async def test_create_cart_movie_already_purchased(self, test_app):
        user_id, headers = await self.create_user_token()
        movie_id = await self.create_movie()

        async with AsyncSession(engine) as session:
            order = OrdersModel(user_id=user_id)
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

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/cart/?movie_id={movie_id}",
                headers=headers
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "You have already purchased this movie. "
                      "Repeat purchases are not allowed."
        }


class TestCartDelete(TestCart):
    async def test_delete_cart_success(self, test_app):
        user_id, headers = await self.create_user_token()
        await self.create_cart(user_id)
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            await client.post(
                f"/api/v1/cart/?movie_id={movie_id}",
                headers=headers
            )
            response = await client.delete(
                f"/api/v1/cart/{movie_id}",
                headers=headers
            )

        assert response.status_code == 204

    async def test_delete_cart_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/v1/cart/{movie_id}",
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Cart not found for the current user."
        }

    async def test_delete_cart_movie_not_found(self, test_app):
        user_id, headers = await self.create_user_token()
        await self.create_cart(user_id)
        movie_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/v1/cart/{movie_id}",
                headers=headers
            )

        assert response.status_code == 404
        assert "detail" in response.json()
