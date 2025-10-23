from typing import List, Optional
from pydantic import BaseModel


class DirectorsListItemSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class DirectorsCreateSchemas(BaseModel):
    name: str


class DirectorsListResponseSchema(BaseModel):
    directors: List[DirectorsListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


class DirectorsDetailSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }


class DirectorsUpdateSchema(BaseModel):
    name: Optional[str]
