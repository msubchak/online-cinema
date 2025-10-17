from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.movies import StarModel
from app.schemas.stars import StarListResponseSchema, StarListItemSchema


router = APIRouter()


@router.get(
    "/",
    response_model=StarListResponseSchema,
    summary="Get a paginated list of stars",
    description="Get a paginated list of stars",
)
async def get_stars(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
) -> StarListResponseSchema:
    offset = (page - 1) * per_page

    count_stmt = select(func.count(StarModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stars found",
        )

    stmt = select(StarModel).order_by(StarModel.id).offset(offset).limit(per_page)
    result_stars = await db.execute(stmt)
    stars = result_stars.scalars().all()

    if not stars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stars found",
        )

    stars_list = [StarListItemSchema.model_validate(star, from_attributes=True) for star in stars]

    total_pages = (total_items + per_page - 1) // per_page

    return StarListResponseSchema(
        stars=stars_list,
        prev_page=(
            f"/stars/?page={page - 1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/stars/?page={page + 1}&per_page={per_page}" if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
