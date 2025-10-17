from fastapi import FastAPI
from app.routes import accounts_router, movies_router, genres_router

app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, users, and orders in an online cinema."
)

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
app.include_router(genres_router, prefix=f"{api_version_prefix}/genres", tags=["genres"])
