from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.movies import GenreModel
from app.schemas.genres import GenresListResponseSchema, GenresListItemSchema, GenresCreateSchemas, GenresDetailSchema, \
    GenreUpdateSchema

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


@router.post(
    "/",
    response_model=GenresDetailSchema,
    summary="Add a new genre",
    description="Add a new genre",
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
            detail="A genre with the same name already exists",
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
            detail="Invalid input data."
        )


@router.get(
    "/{genre_id}/",
    response_model=GenresDetailSchema,
    summary="Get genre details by ID.",
    description="Get genre details by ID",
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
            detail="No genres found",
        )

    return GenresDetailSchema.model_validate(genre)


@router.patch(
    "/{genre_id}",
    summary="Update genre detail by ID",
    description="Update details of a specific genre by its unique ID."
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
            detail="No genres found",
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
            raise HTTPException(status_code=409, detail="A genre with the same name already exists")

    try:
        await db.commit()
        await db.refresh(genre)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Genre updated successfully."}


@router.delete(
    "/{genre_id}",
    summary="Delete genre by ID",
    description="Delete a specific genre by its unique ID.",
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
            detail="No genres found",
        )

    await db.delete(genre)
    await db.commit()
    return
