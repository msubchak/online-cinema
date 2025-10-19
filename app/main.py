from fastapi import FastAPI
from app.routes import (
    accounts_router,
    movies_router,
    genres_router,
    stars_router,
    cart_router,
    order_router,
)

app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, users, and orders in an online cinema."
)

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
app.include_router(genres_router, prefix=f"{api_version_prefix}/genres", tags=["genres"])
app.include_router(stars_router, prefix=f"{api_version_prefix}/stars", tags=["stars"])
app.include_router(cart_router, prefix=f"{api_version_prefix}/cart", tags=["cart"])
app.include_router(order_router, prefix=f"{api_version_prefix}/order", tags=["orders"])
