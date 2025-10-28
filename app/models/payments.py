import enum
from datetime import datetime
from decimal import Decimal

from app.models.accounts import UserModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLAlchemyEnum
from app.models.Base import Base
from sqlalchemy import (
    ForeignKey,
    func,
    DateTime,
    DECIMAL,
)


class StatusEnum(str, enum.Enum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    status: Mapped[StatusEnum] = mapped_column(
        SQLAlchemyEnum(StatusEnum),
        nullable=False,
        default=StatusEnum.SUCCESSFUL,
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(nullable=True)

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        lazy="selectin",
    )
    order: Mapped["OrdersModel"] = relationship(
        "OrdersModel",
        lazy="selectin",
    )
    items: Mapped[list["PaymentItemModel"]] = relationship(
        "PaymentItemModel",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PaymentItemModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"),
        nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id"),
        nullable=False
    )
    price_at_payment: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        nullable=False
    )

    payment: Mapped["PaymentModel"] = relationship(
        "PaymentModel",
        back_populates="items",
        lazy="selectin",
    )
    order_item: Mapped["OrderItemModel"] = relationship(
        "OrderItemModel",
        lazy="selectin",
    )
