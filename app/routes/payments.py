import stripe
from typing import Optional, List
from datetime import date
from sqlalchemy import select
from decimal import Decimal

from app.core.config.email_utils import get_accounts_email_notificator
from app.core.notifications.interfaces import EmailSenderInterface
from app.models.accounts import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, BackgroundTasks
from app.core.database import get_db
from app.core.config import settings
from app.models.order import OrderItemModel, OrdersModel, StatusEnum
from app.models.payments import PaymentModel, PaymentItemModel
from app.schemas.payments import PaymentRequestSchema, PaymentResponseSchema, PaymentItemSchema
from app.security.auth_dependencies import get_current_user, admin_required

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.webhook_secret = settings.STRIPE_WEBHOOK_SECRET


async def update_payment_status(db: AsyncSession, status: StatusEnum, external_id: str):
    stmt = select(PaymentModel).where(PaymentModel.external_payment_id == external_id)
    result = await db.execute(stmt)
    payment = result.scalars().first()

    if payment:
        payment.status = status
        await db.commit()


@router.post(
    "/",
    response_model=PaymentResponseSchema,
    summary="Create a payment",
    description="Processes a payment for a user's order via Stripe.",
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
        status=StatusEnum.CANCELED
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


@router.post(
    "/webhook",
    summary="Stripe Webhook.",
    description="Receives Stripe events and updates payment status (successful, canceled, refunded).",
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    payload = await request.body()
    sig_head = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_head, stripe.webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "payment_intent.succeeded":
        await update_payment_status(db, StatusEnum.SUCCESSFUL, event["data"]["object"]["id"])
        stmt = select(PaymentModel).where(PaymentModel.external_payment_id == event["data"]["object"]["id"])
        result = await db.execute(stmt)
        payment = result.scalars().first()

        if payment:
            order_link = f"https://localhost:8000/api/v1/payment/{payment.order_id}"
            background_tasks.add_task(
                email_sender.send_success_payment,
                payment.user.email,
                order_link
            )

    elif event["type"] == "payment_intent.payment_failed":
        await update_payment_status(db, StatusEnum.CANCELED, event["data"]["object"]["id"])

    elif event["type"] == "charge.refunded":
        await update_payment_status(db, StatusEnum.REFUNDED, event["data"]["object"]["id"])

    return {"status": "success"}


@router.get(
    "/",
    response_model=List[PaymentResponseSchema],
    summary="Get user's payments",
    description="Returns all payments of the current user. Supports optional filters by status and date range.",
    status_code=status.HTTP_200_OK,
)
async def get_payments_by_user(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        status: Optional[StatusEnum] = Query(None, description="Filter by payment status"),
        start_date: Optional[date] = Query(None, description="Filter by start date"),
        end_date: Optional[date] = Query(None, description="Filter by end date"),
) -> List[PaymentResponseSchema]:
    stmt = select(PaymentModel).where(PaymentModel.user_id == current_user.id)

    if status is not None:
        stmt = stmt.where(PaymentModel.status == status)
    if start_date is not None:
        stmt = stmt.where(PaymentModel.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(PaymentModel.created_at <= end_date)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payments found",
        )

    return payments


@router.get(
    "/admin/",
    response_model=List[PaymentResponseSchema],
    summary="View all user payments (admin)",
    description="Allows admins to view all user payments. "
        "Filters can be applied by user, date range, or payments status (paid, canceled, pending).",
    status_code=status.HTTP_200_OK,
)
async def get_payments_by_admin(
        db: AsyncSession = Depends(get_db),
        admin_user: UserModel = Depends(admin_required),
        user_id: Optional[int] = Query(None, description="Filter by user id"),
        status: Optional[StatusEnum] = Query(None, description="Filter by payment status"),
        start_date: Optional[date] = Query(None, description="Filter by start date"),
        end_date: Optional[date] = Query(None, description="Filter by end date"),
) -> List[PaymentResponseSchema]:
    stmt = select(PaymentModel)

    if user_id is not None:
        stmt = stmt.where(PaymentModel.user_id == user_id)
    if status is not None:
        stmt = stmt.where(PaymentModel.status == status)
    if start_date is not None:
        stmt = stmt.where(PaymentModel.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(PaymentModel.created_at <= end_date)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payments found",
        )

    return payments
