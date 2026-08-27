from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.reservation import ReservationStatus
from app.repositories.reservation_repository import ReservationRepository


def _reservation_window_minutes() -> int:
    """How long a reservation holds tickets before expiring.

    Reads from settings so it can be tuned per-environment without a
    code change.
    """
    settings = get_settings()
    return getattr(settings, "reservation_window_minutes", 10)


class ReservationService:
    def __init__(self, db: AsyncSession):
        self.repo = ReservationRepository(db)

    # -- Customer-facing --

    async def create_reservation(
        self,
        *,
        user_id: int,
        ticket_type_id: int,
        quantity: int,
        idempotency_key: str,
    ):
        """Create a new ticket reservation.

        Business rules enforced here (not in the repository):
        - quantity must be positive
        - computes ``expires_at`` from the configurable window
        """
        if quantity <= 0:
            raise ValueError("Quantity must be at least 1")

        expires_at = datetime.now(UTC) + timedelta(
            minutes=_reservation_window_minutes()
        )
        return await self.repo.create(
            user_id=user_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )

    async def get_reservation(self, reservation_id: int):
        reservation = await self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("Reservation not found")
        return reservation

    async def list_my_reservations(
        self,
        *,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
        status: ReservationStatus | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_by_user(
            user_id=user_id, offset=offset, limit=limit, status=status
        )

    async def cancel_reservation(self, reservation_id: int, user_id: int):
        """Cancel a pending reservation, but only if the caller owns it."""
        reservation = await self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("Reservation not found")
        if reservation.user_id != user_id:
            raise ValueError("Not your reservation")
        return await self.repo.cancel(reservation)

    # -- Admin / internal --

    async def list_all_reservations(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: ReservationStatus | None = None,
        user_id: int | None = None,
        ticket_type_id: int | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(
            offset=offset,
            limit=limit,
            status=status,
            user_id=user_id,
            ticket_type_id=ticket_type_id,
        )

    async def confirm_reservation(self, reservation_id: int):
        """Confirm a reservation (called after payment succeeds)."""
        reservation = await self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("Reservation not found")
        return await self.repo.confirm(reservation)

    async def expire_reservation(self, reservation_id: int):
        """Expire a single reservation (called by the background worker)."""
        reservation = await self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("Reservation not found")
        return await self.repo.expire(reservation)
