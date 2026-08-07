from pydantic import BaseModel, Field


class CreatorBrief(BaseModel):
    id: int
    full_name: str | None

    model_config = {"from_attributes": True}


class VenueRead(BaseModel):
    id: int
    name: str
    address: str
    city: str
    capacity: int
    created_by: int
    creator: CreatorBrief

    model_config = {"from_attributes": True}


class PaginatedVenues(BaseModel):
    items: list[VenueRead]
    total: int
    offset: int
    limit: int


class VenueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    capacity: int = Field(gt=0)


class VenueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int | None = Field(default=None, gt=0)
