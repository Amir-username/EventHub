"""Unit tests for Pydantic schema validators.

These are pure validation tests with no DB dependency.
"""

from datetime import UTC

import pytest
from pydantic import ValidationError

from app.schemas.auth import TokenPair, TokenPayload, UserLogin, UserRegister
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.ticket_type import TicketTypeCreate

# ── UserRegister ─────────────────────────────────────────────────────


async def test_register_passwords_match_accepts():
    data = UserRegister(
        email="valid@example.com",
        password="SecurePass1!",
        confirm_pass="SecurePass1!",
    )
    assert data.email == "valid@example.com"


async def test_register_passwords_mismatch_rejects():
    with pytest.raises(ValidationError, match="Passwords do not match"):
        UserRegister(
            email="valid@example.com",
            password="SecurePass1!",
            confirm_pass="DifferentPass2!",
        )


async def test_register_password_too_short_rejects():
    with pytest.raises(ValidationError):
        UserRegister(
            email="valid@example.com",
            password="short",
            confirm_pass="short",
        )


async def test_register_email_invalid_rejects():
    with pytest.raises(ValidationError):
        UserRegister(
            email="not-an-email",
            password="SecurePass1!",
            confirm_pass="SecurePass1!",
        )


async def test_register_full_name_defaults_to_none():
    data = UserRegister(
        email="valid@example.com",
        password="SecurePass1!",
        confirm_pass="SecurePass1!",
    )
    assert data.full_name is None


# ── UserLogin ────────────────────────────────────────────────────────


async def test_login_password_too_short_rejects():
    with pytest.raises(ValidationError):
        UserLogin(
            email="valid@example.com",
            password="short",
        )


# ── TicketTypeCreate ────────────────────────────────────────────────


async def test_ticket_type_create_price_negative_rejects():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TicketTypeCreate(
            event_id=1,
            name="Bad",
            price_cents=-1,
            total_quantity=100,
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=30),
        )


async def test_ticket_type_create_total_quantity_negative_rejects():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TicketTypeCreate(
            event_id=1,
            name="Bad",
            price_cents=1000,
            total_quantity=-5,
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=30),
        )


async def test_ticket_type_create_currency_wrong_length_rejects():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TicketTypeCreate(
            event_id=1,
            name="Bad",
            price_cents=1000,
            total_quantity=100,
            currency="USDD",
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=30),
        )


async def test_ticket_type_create_name_empty_rejects():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TicketTypeCreate(
            event_id=1,
            name="",
            price_cents=1000,
            total_quantity=100,
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=30),
        )


# ── EventCreate / EventUpdate ───────────────────────────────────────


async def test_event_create_title_empty_rejects():
    from datetime import datetime, timedelta

    with pytest.raises(ValidationError):
        EventCreate(
            title="",
            venue_id=1,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=2),
        )


async def test_event_create_title_too_long_rejects():
    from datetime import datetime, timedelta

    with pytest.raises(ValidationError):
        EventCreate(
            title="X" * 256,
            venue_id=1,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=2),
        )


async def test_event_update_all_none_is_valid():
    update = EventUpdate()
    assert update.title is None
    assert update.venue_id is None
    assert update.description is None
    assert update.status is None


# ── TokenPair / TokenPayload ────────────────────────────────────────


async def test_token_pair_defaults():
    pair = TokenPair(access_token="a", refresh_token="r")
    assert pair.token_type == "bearer"


async def test_token_payload_defaults():
    payload = TokenPayload(sub="42")
    assert payload.email is None
    assert payload.role is None
    assert payload.type is None
