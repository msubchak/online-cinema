from typing import List, Optional
from pydantic import BaseModel


class StarListItemSchema(BaseModel):
    id: int
    name: str


class StarListResponseSchema(BaseModel):
    stars: List[StarListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True
    }


class StarCreateSchemas(BaseModel):
    name: str


class StarDetailSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True
    }
