from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    imdb: float
    description: str

    model_config = {
        "from_attributes": True
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True
    }


class MovieCreateSchema(BaseModel):
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float
    gross: float
    description: str
    price: float
    certification: str
    genres: List[str]
    stars: List[str]
    directors: List[str]

    model_config = {
        "from_attributes": True
    }

    @field_validator("year")
    @classmethod
    def validate_year(cls, value):
        current_year = datetime.now().year
        if value > current_year + 1:
            raise ValueError(
                f"The year in 'date' cannot be greater than "
                f"{current_year + 1}."
            )
        return value


class MovieDetailSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float]
    gross: Optional[float]
    description: str
    price: float
    certification: CertificationSchema
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]

    model_config = {
        "from_attributes": True
    }


class MovieUpdateSchema(BaseModel):
    name: Optional[str]
    year: Optional[int]
    time: Optional[int]
    imdb: Optional[float]
    votes: Optional[int]
    meta_score: Optional[float]
    gross: Optional[float]
    description: Optional[str]
    price: Optional[float]
