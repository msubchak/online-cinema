import enum
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy import (
    ForeignKey,
    String,
    Boolean,
    DateTime,
    Enum,
    Integer,
    func,
    Text,
    Date,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from app.core.validators.accounts import (
    validate_email as check_email,
    validate_password_strength
)
from app.models.Base import Base
from app.security.password import verify_password, hash_password
from app.security.utils import generate_secure_token


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    name: Mapped[UserGroupEnum] = mapped_column(
        Enum(UserGroupEnum),
        nullable=False,
        unique=True
    )
    users: Mapped[List["UserModel"]] = relationship(
        "UserModel",
        back_populates="group"
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    _hashed_password: Mapped[str] = mapped_column(
        "hashed_password",
        String(255),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey(
            "user_groups.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )
    group: Mapped["UserGroupModel"] = relationship(
        "UserGroupModel",
        back_populates="users",
        lazy="selectin"
    )

    orders: Mapped[List["OrdersModel"]] = relationship(
        "OrdersModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    activation_token: Mapped[Optional["ActivationTokenModel"]] = relationship(
        "ActivationTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    password_reset_token: Mapped[
        Optional["PasswordResetTokenModel"]
    ] = relationship(
        "PasswordResetTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    refresh_tokens: Mapped[List["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return (f"<UserModel(id={self.id}, email={self.email}, "
                f"is_active={self.is_active})>")

    def has_group(self, group_name: UserGroupEnum) -> bool:
        return self.group.name == group_name

    def set_password(self, new_password: str) -> None:
        self._hashed_password = hash_password(new_password)

    @classmethod
    def create(
            cls,
            email: str,
            raw_password: str,
            group_id: int | Mapped[int]
    ) -> "UserModel":
        user = cls(email=email, group_id=group_id)
        user.password = raw_password
        return user

    @property
    def password(self) -> None:
        raise AttributeError("Password is write-only. "
                             "Use the setter to set the password.")

    @password.setter
    def password(self, raw_password: str) -> None:
        validate_password_strength(raw_password)
        self._hashed_password = hash_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return verify_password(raw_password, self._hashed_password)

    @validates("email")
    def validate_email(self, key, value):
        return check_email(value.lower())


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[Date]] = mapped_column(Date)
    info: Mapped[Optional[str]] = mapped_column(Text)


class TokenBaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=generate_secure_token
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(days=1)
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    def is_expired(self) -> bool:
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires


class ActivationTokenModel(TokenBaseModel):
    __tablename__ = "activation_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="activation_token"
    )

    __table_args__ = (UniqueConstraint("user_id"),)

    def __repr__(self):
        return (f"<ActivationTokenModel(id={self.id}, "
                f"token={self.token}, expires_at={self.expires_at})>")


class PasswordResetTokenModel(TokenBaseModel):
    __tablename__ = "password_reset_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="password_reset_token"
    )

    __table_args__ = (UniqueConstraint("user_id"),)

    def __repr__(self):
        return (f"<PasswordResetTokenModel(id={self.id}, token={self.token}, "
                f"expires_at={self.expires_at})>")


class RefreshTokenModel(TokenBaseModel):
    __tablename__ = "refresh_tokens"

    user: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="refresh_tokens"
    )
    token: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
        default=generate_secure_token
    )

    @classmethod
    def create(
            cls,
            user_id: int,
            days_valid: int,
            token: str
    ) -> "RefreshTokenModel":
        expires_at = datetime.now(timezone.utc) + timedelta(days=days_valid)
        return cls(user_id=user_id, expires_at=expires_at, token=token)

    def __repr__(self):
        return (f"<RefreshTokenModel(id={self.id}, "
                f"token={self.token}, expires_at={self.expires_at})>")
