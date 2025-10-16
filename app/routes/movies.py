from sqlalchemy.exc import IntegrityError
from typing import Optional, Literal

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app import models
from app.core.database import get_db
from app.models.movies import MovieModel, CertificationModel, GenreModel, StarModel, DirectorModel
from app.schemas.movies import MovieListResponseSchema, MovieListItemSchema, MovieCreateSchema, MovieDetailSchema

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


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Add a new movie.",
    description="Add a new movie.",
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    existing_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name),
        (MovieModel.time == movie_data.time)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A movie with the name '{movie_data.name}' and release date "
                f"'{movie_data.time}' already exists."
            )
        )

    try:
        certification_stmt = select(CertificationModel).where(
            CertificationModel.name == movie_data.certification
        )
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()
        if not certification:
            certification = CertificationModel(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(GenreModel).where(GenreModel.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()

            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(StarModel).where(StarModel.name == star_name)
            star_result = await db.execute(star_stmt)
            star = star_result.scalars().first()

            if not star:
                star = StarModel(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(DirectorModel).where(DirectorModel.name == director_name)
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()

            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors"])

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input data"
        )


@router.get(
    "/{movie_id}",
    response_model=MovieDetailSchema,
    summary="Get movie detail by ID",
    description="Fetch detailed information about a specific movie by its unique ID."
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
    .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found."
        )

    return MovieDetailSchema.model_validate(movie)
