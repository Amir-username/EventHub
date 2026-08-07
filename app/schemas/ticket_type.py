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

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "event_id": 1,
                    "event": {
                        "id": 1,
                        "title": "Summer Jazz Night",
                        "status": "published",
                    },
                    "name": "VIP Front Row",
                    "price_cents": 15000,
                    "currency": "USD",
                    "total_quantity": 100,
                    "reserved_quantity": 12,
                    "sold_quantity": 45,
                    "sales_start_at": "2026-08-01T00:00:00Z",
                    "sales_end_at": "2026-09-14T23:59:59Z",
                }
            ]
        },
    }


class PaginatedTicketTypes(BaseModel):
    items: list[TicketTypeRead]
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
                            "event_id": 1,
                            "event": {
                                "id": 1,
                                "title": "Summer Jazz Night",
                                "status": "published",
                            },
                            "name": "VIP Front Row",
                            "price_cents": 15000,
                            "currency": "USD",
                            "total_quantity": 100,
                            "reserved_quantity": 12,
                            "sold_quantity": 45,
                            "sales_start_at": "2026-08-01T00:00:00Z",
                            "sales_end_at": "2026-09-14T23:59:59Z",
                        }
                    ],
                    "total": 3,
                    "offset": 0,
                    "limit": 20,
                }
            ]
        }
    }


class TicketTypeCreate(BaseModel):
    event_id: int = Field(..., json_schema_extra={"examples": [1]})
    name: str = Field(
        min_length=1, max_length=255, json_schema_extra={"examples": ["VIP Front Row"]}
    )
    price_cents: int = Field(ge=0, json_schema_extra={"examples": [15000]})
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        json_schema_extra={"examples": ["USD"]},
    )
    total_quantity: int = Field(ge=0, json_schema_extra={"examples": [100]})
    sales_start_at: datetime = Field(
        ..., json_schema_extra={"examples": ["2026-08-01T00:00:00Z"]}
    )
    sales_end_at: datetime = Field(
        ..., json_schema_extra={"examples": ["2026-09-14T23:59:59Z"]}
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": 1,
                    "name": "VIP Front Row",
                    "price_cents": 15000,
                    "currency": "USD",
                    "total_quantity": 100,
                    "sales_start_at": "2026-08-01T00:00:00Z",
                    "sales_end_at": "2026-09-14T23:59:59Z",
                }
            ]
        }
    }


class TicketTypeUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["General Admission"]},
    )
    price_cents: int | None = Field(
        default=None, ge=0, json_schema_extra={"examples": [5000]}
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        json_schema_extra={"examples": ["EUR"]},
    )
    total_quantity: int | None = Field(
        default=None, ge=0, json_schema_extra={"examples": [500]}
    )
    sales_start_at: datetime | None = Field(
        default=None, json_schema_extra={"examples": ["2026-08-15T00:00:00Z"]}
    )
    sales_end_at: datetime | None = Field(
        default=None, json_schema_extra={"examples": ["2026-09-14T23:59:59Z"]}
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "price_cents": 5000,
                    "total_quantity": 500,
                }
            ]
        }
    }
