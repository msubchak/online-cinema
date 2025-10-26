import uuid
import pytest
import secrets
from app.core.config.email_utils import get_jwt_auth_manager, get_settings
from sqlalchemy import insert, select, delete

from app.models.accounts import UserModel, ActivationTokenModel, UserGroupModel, UserGroupEnum, RefreshTokenModel
from app.core.database import engine
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport

from app.security.password import hash_password
from app.security.token_manager import JWTAuthManager

pytestmark = pytest.mark.asyncio

settings = get_settings()
jwt_manager = JWTAuthManager(
    secret_key_access=settings.SECRET_KEY_ACCESS,
    secret_key_refresh=settings.SECRET_KEY_REFRESH,
    algorithm=settings.JWT_SIGNING_ALGORITHM,
)


class TestAccount():
    def setup_method(self):
        self.email = f"test_{uuid.uuid4().hex[:6]}@example.com"
        self.password = "mySecretPass123!"


    @staticmethod
    async def mock_send_email(to_email: str, subject: str, body: str):
        print(f"Mock send email to {to_email} with subject {subject}")

    async def test_register_user_success(self, monkeypatch, test_app):
        transport = ASGITransport(app=test_app)
        monkeypatch.setattr(
            "app.core.notifications.emails.EmailSender.send_activation_email",
            TestAccount.mock_send_email
        )
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/register/", json={
                "email": self.email,
                "password": self.password,
            })
        assert response.status_code in (200, 201)
        data = response.json()
        assert "id" in data
        assert data["email"] == self.email

    async def test_register_user_existing_email(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email="exists@example.com",
                    hashed_password="hashed_password_here",
                    is_active=True,
                    group_id=1
                )
            )
            await conn.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/register/", json={
                "email": "exists@example.com",
                "password": self.password
            })
        assert response.status_code == 409
        assert response.json() == {"detail": f"A user with this email exists@example.com already exists."}

    async def test_register_user_group_not_found(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(delete(UserGroupModel))
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/register/", json={
                "email": self.email,
                "password": self.password,
            })
        assert response.status_code == 500
        assert response.json() == {"detail": "Default user group not found."}

    async def test_activate_accounts_success(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
            )
            if not result.scalar_one_or_none():
                await conn.execute(
                    insert(UserGroupModel).values(name=UserGroupEnum.USER)
                )

            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password="hashed_password_here",
                    is_active=False,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            token_value = secrets.token_hex(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            await conn.execute(
                insert(ActivationTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/activate/", json={
                "email": self.email,
                "password": self.password,
                "token": token_value
            })
        assert response.status_code == 200
        assert response.json() == {"message": "User account activated successfully."}

    async def test_activate_accounts_invalid_token(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=self.password,
                    is_active=False,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/activate/", json={
                "email": self.email,
                "password": self.password,
                "token": "wrong_token"
            })
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired activation token."}

    async def test_activate_accounts_already_active(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
            )
            if not result.scalar_one_or_none():
                await conn.execute(
                    insert(UserGroupModel).values(name=UserGroupEnum.USER)
                )

            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=self.password,
                    is_active=True,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            token_value = secrets.token_hex(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            await conn.execute(
                insert(ActivationTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/activate/", json={
                "email": self.email,
                "password": self.password,
                "token": token_value
            })
        assert response.status_code == 400
        assert response.json() == {"detail": "User account is already active."}

    async def test_login_success(self, test_app):
        hashed = hash_password("Password123!")
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email="exists1@example.com",
                    hashed_password=hashed,
                    is_active=True,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/login/", json={
                "email": "exists1@example.com",
                "password": "Password123!",
            })
        assert response.status_code == 200

    async def test_login_invalid_email(self, test_app):
        hashed = hash_password("Password123!")
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email="exists1@example.com",
                    hashed_password=hashed,
                    is_active=True,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/login/", json={
                "email": "exists@example.com",
                "password": "Password123!",
            })
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password."}

    async def test_login_invalid_password(self, test_app):
        hashed = hash_password("Password123!")
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email="exists1@example.com",
                    hashed_password=hashed,
                    is_active=True,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/login/", json={
                "email": "exists1@example.com",
                "password": "Password123!aa",
            })
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password."}

    async def test_login_account_is_not_activated(self, test_app):
        hashed = hash_password("Password123!")
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email="exists1@example.com",
                    hashed_password=hashed,
                    is_active=False,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/login/", json={
                "email": "exists1@example.com",
                "password": "Password123!",
            })
        assert response.status_code == 403
        assert response.json() == {"detail": "User account is not activated."}

    async def test_logout_success(self, test_app):
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

        jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user_id})
        async with engine.begin() as conn:
            await conn.execute(
                insert(RefreshTokenModel).values(
                    user_id=user_id,
                    token=jwt_refresh_token,
                    expires_at=datetime.utcnow() + timedelta(days=1)
                )
            )
            await conn.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/logout/", json={
                "refresh_token": jwt_refresh_token,
            })

        assert response.status_code == 200
        assert response.json() == {"message": "User logged out successfully."}

    async def test_logout_invalid_refresh_token(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/accounts/logout/", json={
                "refresh_token": "fake_token",
            })

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid refresh token."}

    async def test_change_password_success(self, test_app):
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

        jwt_access_token = jwt_manager.create_access_token({"user_id": user_id})
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/accounts/change-password/",
                json={
                    "old_password": "Password123!",
                    "new_password": "Password123!!"
                },
                headers=headers
            )
        assert response.status_code == 200
        assert response.json() == {"message": "Password changed successfully."}

    async def test_change_password_user_not_found(self, test_app):
        fake_token = jwt_manager.create_access_token({"user_id": 99999})
        headers = {"Authorization": f"Bearer {fake_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/accounts/change-password/",
                json={
                    "old_password": "Password123!",
                    "new_password": "Password123!!"
                },
                headers=headers
            )
        print(response.status_code)
        print(response.json())

        assert response.status_code == 404
        assert response.json() == {"detail": "User not found."}

    async def test_change_password_invalid_old_password(self, test_app):
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

        jwt_access_token = jwt_manager.create_access_token({"user_id": user_id})
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/accounts/change-password/",
                json={
                    "old_password": "Password123",
                    "new_password": "Password123!!"
                },
                headers=headers
            )
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid old password."}
