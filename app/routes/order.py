from pygments.lexers import q
from sqlalchemy import select

from app.models.accounts import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.models.cart import CartModel
from app.models.order import OrderItemModel, OrdersModel, StatusEnum
from app.schemas.order import OrderResponseSchema, OrderMovieSchema
from app.security.auth_dependencies import get_current_user


router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponseSchema,
    summary="Create an order from the cart",
    description="Creates a new order for all movies in the authenticated user's cart",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
) -> OrderResponseSchema:
    stmt_cart = select(CartModel).where(
        CartModel.user_id == current_user.id,
    )
    result = await db.execute(stmt_cart)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart is empty or not found",
        )
    cart_items = list(cart.items)

    for item in cart.items:
        if not item.movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie with id {item.movie_id} no longer exists"
            )

        stmt_bought = (
            select(OrderItemModel)
            .join(OrdersModel)
            .where(
                OrdersModel.user_id == current_user.id,
                OrdersModel.status == StatusEnum.PAID,
                OrderItemModel.movie_id == item.movie_id
            )
        )
        result = await db.execute(stmt_bought)
        already_bought = result.scalars().first()
        if already_bought:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie '{item.movie.name}' already purchased",
            )

        stmt_pending = (
            select(OrderItemModel)
            .join(OrdersModel)
            .where(
                OrdersModel.user_id == current_user.id,
                OrdersModel.status == StatusEnum.PENDING,
                OrderItemModel.movie_id == item.movie_id
            )
        )
        result = await db.execute(stmt_pending)
        pending = result.scalars().first()

        if pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie '{item.movie.name}' is already in a pending order",
            )

    total_amount = sum(item.movie.price for item in cart.items)

    new_order = OrdersModel(
        user_id=current_user.id,
        total_amount=total_amount
    )

    async with db.begin():
        db.add(new_order)

        for item in cart_items:
            db.add(OrderItemModel(
                order=new_order,
                movie_id=item.movie_id,
                price_at_order=item.movie.price
            ))

        for item in cart_items:
            await db.delete(item)

    items = []
    for item in cart_items:
        order_movie = OrderMovieSchema(
            movie_id=item.movie_id,
            name=item.movie.name,
            price_at_order=item.movie.price
        )
        items.append(order_movie)


    return OrderResponseSchema(
        id=new_order.id,
        created_at=new_order.created_at,
        status=new_order.status.value,
        total_amount=total_amount,
        items=items,
    )


@router.post(
    "/{order_id}/pay",
    summary="Pay for an order",
    description="Processes payment for a specific order of the current user."
                "Checks if the order exists and has not already been paid."
                "If successful, updates the order status to 'PAID'.",
    status_code=status.HTTP_200_OK,
)
async def pay_order(
        order_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    stmt_order = select(OrdersModel).where(
        OrdersModel.id == order_id,
        OrdersModel.user_id == current_user.id,
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
        detail="Order is already paid",
    )

    order.status = StatusEnum.PAID
    await db.commit()
    await db.refresh(order)

    return {"message": f"Order {order.id} has been successfully paid."}


@router.post(
    "/{order_id}/cancel",
    summary="Cancel a pending order",
    description="Allows a user to cancel their order if it has not been paid yet. Paid orders cannot be canceled directly.",
    status_code=status.HTTP_200_OK,
)
async def cancel_order(
        order_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    stmt_order = select(OrdersModel).where(
        OrdersModel.id == order_id,
        OrdersModel.user_id == current_user.id
    )
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status == StatusEnum.CANCELED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already canceled",
        )

    if order.status == StatusEnum.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid orders cannot be canceled directly",
        )

    order.status = StatusEnum.CANCELED
    await db.commit()
    await db.refresh(order)

    return {"message": f"Order {order.id} has been canceled."}
