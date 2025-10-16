import uuid
from sqlalchemy import (
    ForeignKey,
    String,
    Integer,
    Text,
    UniqueConstraint,
    Column,
    Table, Float, DECIMAL,
)
from sqlalchemy.orm import relationship
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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    movies = relationship(
        "MovieModel",
        secondary=movie_genres,
        back_populates="genres",
    )


class StarModel(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    movies = relationship(
        "MovieModel",
        secondary=movie_stars,
        back_populates="stars",
    )


class DirectorModel(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    movies = relationship(
        "MovieModel",
        secondary=movie_directors,
        back_populates="directors",
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    movies = relationship(
        "MovieModel",
        back_populates="certification",
    )


class MovieModel(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)
    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    description = Column(Text, nullable=False)
    price = Column(DECIMAL(10, 2))
    certification_id = Column(Integer, ForeignKey("certifications.id"), nullable=False)

    certification  = relationship("CertificationModel", back_populates="movies")
    genres = relationship("GenreModel", secondary=movie_genres ,back_populates="movies")
    stars = relationship("StarModel", secondary=movie_stars , back_populates="movies")
    directors = relationship("DirectorModel", secondary=movie_directors , back_populates="movies")

    __table_args__ = (
        UniqueConstraint(
            "name",
            "year",
            "time",
            name="unique_name_year_time"
        ),
    )
