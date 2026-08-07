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

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "venue_id": 1,
                    "venue": {
                        "id": 1,
                        "name": "Madison Square Garden",
                        "city": "New York",
                    },
                    "title": "Summer Jazz Night",
                    "description": "An evening of smooth jazz under the stars with world-class musicians.",
                    "starts_at": "2026-09-15T19:00:00Z",
                    "ends_at": "2026-09-15T23:00:00Z",
                    "status": "published",
                    "created_by": 1,
                    "creator": {"id": 1, "full_name": "Admin"},
                    "created_at": "2026-08-01T10:30:00Z",
                }
            ]
        },
    }


class PaginatedEvents(BaseModel):
    items: list[EventRead]
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
                            "venue_id": 1,
                            "venue": {
                                "id": 1,
                                "name": "Madison Square Garden",
                                "city": "New York",
                            },
                            "title": "Summer Jazz Night",
                            "description": "An evening of smooth jazz under the stars with world-class musicians.",
                            "starts_at": "2026-09-15T19:00:00Z",
                            "ends_at": "2026-09-15T23:00:00Z",
                            "status": "published",
                            "created_by": 1,
                            "creator": {"id": 1, "full_name": "Admin"},
                            "created_at": "2026-08-01T10:30:00Z",
                        }
                    ],
                    "total": 42,
                    "offset": 0,
                    "limit": 20,
                }
            ]
        }
    }


class EventCreate(BaseModel):
    venue_id: int = Field(..., json_schema_extra={"examples": [1]})
    title: str = Field(
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["Summer Jazz Night"]},
    )
    description: str | None = Field(
        default=None,
        json_schema_extra={
            "examples": [
                "An evening of smooth jazz under the stars with world-class musicians."
            ]
        },
    )
    starts_at: datetime = Field(
        ..., json_schema_extra={"examples": ["2026-09-15T19:00:00Z"]}
    )
    ends_at: datetime = Field(
        ..., json_schema_extra={"examples": ["2026-09-15T23:00:00Z"]}
    )
    status: str = Field(default="draft", json_schema_extra={"examples": ["draft"]})

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "venue_id": 1,
                    "title": "Summer Jazz Night",
                    "description": "An evening of smooth jazz under the stars with world-class musicians.",
                    "starts_at": "2026-09-15T19:00:00Z",
                    "ends_at": "2026-09-15T23:00:00Z",
                    "status": "draft",
                }
            ]
        }
    }


class EventUpdate(BaseModel):
    venue_id: int | None = Field(default=None, json_schema_extra={"examples": [2]})
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["Winter Comedy Fest"]},
    )
    description: str | None = Field(
        default=None,
        json_schema_extra={"examples": ["A hilarious lineup of stand-up comedians."]},
    )
    starts_at: datetime | None = Field(
        default=None, json_schema_extra={"examples": ["2026-12-20T20:00:00Z"]}
    )
    ends_at: datetime | None = Field(
        default=None, json_schema_extra={"examples": ["2026-12-20T23:30:00Z"]}
    )
    status: str | None = Field(
        default=None, json_schema_extra={"examples": ["published"]}
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Winter Comedy Fest",
                    "description": "A hilarious lineup of stand-up comedians.",
                    "status": "published",
                }
            ]
        }
    }
