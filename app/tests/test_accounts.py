import uuid
import pytest
import secrets
from app.core.config.email_utils import get_settings
from sqlalchemy import insert, select, delete

from app.models.accounts import (
    UserModel,
    ActivationTokenModel,
    UserGroupModel,
    UserGroupEnum,
    RefreshTokenModel,
    PasswordResetTokenModel
)
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
    async def mock_send_email(to_email: str, subject: str, body: str) -> None:
        print(f"Mock send email to {to_email} with subject {subject}")


class TestRegister(TestAccount):
    async def test_register_user_success(self, monkeypatch, test_app):
        transport = ASGITransport(app=test_app)
        monkeypatch.setattr(
            "app.core.notifications.emails.EmailSender.send_activation_email",
            TestAccount.mock_send_email
        )
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/register/",
                json={
                    "email": "exists@example.com",
                    "password": self.password
                }
            )
        assert response.status_code == 409
        assert "detail" in response.json()

    async def test_register_user_group_not_found(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(delete(UserGroupModel))
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/register/",
                json={
                    "email": self.email,
                    "password": self.password,
                }
            )
        assert response.status_code == 500
        assert response.json() == {"detail": "Default user group not found."}


class TestActivateAccount(TestAccount):
    async def test_activate_accounts_success(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                select(UserGroupModel).where(
                    UserGroupModel.name == UserGroupEnum.USER
                )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/activate/",
                json={
                    "email": self.email,
                    "password": self.password,
                    "token": token_value
                }
            )
        assert response.status_code == 200
        assert response.json() == {
            "message": "User account activated successfully."
        }

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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/activate/",
                json={
                    "email": self.email,
                    "password": self.password,
                    "token": "wrong_token"
                }
            )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Invalid or expired activation token."
        }

    async def test_activate_accounts_already_active(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                select(UserGroupModel).where(
                    UserGroupModel.name == UserGroupEnum.USER
                )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/activate/",
                json={
                    "email": self.email,
                    "password": self.password,
                    "token": token_value
                }
            )
        assert response.status_code == 400
        assert response.json() == {"detail": "User account is already active."}


class TestLogin(TestAccount):
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={
                    "email": "exists1@example.com",
                    "password": "Password123!",
                }
            )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={
                    "email": "exists@example.com",
                    "password": "Password123!",
                }
            )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={
                    "email": "exists1@example.com",
                    "password": "Password123!aa",
                }
            )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/login/",
                json={
                    "email": "exists1@example.com",
                    "password": "Password123!",
                }
            )
        assert response.status_code == 403
        assert response.json() == {"detail": "User account is not activated."}


class TestLogout(TestAccount):
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

        jwt_refresh_token = jwt_manager.create_refresh_token(
            {
                "user_id": user_id
            }
        )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/logout/",
                json={
                    "refresh_token": jwt_refresh_token,
                }
            )

        assert response.status_code == 200
        assert response.json() == {"message": "User logged out successfully."}

    async def test_logout_invalid_refresh_token(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/logout/",
                json={
                    "refresh_token": "fake_token",
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid refresh token."}


class TestChangePassword(TestAccount):
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

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": user_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
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

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": user_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
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


class TestResetPasswordRequest(TestAccount):
    async def test_reset_password_request_success(self, test_app, monkeypatch):
        monkeypatch.setattr(
            "app.core.notifications.emails."
            "EmailSender.send_password_reset_email",
            TestAccount.mock_send_email
        )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/request/",
                json={
                    "email": "exists1@example.com",
                }
            )

        assert response.status_code == 200
        assert response.json() == {
            "message": "Password reset email sent successfully."
        }

    async def test_reset_password_request_user_not_active(self, test_app):
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/request/",
                json={
                    "email": "exists1@example.com",
                }
            )

        assert response.json() == {
            "message": "If you are registered, you will "
                       "receive an email with instructions."
        }

    async def test_reset_password_request_invalid_user(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/request/",
                json={
                    "email": "exists1@example.com",
                }
            )

        assert response.json() == {
            "message": "If you are registered, you will "
                       "receive an email with instructions."
        }


