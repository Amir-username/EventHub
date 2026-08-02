import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models import (
    ApiKey,
    Event,
    EventStatus,
    FeatureFlag,
    Order,
    OrderStatus,
    Reservation,
    ReservationStatus,
    TicketType,
    User,
    UserRole,
    Venue,
    WebhookEvent,
)


async def seed_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        print("Users already seeded, skipping...")
        result = await session.execute(select(User))
        return list(result.scalars().all())

    users = [
        User(
            email="admin@eventhub.com",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "password"
            full_name="Admin User",
            role=UserRole.ADMIN,
        ),
        User(
            email="alice@example.com",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            full_name="Alice Johnson",
            role=UserRole.CUSTOMER,
        ),
        User(
            email="bob@example.com",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            full_name="Bob Smith",
            role=UserRole.CUSTOMER,
        ),
    ]
    session.add_all(users)
    await session.commit()
    for u in users:
        await session.refresh(u)
    print(f"Seeded {len(users)} users")
    return users


async def seed_venues(session: AsyncSession, admin: User) -> list[Venue]:
    result = await session.execute(select(Venue).limit(1))
    if result.scalar_one_or_none():
        print("Venues already seeded, skipping...")
        result = await session.execute(select(Venue))
        return list(result.scalars().all())

    venues = [
        Venue(
            name="Madison Square Garden",
            address="4 Pennsylvania Plaza",
            city="New York",
            capacity=20789,
            created_by=admin.id,
        ),
        Venue(
            name="The O2 Arena",
            address="Peninsula Square",
            city="London",
            capacity=20000,
            created_by=admin.id,
        ),
        Venue(
            name="Tokyo Dome",
            address="1-3-61 Koraku",
            city="Tokyo",
            capacity=55000,
            created_by=admin.id,
        ),
    ]
    session.add_all(venues)
    await session.commit()
    for v in venues:
        await session.refresh(v)
    print(f"Seeded {len(venues)} venues")
    return venues


async def seed_events(
    session: AsyncSession, admin: User, venues: list[Venue]
) -> list[Event]:
    result = await session.execute(select(Event).limit(1))
    if result.scalar_one_or_none():
        print("Events already seeded, skipping...")
        result = await session.execute(select(Event))
        return list(result.scalars().all())

    now = datetime.now(UTC)
    events = [
        Event(
            venue_id=venues[0].id,
            title="Summer Music Festival 2026",
            description="A three-day outdoor music festival featuring top artists.",
            starts_at=now + timedelta(days=30),
            ends_at=now + timedelta(days=33),
            status=EventStatus.PUBLISHED,
            created_by=admin.id,
        ),
        Event(
            venue_id=venues[1].id,
            title="Tech Conference London",
            description="Annual developer conference with workshops and keynotes.",
            starts_at=now + timedelta(days=60),
            ends_at=now + timedelta(days=61),
            status=EventStatus.PUBLISHED,
            created_by=admin.id,
        ),
        Event(
            venue_id=venues[2].id,
            title="Anime Expo Tokyo",
            description="The biggest anime convention in Japan.",
            starts_at=now + timedelta(days=90),
            ends_at=now + timedelta(days=92),
            status=EventStatus.DRAFT,
            created_by=admin.id,
        ),
    ]
    session.add_all(events)
    await session.commit()
    for e in events:
        await session.refresh(e)
    print(f"Seeded {len(events)} events")
    return events


async def seed_ticket_types(
    session: AsyncSession, events: list[Event]
) -> list[TicketType]:
    result = await session.execute(select(TicketType).limit(1))
    if result.scalar_one_or_none():
        print("Ticket types already seeded, skipping...")
        result = await session.execute(select(TicketType))
        return list(result.scalars().all())

    now = datetime.now(UTC)
    ticket_types = [
        # Festival tickets
        TicketType(
            event_id=events[0].id,
            name="General Admission",
            price_cents=15000,
            currency="USD",
            total_quantity=5000,
            sales_start_at=now - timedelta(days=10),
            sales_end_at=events[0].starts_at,
        ),
        TicketType(
            event_id=events[0].id,
            name="VIP Pass",
            price_cents=45000,
            currency="USD",
            total_quantity=500,
            sales_start_at=now - timedelta(days=10),
            sales_end_at=events[0].starts_at,
        ),
        # Conference tickets
        TicketType(
            event_id=events[1].id,
            name="Early Bird",
            price_cents=29900,
            currency="GBP",
            total_quantity=200,
            sales_start_at=now - timedelta(days=5),
            sales_end_at=events[1].starts_at - timedelta(days=14),
        ),
        TicketType(
            event_id=events[1].id,
            name="Regular",
            price_cents=39900,
            currency="GBP",
            total_quantity=800,
            sales_start_at=now,
            sales_end_at=events[1].starts_at,
        ),
    ]
    session.add_all(ticket_types)
    await session.commit()
    for t in ticket_types:
        await session.refresh(t)
    print(f"Seeded {len(ticket_types)} ticket types")
    return ticket_types


