from datetime import datetime, timezone

from app.core.database import async_session
from app.models.accounts import (
    RefreshTokenModel,
    ActivationTokenModel,
    PasswordResetTokenModel
)
from app.celery_app.celery_app import celery_app
import asyncio


def delete_expired_token_sync():
    async def inner():
        async with async_session() as db:
            now_utc = datetime.now(timezone.utc)

            await db.execute(
                RefreshTokenModel.__table__.delete().where(
                    RefreshTokenModel.expires_at < now_utc
                )
            )

            await db.execute(
                ActivationTokenModel.__table__.delete().where(
                    ActivationTokenModel.expires_at < now_utc
                )
            )

            await db.execute(
                PasswordResetTokenModel.__table__.delete().where(
                    PasswordResetTokenModel.expires_at < now_utc
                )
            )

            await db.commit()
    asyncio.run(inner())


@celery_app.task
def delete_expired_token_task():
    delete_expired_token_sync()
