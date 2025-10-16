from typing import Optional, Literal

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.database import get_db
from app.models.movies import MovieModel
from app.schemas.movies import MovieListResponseSchema, MovieListItemSchema

router = APIRouter()


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description="Get a paginated list of movies",
)
async def get_movie_list(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db),
        year: Optional[int] = Query(None, description="Filter by year"),
        imdb: Optional[float] = Query(None, description="Filter by imdb rating"),
        sort_by: Literal["id", "price", "time", "votes"] = Query("id"),
        order: Literal["asc", "desc"] = Query("asc"),
        search: Optional[str] = Query(
            None,
            description="Filter by name, description, stars and directors"
        )
) -> MovieListResponseSchema:
    query = select(MovieModel)

    #filter
    if year is not None:
        query = query.where(MovieModel.year == year)
    if imdb is not None:
        query = query.where(MovieModel.imdb == imdb)

    #sort
    if not hasattr(MovieModel, sort_by):
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_by}")
    column = getattr(MovieModel, sort_by)
    query = query.order_by(column.desc() if order == "desc" else column)

    #search
    if search:
        query = query.where(
            or_(
                MovieModel.name.ilike(f"%{search}%"),
                MovieModel.description.ilike(f"%{search}%"),
                MovieModel.stars.any(models.StarModel.name.ilike(f"%{search}%")),
                MovieModel.directors.any(models.DirectorModel.name.ilike(f"%{search}%")),
            )
        )

    #pagination
    total_items_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total_items = total_items_result.scalar() or 0

    total_pages = (total_items + per_page - 1) // per_page

    if total_pages == 0 or page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page
    result = await db.execute(
        query.offset(offset).limit(per_page)
    )
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies found."
        )

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            f"/movies/?page={page - 1}&per_page={per_page}"
            f"&sort_by={sort_by}&order={order}" if page > 1 else None
        ),
        next_page=(
            f"/movies/?page={page + 1}&per_page={per_page}"
            f"&sort_by={sort_by}&order={order}" if page < total_pages else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
