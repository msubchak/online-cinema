from datetime import datetime
from typing import List
from pydantic import BaseModel


class OrderMovieSchema(BaseModel):
    movie_id: int
    name: str
    price_at_order: float


class OrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    status: str
    total_amount: float
    items: List[OrderMovieSchema]
