import uuid
from decimal import Decimal
from sqlalchemy import (
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Column,
    Table,
    DECIMAL,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.Base import Base


movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)


movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("star_id", Integer, ForeignKey("stars.id"), primary_key=True),
)


movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id"), primary_key=True),
    Column("director_id", Integer, ForeignKey("directors.id"), primary_key=True),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_genres,
        back_populates="genres",
    )


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_stars,
        back_populates="stars",
    )


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_directors,
        back_populates="directors",
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        back_populates="certification",
    )


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[float | None] = mapped_column(nullable=True)
    gross: Mapped[float | None] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2))
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"), nullable=False)

    items: Mapped[list["OrderItemModel"]] = relationship(
        "OrderItemModel",
        back_populates="movie",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    certification: Mapped["CertificationModel"] = relationship(
        "CertificationModel",
        back_populates="movies",
        lazy="selectin",
    )
    genres: Mapped[list["GenreModel"]] = relationship(
        "GenreModel",
        secondary=movie_genres,
        back_populates="movies",
        lazy="selectin",
    )
    stars: Mapped[list["StarModel"]] = relationship(
        "StarModel",
        secondary=movie_stars,
        back_populates="movies",
        lazy="selectin",
    )
    directors: Mapped[list["DirectorModel"]] = relationship(
        "DirectorModel",
        secondary=movie_directors,
        back_populates="movies",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "name",
            "year",
            "time",
            name="unique_name_year_time"
        ),
    )
