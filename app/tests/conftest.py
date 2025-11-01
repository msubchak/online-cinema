import pytest_asyncio
from sqlalchemy import insert, delete
from app.main import app
from app.core.database import engine
from app.models.movies import movie_genres, movie_stars, movie_directors
from app.models import (
    MovieModel,
    GenreModel,
    StarModel,
    CertificationModel,
    DirectorModel,
    OrdersModel,
    OrderItemModel,
    CartModel,
    CartItemModel,
    PaymentModel
)
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
        await conn.execute(insert(
            UserGroupModel
        ).values(name=UserGroupEnum.USER))
        await conn.commit()
    yield app
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clear_all_tables():
    async with engine.begin() as conn:
        for model in [
            ActivationTokenModel, PasswordResetTokenModel, RefreshTokenModel,
            UserModel, UserGroupModel,
            OrderItemModel, OrdersModel,
            MovieModel, GenreModel,
            StarModel, DirectorModel,
            CertificationModel, CartModel,
            CartItemModel, PaymentModel,
        ]:
            await conn.execute(delete(model))

        for table in [movie_genres, movie_stars, movie_directors]:
            await conn.execute(table.delete())

        await conn.execute(
            insert(UserGroupModel).values(name=UserGroupEnum.USER)
        )
        await conn.commit()
