import enum
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLAlchemyEnum
from app.models.Base import Base
from sqlalchemy import (
    ForeignKey,
    func,
    DateTime, DECIMAL,
)


class StatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"



class OrdersModel(Base):
    __tablename__ = "orders"

    id = Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id = Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status = Mapped[StatusEnum] = mapped_column(
        SQLAlchemyEnum(StatusEnum),
        nullable=False,
        default=StatusEnum.PENDING,
    )
    total_amount = Mapped[float] = mapped_column(DECIMAL(10,2), nullable=True)

    items = Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    user = Mapped["UserModel"] = relationship(back_populates="orders")


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id = Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id = Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    movie_id = Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    price_at_order = Mapped[float] = mapped_column(DECIMAL(10,2), nullable=False)

    order = Mapped["OrdersModel"] = relationship(back_populates="items")
    movie = Mapped["MovieModel"] = relationship(back_populates="items")
