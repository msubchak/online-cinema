from datetime import datetime
from typing import List
from pydantic import BaseModel


class CartMovieSchema(BaseModel):
    movie_id: int
    name: str
    price: float
    added_at: datetime

    class Config:
        from_attributes = True


class CartResponseSchema(BaseModel):
    user_id: int
    movies: List[CartMovieSchema]
