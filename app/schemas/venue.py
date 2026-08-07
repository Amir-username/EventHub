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

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Madison Square Garden",
                    "address": "4 Pennsylvania Plaza, New York, NY 10001",
                    "city": "New York",
                    "capacity": 20800,
                    "created_by": 1,
                    "creator": {"id": 1, "full_name": "Admin"},
                }
            ]
        },
    }


class PaginatedVenues(BaseModel):
    items: list[VenueRead]
    total: int
    offset: int
    limit: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "name": "Madison Square Garden",
                            "address": "4 Pennsylvania Plaza, New York, NY 10001",
                            "city": "New York",
                            "capacity": 20800,
                            "created_by": 1,
                            "creator": {"id": 1, "full_name": "Admin"},
                        }
                    ],
                    "total": 15,
                    "offset": 0,
                    "limit": 20,
                }
            ]
        }
    }


class VenueCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["Madison Square Garden"]},
    )
    address: str = Field(
        min_length=1,
        max_length=500,
        json_schema_extra={"examples": ["4 Pennsylvania Plaza, New York, NY 10001"]},
    )
    city: str = Field(
        min_length=1, max_length=100, json_schema_extra={"examples": ["New York"]}
    )
    capacity: int = Field(gt=0, json_schema_extra={"examples": [20800]})

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Madison Square Garden",
                    "address": "4 Pennsylvania Plaza, New York, NY 10001",
                    "city": "New York",
                    "capacity": 20800,
                }
            ]
        }
    }


class VenueUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["Barclays Center"]},
    )
    address: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        json_schema_extra={"examples": ["620 Atlantic Ave, Brooklyn, NY 11217"]},
    )
    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        json_schema_extra={"examples": ["Brooklyn"]},
    )
    capacity: int | None = Field(
        default=None, gt=0, json_schema_extra={"examples": [17732]}
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Barclays Center",
                    "capacity": 17732,
                }
            ]
        }
    }
