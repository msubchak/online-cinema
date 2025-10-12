from fastapi import FastAPI
from routes import accounts_router

app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, users, and orders in an online cinema."
)

api_version_prefix = "api/v1"

app.include_router(accounts_router, prefix=api_version_prefix)
