from typing import List, Optional
from pydantic import BaseModel


class GenresListItemSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class GenresCreateSchemas(BaseModel):
    name: str


class GenresListResponseSchema(BaseModel):
    genres: List[GenresListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


class GenresDetailSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class GenreUpdateSchema(BaseModel):
    name: Optional[str]