class TestResetPasswordComplete(TestAccount):
    async def test_reset_password_complete_success(
            self,
            test_app,
            monkeypatch
    ):
        monkeypatch.setattr(
            "app.core.notifications.emails."
            "EmailSender.send_password_reset_complete_email",
            TestAccount.mock_send_email
        )

        async with engine.begin() as conn:
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
                insert(PasswordResetTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": token_value,
                    "email": self.email,
                    "new_password": "nEwPassword!!23"
                }
            )

        assert response.status_code == 200
        assert response.json() == {"message": "Password reset successfully."}

    async def test_reset_password_complete_user_not_found(self, test_app):
        async with engine.begin() as conn:
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
                insert(PasswordResetTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": token_value,
                    "email": "fake@gmail.com",
                    "new_password": "NewPassword11!!"
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid email or token."}

    async def test_reset_password_complete_user_not_active(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=self.password,
                    is_active=False,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            token_value = secrets.token_hex(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            await conn.execute(
                insert(PasswordResetTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": token_value,
                    "email": self.email,
                    "new_password": "NewPassword11!!"
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid email or token."}

    async def test_reset_password_complete_invalid_email(self, test_app):
        async with engine.begin() as conn:
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
                insert(PasswordResetTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": token_value,
                    "email": "example313@example.come",
                    "new_password": "nEwPassword!!23"
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid email or token."}

    async def test_reset_password_complete_invalid_token(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=self.password,
                    is_active=True,
                    group_id=1
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": "fake_token",
                    "email": self.email,
                    "new_password": "nEwPassword!!23"
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid email or token."}

    async def test_reset_password_complete_expired_token(self, test_app):
        async with engine.begin() as conn:
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
            expires = datetime.utcnow() - timedelta(hours=1)
            await conn.execute(
                insert(PasswordResetTokenModel).values(
                    token=token_value,
                    expires_at=expires,
                    user_id=user_id
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/reset-password/complete/",
                json={
                    "token": token_value,
                    "email": self.email,
                    "new_password": "Password123!!"
                })
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid email or token."}


class TestTokenRefresh(TestAccount):
    async def test_token_refresh_success(self, test_app):
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

        jwt_refresh_token = jwt_manager.create_refresh_token(
            {
                "user_id": user_id
            }
        )
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
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/token/refresh/",
                json={
                    "refresh_token": jwt_refresh_token,
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != ""
        assert data["token_type"] == "bearer"

    async def test_token_refresh_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/token/refresh/",
                json={
                    "refresh_token": "fake_refresh_token"
                }
            )

        assert response.status_code == 401
        assert response.json() == {"detail": "Refresh token not found."}

    async def test_token_refresh_invalid_refresh_token(self, test_app):
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

        invalid_token = "invalid.jwt.token"
        async with engine.begin() as conn:
            await conn.execute(
                insert(RefreshTokenModel).values(
                    user_id=user_id,
                    token=invalid_token,
                    expires_at=datetime.utcnow() + timedelta(days=1)
                )
            )
            await conn.commit()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/token/refresh/",
                json={
                    "refresh_token": invalid_token
                }
            )

        assert response.status_code == 400
        assert "detail" in response.json()


class TestAdminChangeGroup(TestAccount):
    async def test_admin_change_user_group_success(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.MODERATOR))

            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                )
            )
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=3
                ).returning(UserModel.id)
            )
            admin_id = result.scalar_one()
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": admin_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/change-user-group/",
                json={
                    "email": self.email,
                    "new_group": "moderator"
                },
                headers=headers
            )

        assert response.status_code == 200
        assert "message" in response.json()

    async def test_admin_change_user_group_user_not_found(self, test_app):
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
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": admin_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/change-user-group/",
                json={
                    "email": "fakeemail@gmail.com",
                    "new_group": "moderator"
                },
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "User not found."}

    async def test_admin_change_user_group_not_found(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                )
            )
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
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
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/change-user-group/",
                json={
                    "email": self.email,
                    "new_group": "moderator"
                },
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Group not found."}

    async def test_admin_change_user_group_already_in_group(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.MODERATOR))
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                )
            )
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=3
                ).returning(UserModel.id)
            )
            admin_id = result.scalar_one()
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": admin_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/change-user-group/",
                json={
                    "email": self.email,
                    "new_group": "user"
                },
                headers=headers
            )

        assert response.status_code == 400
        assert "detail" in response.json()


class TestActivateUser(TestAccount):
    async def test_admin_activate_user_success(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=False,
                    group_id=1
                )
            )
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
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
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/activate-user/",
                json={
                    "email": self.email,
                },
                headers=headers
            )

        assert response.status_code == 200
        assert response.json() == {"message": f"User {self.email} activated"}

    async def test_admin_activate_user_already_activate(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(insert(
                UserGroupModel
            ).values(name=UserGroupEnum.ADMIN))
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                )
            )
            result = await conn.execute(
                insert(UserModel).values(
                    email="admin@example.com",
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
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/activate-user/",
                json={
                    "email": self.email,
                },
                headers=headers
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "User not found or user already active."
        }

    async def test_admin_activate_user_not_found(self, test_app):
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
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": admin_id
            }
        )
        headers = {"Authorization": f"Bearer {jwt_access_token}"}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/admin/activate-user/",
                json={
                    "email": self.email,
                },
                headers=headers
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "User not found or user already active."
        }


class TestResendActivation(TestAccount):
    async def test_resend_activation_success(self, test_app, monkeypatch):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=False,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            await conn.execute(
                insert(ActivationTokenModel).values(
                    user_id=user_id,
                    token="abc123",
                    expires_at=datetime.utcnow() - timedelta(hours=1)
                )
            )
            await conn.commit()

        monkeypatch.setattr(
            "app.core.notifications.emails.EmailSender.send_activation_email",
            TestAccount.mock_send_email
        )

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/resend-activation/",
                json={
                    "email": self.email,
                }
            )

        assert response.status_code == 200
        assert response.json() == {"message": "Activation link sent."}

    async def test_resend_activation_user_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/resend-activation/",
                json={
                    "email": self.email,
                }
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "User not found."}

    async def test_resend_activation_user_is_active(self, test_app):
        async with engine.begin() as conn:
            await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                )
            )

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/resend-activation/",
                json={
                    "email": self.email
                }
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "User is already active."}

    async def test_resend_activation_already_activate(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=False,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            await conn.execute(
                insert(ActivationTokenModel).values(
                    user_id=user_id,
                    token="abc123",
                    expires_at=datetime.utcnow() + timedelta(hours=1)
                )
            )
            await conn.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/resend-activation/",
                json={
                    "email": self.email,
                }
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Activation link already sent. Please try again later."
        }

    async def test_resend_activation_token_not_expired(self, test_app):
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email=self.email,
                    hashed_password=hash_password("Password123!"),
                    is_active=False,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            await conn.execute(
                insert(ActivationTokenModel).values(
                    user_id=user_id,
                    token="abc123",
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
            )
            await conn.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/accounts/resend-activation/",
                json={
                    "email": self.email,
                }
            )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Activation link already sent. Please try again later."
        }
