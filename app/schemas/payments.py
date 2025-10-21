from datetime import datetime
from typing import List
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
from app.models.payments import StatusEnum


class PaymentItemSchema(BaseModel):
    order_item_id: int
    price_at_payment: Decimal

    model_config = {
        "from_attributes": True
    }


class PaymentResponseSchema(BaseModel):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    status: StatusEnum
    amount: Decimal
    external_payment_id: Optional[str] = None
    items: List[PaymentItemSchema]

    model_config = {
        "from_attributes": True
    }


class PaymentRequestSchema(BaseModel):
    order_id: int
    external_payment_id: Optional[str] = None
