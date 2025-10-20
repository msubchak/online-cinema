import stripe
from sqlalchemy import select
from decimal import Decimal
from app.models.accounts import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.core.config import settings
from app.models.order import OrderItemModel, OrdersModel, StatusEnum
from app.models.payments import PaymentModel, PaymentItemModel
from app.schemas.payments import PaymentRequestSchema, PaymentResponseSchema, PaymentItemSchema
from app.security.auth_dependencies import get_current_user


router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post(
    "/",
    response_model=PaymentResponseSchema,
    summary="",
    description="",
    status_code=status.HTTP_201_CREATED,
)
async def create_payments(
        payment_data: PaymentRequestSchema,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
) -> PaymentResponseSchema:
    stmt_user = select(UserModel).where(UserModel.email == current_user.email)
    result = await db.execute(stmt_user)
    user = result.scalars().one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    stmt_order = select(OrdersModel).where(
        OrdersModel.id == payment_data.order_id,
        OrdersModel.user_id == current_user.id
    )
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status == StatusEnum.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already paid",
        )

    stmt_items = select(OrderItemModel).where(OrderItemModel.order_id == payment_data.order_id)
    result = await db.execute(stmt_items)
    items = result.scalars().all()

    total_amount = sum(item.price_at_order for item in items)

    if not stripe.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is not configured. Please try later."
        )

    try:
        intent = stripe.PaymentIntent.create(
            amount=int((total_amount * Decimal(100)).to_integral_value()),
            currency="uah",
            payment_method_types=["card"]
        )
    except stripe.error.InvalidRequestError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment method not available. Try a different payment method."
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment processing error. Please try again later."
        )
    external_payment_id = intent.id

    payment = PaymentModel(
        user_id=current_user.id,
        order_id=order.id,
        amount=total_amount,
        external_payment_id=intent.id,
        status=StatusEnum.SUCCESSFUL
    )

    payment.items = [
        PaymentItemModel(
            order_item_id=item.id,
            price_at_payment=item.price_at_order,
        )
        for item in items
    ]
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentResponseSchema(
        id=payment.id,
        user_id=payment.user_id,
        order_id=payment.order_id,
        created_at=payment.created_at,
        status=payment.status,
        amount=payment.amount,
        external_payment_id=payment.external_payment_id,
        items=[
            PaymentItemSchema(
                order_item_id=item.order_item_id,
                price_at_payment=item.price_at_payment
            )
                for item in payment.items
        ],
    )
