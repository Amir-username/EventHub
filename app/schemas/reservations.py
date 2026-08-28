from datetime import datetime

from pydantic import BaseModel, Field


class EventBrief(BaseModel):
    id: int
    title: str

    model_config = {"from_attributes": True}


class TicketTypeBrief(BaseModel):
    id: int
    name: str
    price_cents: int
    currency: str
    event: EventBrief

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    id: int
    email: str
    full_name: str | None

    model_config = {"from_attributes": True}


class ReservationRead(BaseModel):
    id: int
    user_id: int
    ticket_type_id: int
    ticket_type: TicketTypeBrief
    quantity: int
    status: str
    idempotency_key: str
    expires_at: datetime
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "user_id": 2,
                    "ticket_type_id": 3,
                    "ticket_type": {
                        "id": 3,
                        "name": "VIP Front Row",
                        "price_cents": 15000,
                        "currency": "USD",
                        "event": {"id": 1, "title": "Summer Jazz Night"},
                    },
                    "quantity": 2,
                    "status": "pending",
                    "idempotency_key": "req_abc123",
                    "expires_at": "2026-08-27T11:10:00Z",
                    "created_at": "2026-08-27T11:00:00Z",
                }
            ]
        },
    }


class ReservationReadWithUser(ReservationRead):
    user: UserBrief

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "user_id": 2,
                    "ticket_type_id": 3,
                    "ticket_type": {
                        "id": 3,
                        "name": "VIP Front Row",
                        "price_cents": 15000,
                        "currency": "USD",
                        "event": {"id": 1, "title": "Summer Jazz Night"},
                    },
                    "quantity": 2,
                    "status": "pending",
                    "idempotency_key": "req_abc123",
                    "expires_at": "2026-08-27T11:10:00Z",
                    "created_at": "2026-08-27T11:00:00Z",
                    "user": {
                        "id": 2,
                        "email": "jane@example.com",
                        "full_name": "Jane Doe",
                    },
                }
            ]
        },
    }


class PaginatedReservations(BaseModel):
    items: list[ReservationRead]
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
                            "user_id": 2,
                            "ticket_type_id": 3,
                            "ticket_type": {
                                "id": 3,
                                "name": "VIP Front Row",
                                "price_cents": 15000,
                                "currency": "USD",
                                "event": {
                                    "id": 1,
                                    "title": "Summer Jazz Night",
                                },
                            },
                            "quantity": 2,
                            "status": "pending",
                            "idempotency_key": "req_abc123",
                            "expires_at": "2026-08-27T11:10:00Z",
                            "created_at": "2026-08-27T11:00:00Z",
                        }
                    ],
                    "total": 5,
                    "offset": 0,
                    "limit": 20,
                }
            ]
        }
    }


class PaginatedAdminReservations(BaseModel):
    items: list[ReservationReadWithUser]
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
                            "user_id": 2,
                            "ticket_type_id": 3,
                            "ticket_type": {
                                "id": 3,
                                "name": "VIP Front Row",
                                "price_cents": 15000,
                                "currency": "USD",
                                "event": {
                                    "id": 1,
                                    "title": "Summer Jazz Night",
                                },
                            },
                            "quantity": 2,
                            "status": "pending",
                            "idempotency_key": "req_abc123",
                            "expires_at": "2026-08-27T11:10:00Z",
                            "created_at": "2026-08-27T11:00:00Z",
                            "user": {
                                "id": 2,
                                "email": "jane@example.com",
                                "full_name": "Jane Doe",
                            },
                        }
                    ],
                    "total": 42,
                    "offset": 0,
                    "limit": 20,
                }
            ]
        }
    }


class ReservationCreate(BaseModel):
    ticket_type_id: int = Field(..., json_schema_extra={"examples": [3]})
    quantity: int = Field(gt=0, json_schema_extra={"examples": [2]})
    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
        json_schema_extra={"examples": ["req_abc123"]},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticket_type_id": 3,
                    "quantity": 2,
                    "idempotency_key": "req_abc123",
                }
            ]
        }
    }
