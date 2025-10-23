from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DirectorModel
from app.schemas.directors import DirectorsListResponseSchema, DirectorsListItemSchema, DirectorsCreateSchemas, \
    DirectorsDetailSchema

router = APIRouter()


@router.get(
    "/",
    response_model=DirectorsListResponseSchema,
    summary="Retrieve all directors",
    description="Returns a paginated list of all directors with navigation links for browsing through pages.",
    status_code=status.HTTP_200_OK,
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


@router.post(
    "/",
    response_model=DirectorsDetailSchema,
    summary="Create a new director",
    description="Creates a new director with a unique name. Returns the created director details.",
    status_code=status.HTTP_201_CREATED,
)
async def create_director(
        director_data: DirectorsCreateSchemas,
        db: AsyncSession = Depends(get_db),
) -> DirectorsDetailSchema:
    existing_stmt = select(DirectorModel).where(
        DirectorModel.name == director_data.name
    )
    result = await db.execute(existing_stmt)
    directors = result.scalars().all()

    if directors:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Director with name '{director_data.name}' already exists",
        )

    try:
        director = DirectorModel(
            name=director_data.name,
        )
        db.add(director)
        await db.commit()
        await db.refresh(director)

        return DirectorsDetailSchema.model_validate(director)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to create director due to database constraint violation"
        )


@router.get(
    "/{director_id}",
    response_model=DirectorsDetailSchema,
    summary="Get director by ID",
    description="Retrieves detailed information about a specific director by their unique ID.",
    status_code=status.HTTP_200_OK,
)
async def get_director_by_id(
        director_id: int,
        db: AsyncSession = Depends(get_db),
) -> DirectorsDetailSchema:
    stmt = select(DirectorModel).where(DirectorModel.id == director_id)
    result = await db.execute(stmt)
    director = result.scalars().first()

    if not director:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Director with ID {director_id} not found",
        )

    return DirectorsDetailSchema.model_validate(director)
