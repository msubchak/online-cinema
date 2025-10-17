from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.movies import GenreModel
from app.schemas.genres import GenresListResponseSchema, GenresListItemSchema

router = APIRouter()


@router.get(
    "/",
    response_model=GenresListResponseSchema,
    summary="Get a paginated list of genres",
    description="Get a paginated list of genres",
)
async def get_genres(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
) -> GenresListResponseSchema:
    offset = (page - 1) * per_page

    count_stmt = select(func.count(GenreModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genres found",
        )

    order_by = GenreModel.default_order_by()
    stmt = select(GenreModel)
    if order_by:
        stmt = stmt.order_by(*order_by)

    stmt = stmt.offset(offset).limit(per_page)

    result_genres = await db.execute(stmt)
    genres = result_genres.scalars().all()

    if not genres:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No genres found",
        )

    genres_list = [GenresListItemSchema.model_validate(genre) for genre in genres]

    total_pages = (total_items + per_page - 1) // per_page

    return GenresListResponseSchema(
        genres=genres_list,
        prev_page=(
            f"/genres/?page={page - 1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/genres/?page={page + 1}&per_page={per_page}" if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
