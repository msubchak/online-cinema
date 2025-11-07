from fastapi import FastAPI, Depends
from app.routes import (
    accounts_router,
    movies_router,
    genres_router,
    stars_router,
    cart_router,
    order_router,
    payments_router,
    directors_router,
)
from sqlalchemy import select, insert
from app.models.accounts import UserGroupModel, UserGroupEnum
from app.core.database import engine
from app.models.Base import Base


app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, "
                "users, and orders in an online cinema.",
)


async def ensure_default_group():
    async with engine.begin() as conn:
        existing = await conn.execute(select(UserGroupModel.name))
        existing_names = {row[0] for row in existing.fetchall()}
        required = {UserGroupEnum.USER, UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR}
        missing = required - existing_names

        if missing:
            await conn.execute(
                insert(UserGroupModel),
                [{"name": name} for name in missing]
            )


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_default_group()


api_version_prefix = "/api/v1"

app.include_router(
    accounts_router,
    prefix=f"{api_version_prefix}/accounts",
    tags=["accounts"]
)
app.include_router(
    movies_router,
    prefix=f"{api_version_prefix}/movies",
    tags=["movies"]
)
app.include_router(
    genres_router,
    prefix=f"{api_version_prefix}/genres",
    tags=["genres"]
)
app.include_router(
    stars_router,
    prefix=f"{api_version_prefix}/stars",
    tags=["stars"]
)
app.include_router(
    directors_router,
    prefix=f"{api_version_prefix}/directors",
    tags=["directors"]
)
app.include_router(
    cart_router,
    prefix=f"{api_version_prefix}/cart",
    tags=["cart"]
)
app.include_router(
    order_router,
    prefix=f"{api_version_prefix}/order",
    tags=["orders"]
)
app.include_router(
    payments_router,
    prefix=f"{api_version_prefix}/payment",
    tags=["payments"]
)
