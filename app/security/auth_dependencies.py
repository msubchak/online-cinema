from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.email_utils import get_jwt_auth_manager
from app.core.database import get_db
from app.models.accounts import UserModel, UserGroupEnum
from app.security.interfaces import JWTAuthManagerInterface


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/login/")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> UserModel:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token."
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_BAD_REQUEST,
            detail="No user found."
        )

    return user


async def admin_required(
        current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    if current_user.group.name != UserGroupEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )
    return current_user


async def moderator_required(
        current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    if current_user.group.name not in [
        UserGroupEnum.MODERATOR,
        UserGroupEnum.ADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin privileges required."
        )
    return current_user
