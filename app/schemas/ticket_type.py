from datetime import datetime

from pydantic import BaseModel, Field


class EventBrief(BaseModel):
    id: int
    title: str
    status: str

    model_config = {"from_attributes": True}


class TicketTypeRead(BaseModel):
    id: int
    event_id: int
    event: EventBrief
    name: str
    price_cents: int
    currency: str
    total_quantity: int
    reserved_quantity: int
    sold_quantity: int
    sales_start_at: datetime
    sales_end_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTicketTypes(BaseModel):
    items: list[TicketTypeRead]
    total: int
    offset: int
    limit: int


class TicketTypeCreate(BaseModel):
    event_id: int
    name: str = Field(min_length=1, max_length=255)
    price_cents: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    total_quantity: int = Field(ge=0)
    sales_start_at: datetime
    sales_end_at: datetime


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    total_quantity: int | None = Field(default=None, ge=0)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
