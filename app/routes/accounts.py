from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, status, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from app.core.config.settings import BaseAppSettings
from app.core.config.email_utils import get_accounts_email_notificator, get_settings, get_jwt_auth_manager
from app.core.database import get_db
from app.core.exceptions.security import BaseSecurityError
from app.core.notifications.interfaces import EmailSenderInterface
from app.models.accounts import (
    UserModel,
    UserGroupEnum,
    ActivationTokenModel,
    UserGroupModel, RefreshTokenModel, PasswordResetTokenModel
)
from app.core import accounts_validators
from app.schemas.accounts import (
    UserRegistrationResponseSchema,
    UserRegistrationRequestSchema,
    MessageResponseSchema,
    UserActivationRequestSchema, UserLoginResponseSchema, UserLoginRequestSchema, UserLogoutRequestSchema,
    UserChangePasswordRequestSchema, PasswordResetRequestSchema, PasswordResetCompleteRequestSchema,
    TokenRefreshResponseSchema, TokenRefreshRequestSchema, ChangeUserGroupRequestSchema
)
from app.security.auth_dependencies import get_current_user, admin_required
from app.security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    summary="User Registration",
    description="Register a new user with an email and password.",
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
        user_data: UserRegistrationRequestSchema,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserRegistrationResponseSchema:
    stmt = select(UserModel).where(UserModel.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists.",
        )

    stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    result = await db.execute(stmt)
    user_group = result.scalars().first()
    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found."
        )

    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)

        await db.commit()
        await db.refresh(new_user)

        activation_link = f"https://localhost:8000/api/v1/accounts/activate?token={activation_token.token}"
        background_tasks.add_task(
            email_sender.send_activation_email,
            new_user.email,
            activation_link,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation"
        ) from e
    else:
        return UserRegistrationResponseSchema.model_validate(new_user)


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    summary="Activate a user",
    description="Activate a user's account using their email and activation token.",
    status_code=status.HTTP_200_OK,
)
async def activate_account(
        activation_data: UserActivationRequestSchema,
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(
            UserModel.email == activation_data.email,
            ActivationTokenModel.token == activation_data.token
        )
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if not token_record or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )
    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    summary="Login a user",
    description="Login a user's account.",
    status_code=status.HTTP_200_OK,
)
async def login_user(
        login_data: UserLoginRequestSchema,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> UserLoginResponseSchema:
    stmt = select(UserModel).filter_by(email=login_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated."
        )

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.LOGIN_TIME_DAYS,
            token=jwt_refresh_token
        )
        db.add(refresh_token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request."
        )

    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@router.post(
    "/logout/",
    response_model=MessageResponseSchema,
    summary="Logout a user",
    description="Logout a user's account.",
    status_code=status.HTTP_200_OK,
)
async def logout_user(
        logout_data: UserLogoutRequestSchema,
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    stmt = select(RefreshTokenModel).where(
        RefreshTokenModel.token == logout_data.refresh_token
    )
    result = await db.execute(stmt)
    token = result.scalars().first()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token."
        )

    await db.delete(token)
    await db.commit()

    return MessageResponseSchema(message="User logged out successfully.")


@router.post(
    "/change-password/",
    response_model=MessageResponseSchema,
    summary="Change a user's password",
    description="Change a user's password.",
    status_code=status.HTTP_200_OK,
)
async def change_password(
        change_pass_data: UserChangePasswordRequestSchema,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user)
) -> MessageResponseSchema:
    stmt = select(UserModel).where(UserModel.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found."
        )

    if not user.verify_password(change_pass_data.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password."
        )

    try:
        user.password = change_pass_data.new_password
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request."
        )

    return MessageResponseSchema(message="Password changed successfully.")


@router.post(
    "/reset-password/request/",
    response_model=MessageResponseSchema,
    summary="Reset a user's password",
    description="Reset a user's password.",
    status_code=status.HTTP_200_OK,
)
async def request_password_reset_token(
        data: PasswordResetRequestSchema,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator)
) -> MessageResponseSchema:
    stmt = select(UserModel).where(UserModel.email == data.email)
    result = await db.execute(stmt)
    user = result.scalars().one_or_none()

    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If you are registered, you will receive an email with instructions."
        )

    await db.execute(delete(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id))

    reset_token = PasswordResetTokenModel(user_id=cast(int, user.id))
    db.add(reset_token)
    await db.commit()

    reset_link = f"https://localhost:8000/api/v1/accounts/reset-password?token={reset_token.token}"
    background_tasks.add_task(
        email_sender.send_password_reset_email,
        user.email,
        reset_link,
    )

    return MessageResponseSchema(
        message="Password reset email sent successfully."
    )


@router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
    summary="Reset a user's password",
    description="Reset a user's password if a valid token is provided",
    status_code=status.HTTP_200_OK,
)
async def reset_password(
        data: PasswordResetCompleteRequestSchema,
        background_tasks: BackgroundTasks,
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    stmt = select(UserModel).where(UserModel.email == data.email)
    result = await db.execute(stmt)
    user = result.scalars().one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    stmt = select(PasswordResetTokenModel).filter_by(user_id=user.id)
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    if not token_record or token_record.token != data.token:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    expires_at = cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.delete(token_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    try:
        user.set_password(data.password)
        await db.delete(token_record)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password."
        )

    login_link = "https://localhost:8000/api/v1/accounts/login"
    background_tasks.add_task(
        email_sender.send_password_reset_complete_email,
        user.email,
        login_link
    )

    return MessageResponseSchema(message="Password reset successfully.")


@router.post(
    "/token/refresh/",
    response_model=TokenRefreshResponseSchema,
    summary="Refresh access token",
    description="Refresh the accesss token using a valid refresh token",
    status_code=status.HTTP_200_OK,
)
async def refresh_access_token(
        token_data: TokenRefreshRequestSchema,
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = decoded_token.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    stmt = select(RefreshTokenModel).filter_by(token=token_data.refresh_token)
    result = await db.execute(stmt)
    refresh_token_record = result.scalars().first()
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found."
        )

    stmt = select(UserModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    user = result.scalars().one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@router.post(
    "/admin/change-user-group/",
    response_model=MessageResponseSchema,
    summary="Change user group",
    description="Change user group",
    status_code=status.HTTP_200_OK,
)
async def change_user_group(
        data: ChangeUserGroupRequestSchema,
        db: AsyncSession = Depends(get_db),
        admin_user: UserModel = Depends(admin_required)
) -> MessageResponseSchema:
    stmt = select(UserModel).where(UserModel.email == data.email)
    result = await db.execute(stmt)
    user = result.scalars().one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    stmt = select(UserGroupModel).where(UserGroupModel.name == data.new_group)
    result = await db.execute(stmt)
    group = result.scalars().one_or_none()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found."
        )

    if user.group_id == group.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already in group {group.name}."
        )

    try:
        user.group_id = group.id
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user group."
        )

    return MessageResponseSchema(message=f"User {user.email} changed group to {group.name}")