async def seed_reservations(
    session: AsyncSession, users: list[User], ticket_types: list[TicketType]
) -> list[Reservation]:
    result = await session.execute(select(Reservation).limit(1))
    if result.scalar_one_or_none():
        print("Reservations already seeded, skipping...")
        result = await session.execute(select(Reservation))
        return list(result.scalars().all())

    now = datetime.now(UTC)
    reservations = [
        Reservation(
            user_id=users[1].id,
            ticket_type_id=ticket_types[0].id,
            quantity=2,
            status=ReservationStatus.CONFIRMED,
            idempotency_key="seed-res-001",
            expires_at=now + timedelta(hours=1),
        ),
        Reservation(
            user_id=users[2].id,
            ticket_type_id=ticket_types[2].id,
            quantity=1,
            status=ReservationStatus.PENDING,
            idempotency_key="seed-res-002",
            expires_at=now + timedelta(minutes=30),
        ),
    ]
    session.add_all(reservations)
    await session.commit()
    for r in reservations:
        await session.refresh(r)
    print(f"Seeded {len(reservations)} reservations")
    return reservations


async def seed_orders(
    session: AsyncSession, reservations: list[Reservation]
) -> list[Order]:
    result = await session.execute(select(Order).limit(1))
    if result.scalar_one_or_none():
        print("Orders already seeded, skipping...")
        result = await session.execute(select(Order))
        return list(result.scalars().all())

    orders = [
        Order(
            reservation_id=reservations[0].id,
            amount_cents=30000,
            status=OrderStatus.PAID,
            provider_reference="pi_3Oseed0001",
        ),
    ]
    session.add_all(orders)
    await session.commit()
    for o in orders:
        await session.refresh(o)
    print(f"Seeded {len(orders)} orders")
    return orders


async def seed_webhook_events(session: AsyncSession) -> None:
    result = await session.execute(select(WebhookEvent).limit(1))
    if result.scalar_one_or_none():
        print("Webhook events already seeded, skipping...")
        return

    now = datetime.now(UTC)
    events = [
        WebhookEvent(
            provider_event_id="evt_seed_001",
            payload='{"type":"payment_intent.succeeded","amount":30000}',
            processed_at=now,
        ),
        WebhookEvent(
            provider_event_id="evt_seed_002",
            payload='{"type":"payment_intent.created","amount":29900}',
            processed_at=None,
        ),
    ]
    session.add_all(events)
    await session.commit()
    print(f"Seeded {len(events)} webhook events")


async def seed_api_keys(session: AsyncSession) -> None:
    result = await session.execute(select(ApiKey).limit(1))
    if result.scalar_one_or_none():
        print("API keys already seeded, skipping...")
        return

    keys = [
        ApiKey(
            partner_name="Partner One",
            key_hash="sha256$seededhash001",
            scopes="events:read tickets:read",
            rate_limit_tier="standard",
        ),
        ApiKey(
            partner_name="Partner Two",
            key_hash="sha256$seededhash002",
            scopes="events:write tickets:write",
            rate_limit_tier="premium",
        ),
    ]
    session.add_all(keys)
    await session.commit()
    print(f"Seeded {len(keys)} API keys")


async def seed_feature_flags(session: AsyncSession) -> None:
    result = await session.execute(select(FeatureFlag).limit(1))
    if result.scalar_one_or_none():
        print("Feature flags already seeded, skipping...")
        return

    flags = [
        FeatureFlag(
            key="new_checkout_flow", enabled=True, rollout='{"percentage": 50}'
        ),
        FeatureFlag(key="dark_mode", enabled=False, rollout=None),
        FeatureFlag(
            key="beta_notifications",
            enabled=True,
            rollout='{"users": ["alice@example.com"]}',
        ),
    ]
    session.add_all(flags)
    await session.commit()
    print(f"Seeded {len(flags)} feature flags")


async def run_seed() -> None:
    async with AsyncSessionLocal() as session:
        users = await seed_users(session)
        admin = next(u for u in users if u.role == UserRole.ADMIN)
        venues = await seed_venues(session, admin)
        events = await seed_events(session, admin, venues)
        ticket_types = await seed_ticket_types(session, events)
        reservations = await seed_reservations(session, users, ticket_types)
        await seed_orders(session, reservations)
        await seed_webhook_events(session)
        await seed_api_keys(session)
        await seed_feature_flags(session)
    print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    asyncio.run(run_seed())
