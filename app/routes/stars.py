from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.movies import StarModel
from app.schemas.stars import (
    StarListResponseSchema,
    StarListItemSchema,
    StarDetailSchema,
    StarCreateSchemas,
    StarUpdateSchema
)

router = APIRouter()


@router.get(
    "/",
    response_model=StarListResponseSchema,
    summary="Retrieve a paginated list of stars",
    description="Return a paginated list of all available stars.",
    status_code=status.HTTP_200_OK,
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
            detail="No stars found in the database.",
        )

    stmt = (select(StarModel)
            .order_by(StarModel.id)
            .offset(offset)
            .limit(per_page))
    result_stars = await db.execute(stmt)
    stars = result_stars.scalars().all()

    if not stars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stars found on page {page}.",
        )

    stars_list = [
        StarListItemSchema.model_validate(
            star, from_attributes=True
        ) for star in stars
    ]

    total_pages = (total_items + per_page - 1) // per_page

    return StarListResponseSchema(
        stars=stars_list,
        prev_page=(
            f"/stars/?page={page - 1}&per_page={per_page}"
            if page > 1 else None
        ),
        next_page=(
            f"/stars/?page={page + 1}&per_page={per_page}"
            if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get(
    "/{star_id}",
    response_model=StarDetailSchema,
    summary="Get star details by ID",
    description="Retrieve detailed information about a star by its unique ID.",
    status_code=status.HTTP_200_OK,
)
async def get_star_by_id(
        star_id: int,
        db: AsyncSession = Depends(get_db),
) -> StarDetailSchema:
    stmt = select(StarModel).where(StarModel.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Star with ID '{star_id}' not found.",
        )

    return StarDetailSchema.model_validate(star, from_attributes=True)


@router.post(
    "/",
    response_model=StarDetailSchema,
    summary="Create a new star",
    description="Add a new star to the database. "
                "If a star with the same name already exists, "
                "a 409 error will be returned.",
    status_code=status.HTTP_201_CREATED,
)
async def create_star(
        star_data: StarCreateSchemas,
        db: AsyncSession = Depends(get_db),
) -> StarDetailSchema:
    existing_stmt = select(StarModel).where(
        StarModel.name == star_data.name,
    )
    existing_result = await db.execute(existing_stmt)
    existing_star = existing_result.scalars().first()

    if existing_star:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The star '{star_data.name}' already exists.",
        )

    try:
        star = StarModel(
            name=star_data.name
        )
        db.add(star)
        await db.commit()
        await db.refresh(star)

        return StarDetailSchema.model_validate(star)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid star data. Please verify your input and try again."
        )


@router.patch(
    "/{star_id}",
    summary="Update a star by ID",
    description="Update one or more fields of an existing star "
                "using its unique ID.",
    status_code=status.HTTP_200_OK,
)
async def update_star(
        star_id: int,
        star_data: StarUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    stmt = select(StarModel).where(StarModel.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Star with ID '{star_id}' not found.",
        )

    for field, value in star_data.model_dump(exclude_unset=True).items():
        setattr(star, field, value)

    if star_data.name:
        existing_stmt = select(StarModel).where(
            StarModel.name == star_data.name,
            StarModel.id != star_id
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A star named '{star_data.name}' already exists.",
            )

    try:
        await db.commit()
        await db.refresh(star)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid or duplicate star data."
        )

    return {"detail": "Star updated successfully."}


@router.delete(
    "/{star_id}",
    summary="Delete a star by ID",
    description="Remove a star from the database by its unique ID.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_star(
        star_id: int,
        db: AsyncSession = Depends(get_db),
):
    stmt = select(StarModel).where(StarModel.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Star with ID '{star_id}' not found.",
        )

    await db.delete(star)
    await db.commit()
    return
