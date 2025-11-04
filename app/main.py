from fastapi import FastAPI, Depends
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

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
from app.security.auth_dependencies import get_current_user
from sqlalchemy import select, insert
from app.models.accounts import UserGroupModel, UserGroupEnum
from app.core.database import engine
from app.models.Base import Base

app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, "
                "users, and orders in an online cinema.",
    #docs_url=None,
    #   redoc_url=None
)


#@app.get("/docs", include_in_schema=False)
#async def get_protected_docs(current_user=Depends(get_current_user)):
    #    return get_swagger_ui_html(
#       openapi_url="/openapi.json",
#       title="Protected Swagger UI",
#       swagger_ui_parameters={"persistAuthorization": True},
#   )


#@app.get("/redoc", include_in_schema=False)
#async def get_protected_redoc(current_user=Depends(get_current_user)):
    #return get_redoc_html(
    #        openapi_url="/openapi.json",
    #        title="Protected ReDoc"
#    )


async def ensure_default_group():
    async with engine.begin() as conn:
        result = await conn.execute(
            select(UserGroupModel)
            .where(UserGroupModel.name == UserGroupEnum.USER)
        )
        if not result.scalar():
            await conn.execute(
                insert(UserGroupModel).values(name=UserGroupEnum.USER)
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
