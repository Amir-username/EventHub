from datetime import datetime

from pydantic import BaseModel, Field


class VenueBrief(BaseModel):
    id: int
    name: str
    city: str

    model_config = {"from_attributes": True}


class CreatorBrief(BaseModel):
    id: int
    full_name: str | None

    model_config = {"from_attributes": True}


class EventRead(BaseModel):
    id: int
    venue_id: int
    venue: VenueBrief
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    created_by: int
    creator: CreatorBrief
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedEvents(BaseModel):
    items: list[EventRead]
    total: int
    offset: int
    limit: int


class EventCreate(BaseModel):
    venue_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    status: str = "draft"


class EventUpdate(BaseModel):
    venue_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None
