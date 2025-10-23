from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DirectorModel
from app.schemas.directors import DirectorsListResponseSchema, DirectorsListItemSchema

router = APIRouter()


@router.get(
    "/",
    response_model=DirectorsListResponseSchema,
    summary="Retrieve all directors",
    description="Returns a paginated list of all directors with navigation links for browsing through pages.",
)
async def get_directors(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
) -> DirectorsListResponseSchema:
    offset = (page - 1) * per_page

    count_stmt = select(func.count(DirectorModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No directors found in the database",
        )

    order_by = DirectorModel.default_order_by()
    stmt = select(DirectorModel)
    if order_by:
        stmt = stmt.order_by(*order_by)

    stmt = stmt.offset(offset).limit(per_page)

    result_directors = await db.execute(stmt)
    directors = result_directors.scalars().all()

    if not directors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found - no directors available for the requested page",
        )

    directors_list = [DirectorsListItemSchema.model_validate(director) for director in directors]

    total_pages = (total_items + per_page - 1) // per_page

    return DirectorsListResponseSchema(
        directors=directors_list,
        prev_page=(
            f"/directors/?page={page - 1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/directors/?page={page + 1}&per_page={per_page}" if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
