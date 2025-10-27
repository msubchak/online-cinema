import pytest_asyncio
from sqlalchemy import insert, delete
from app.main import app
from app.core.database import engine
from app.models.Base import Base
from app.models.accounts import (
    UserModel,
    ActivationTokenModel,
    RefreshTokenModel,
    UserGroupModel,
    UserGroupEnum,
    PasswordResetTokenModel
)


@pytest_asyncio.fixture(scope="module")
async def test_app():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(insert(UserGroupModel).values(name=UserGroupEnum.USER))
        await conn.commit()
    yield app
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clear_all_tables():
    async with engine.begin() as conn:
        await conn.execute(delete(ActivationTokenModel))
        await conn.execute(delete(PasswordResetTokenModel))
        await conn.execute(delete(RefreshTokenModel))
        await conn.execute(delete(UserModel))
        await conn.execute(delete(UserGroupModel))
        await conn.execute(
            insert(UserGroupModel).values(name=UserGroupEnum.USER)
        )
        await conn.commit()
