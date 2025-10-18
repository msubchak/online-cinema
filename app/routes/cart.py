from sqlalchemy import select

from app.core.config.email_utils import get_jwt_auth_manager
from app.models.cart import CartModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.cart import CartResponseSchema, CartMovieSchema
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.security.auth_dependencies import get_current_user

router = APIRouter()


@router.get(
    "/",
    response_model=CartResponseSchema,
    summary="Get current user's cart",
    description="Returns the shopping cart of the authenticated user",
    status_code=status.HTTP_200_OK,
)
async def get_cart_by_user_id(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
) -> CartResponseSchema:
    stmt = select(CartModel).where(CartModel.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="No cart found",
        )

    movies_list = []

    for item in cart.items:
        movie_data = CartMovieSchema(
            movie_id=item.movie.id,
            name=item.movie.name,
            price=float(item.movie.price),
            added_at=item.added_at,
        )
        movies_list.append(movie_data)

    return CartResponseSchema(
        user_id=current_user.id,
        movies=movies_list,
    )
