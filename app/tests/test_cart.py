import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from app.core.database import engine
from app.models import CartModel, UserModel
from app.security.password import hash_password
from app.tests.test_accounts import jwt_manager

pytestmark = pytest.mark.asyncio


class TestCart():
    async def create_moderator_token(self):
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


class TestCartGet(TestCart):
    async def test_get_cart_success(self, test_app):
        user_id, headers = await self.create_moderator_token()
        await self.create_cart(user_id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("api/v1/cart/", headers=headers)

        assert response.status_code == 200

    async def test_get_cart_not_found(self, test_app):
        user_id, headers = await self.create_moderator_token()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("api/v1/cart/", headers=headers)

        assert response.status_code == 404
        assert "detail" in response.json()
