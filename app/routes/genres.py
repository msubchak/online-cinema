from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.movies import GenreModel
from app.schemas.genres import (
    GenresListResponseSchema,
    GenresListItemSchema,
    GenresCreateSchemas,
    GenresDetailSchema,
    GenreUpdateSchema
)

router = APIRouter()


@router.get(
    "/",
    response_model=GenresListResponseSchema,
    summary="Retrieve a paginated list of genres",
    description="Return a paginated list of all available genres.",
    status_code=status.HTTP_200_OK,
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
            detail="No genres found in the database.",
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
            detail="No genres found in the database.",
        )

    genres_list = [
        GenresListItemSchema.model_validate(genre)
        for genre in genres
    ]

    total_pages = (total_items + per_page - 1) // per_page

    return GenresListResponseSchema(
        genres=genres_list,
        prev_page=(
            f"/genres/?page={page - 1}&per_page={per_page}"
            if page > 1 else None
        ),
        next_page=(
            f"/genres/?page={page + 1}&per_page={per_page}"
            if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get(
    "/{genre_id}/",
    response_model=GenresDetailSchema,
    summary="Get genre details by ID",
    description="Retrieve detailed information "
                "about a genre by its unique ID.",
    status_code=status.HTTP_200_OK,
)
async def get_genre_by_id(
        genre_id: int,
        db: AsyncSession = Depends(get_db),
) -> GenresDetailSchema:
    stmt = select(GenreModel).where(GenreModel.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Genre with ID '{genre_id}' not found.",
        )

    return GenresDetailSchema.model_validate(genre)


@router.post(
    "/",
    response_model=GenresDetailSchema,
    summary="Create a new genre",
    description="Add a new genre to the database. "
                "If a genre with the same name already exists, "
                "a 409 error will be returned.",
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(
        genre_data: GenresCreateSchemas,
        db: AsyncSession = Depends(get_db),
) -> GenresDetailSchema:
    existing_stmt = select(GenreModel).where(
        (GenreModel.name == genre_data.name)
    )
    existing_result = await db.execute(existing_stmt)
    existing_genre = existing_result.scalars().first()

    if existing_genre:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The genre '{genre_data.name}' already exists.",
        )

    try:
        genre = GenreModel(
            name=genre_data.name
        )
        db.add(genre)
        await db.commit()
        await db.refresh(genre)

        return GenresDetailSchema.model_validate(genre)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid genre data. "
                   "Please verify your input and try again."
        )


@router.patch(
    "/{genre_id}",
    summary="Update a genre by ID",
    description="Update one or more fields of "
                "an existing genre using its unique ID.",
    status_code=status.HTTP_200_OK,
)
async def update_genre(
        genre_id: int,
        genre_data: GenreUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    stmt = select(GenreModel).where(GenreModel.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Genre with ID '{genre_id}' not found.",
        )

    for field, value in genre_data.model_dump(exclude_unset=True).items():
        setattr(genre, field, value)

    if genre_data.name:
        existing_stmt = select(GenreModel).where(
            GenreModel.name == genre_data.name,
            GenreModel.id != genre_id
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A genre named '{genre_data.name}' already exists."
            )

    try:
        await db.commit()
        await db.refresh(genre)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid or duplicate genre data."
        )

    return {"detail": "Genre updated successfully."}


@router.delete(
    "/{genre_id}",
    summary="Delete a genre by ID",
    description="Remove a genre from the database by its unique ID.",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_genre(
        genre_id: int,
        db: AsyncSession = Depends(get_db),
):
    stmt = select(GenreModel).where(GenreModel.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().one_or_none()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Genre with ID '{genre_id}' not found.",
        )

    await db.delete(genre)
    await db.commit()
    return
