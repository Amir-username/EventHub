from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reservation import Reservation, ReservationStatus
from app.models.ticket_type import TicketType


class ReservationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # -- Read --

    async def get_by_id(self, reservation_id: int) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation)
            .options(
                selectinload(Reservation.ticket_type).selectinload(TicketType.event),
                selectinload(Reservation.user),
            )
            .where(Reservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(Reservation.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        *,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
        status: ReservationStatus | None = None,
    ) -> tuple[list[Reservation], int]:
        base = select(Reservation).where(Reservation.user_id == user_id)
        count_q = (
            select(func.count())
            .select_from(Reservation)
            .where(Reservation.user_id == user_id)
        )

        if status is not None:
            base = base.where(Reservation.status == status)
            count_q = count_q.where(Reservation.status == status)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(
                selectinload(Reservation.ticket_type).selectinload(TicketType.event),
            )
            .order_by(Reservation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: ReservationStatus | None = None,
        user_id: int | None = None,
        ticket_type_id: int | None = None,
    ) -> tuple[list[Reservation], int]:
        base = select(Reservation)
        count_q = select(func.count()).select_from(Reservation)

        if status is not None:
            base = base.where(Reservation.status == status)
            count_q = count_q.where(Reservation.status == status)
        if user_id is not None:
            base = base.where(Reservation.user_id == user_id)
            count_q = count_q.where(Reservation.user_id == user_id)
        if ticket_type_id is not None:
            base = base.where(Reservation.ticket_type_id == ticket_type_id)
            count_q = count_q.where(Reservation.ticket_type_id == ticket_type_id)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = (
            base.options(
                selectinload(Reservation.ticket_type).selectinload(TicketType.event),
                selectinload(Reservation.user),
            )
            .order_by(Reservation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def list_expired_pending(
        self,
        *,
        now: datetime,
        batch_size: int = 100,
    ) -> list[Reservation]:
        """Return pending reservations whose expiry time has passed.

        Used by the background expiry worker.  The *batch_size* caps each
        sweep so a single worker tick never processes an unbounded number.
        """
        result = await self.db.execute(
            select(Reservation)
            .options(selectinload(Reservation.ticket_type))
            .where(
                Reservation.status == ReservationStatus.PENDING,
                Reservation.expires_at < now,
            )
            .order_by(Reservation.expires_at.asc())
            .limit(batch_size)
        )
        return list(result.scalars().all())

    # -- Write --

    async def create(
        self,
        *,
        user_id: int,
        ticket_type_id: int,
        quantity: int,
        idempotency_key: str,
        expires_at: datetime,
    ) -> Reservation:
        """Reserve *quantity* tickets of *ticket_type_id* for *user_id*.

        Uses ``SELECT … FOR UPDATE`` on the ``ticket_types`` row so that
        concurrent reservation attempts for the same ticket type are
        serialised.  The lock is held until the transaction commits.

        Returns the new (or existing, if idempotent) ``Reservation``.
        Raises ``ValueError`` when tickets are unavailable or sales are
        not open.
        """
        # ---- idempotency check ----
        existing = await self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            # If the previous reservation is in a terminal state the
            # caller should use a *new* idempotency key.  Surface this
            # as a clear error rather than silently returning a dead
            # reservation.
            if existing.status in (
                ReservationStatus.EXPIRED,
                ReservationStatus.CANCELLED,
            ):
                raise ValueError(
                    "Idempotency key was already used for an expired or "
                    "cancelled reservation. Use a new key."
                )
            return existing

        # ---- lock the ticket_type row ----
        result = await self.db.execute(
            select(TicketType).where(TicketType.id == ticket_type_id).with_for_update()
        )
        ticket_type = result.scalar_one_or_none()
        if ticket_type is None:
            raise ValueError("Ticket type not found")

        # ---- availability check ----
        if ticket_type.reserved_quantity + quantity > ticket_type.total_quantity:
            raise ValueError("Not enough tickets available")

        # ---- sale window check ----
        now = datetime.now(UTC)
        if now < ticket_type.sales_start_at:
            raise ValueError("Ticket sales have not started yet")
        if now > ticket_type.sales_end_at:
            raise ValueError("Ticket sales have ended")

        # ---- update counter ----
        ticket_type.reserved_quantity += quantity

        # ---- insert reservation ----
        reservation = Reservation(
            user_id=user_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            status=ReservationStatus.PENDING,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        self.db.add(reservation)

        # commit flushes both the ticket_type UPDATE and the reservation
        # INSERT atomically, then releases the FOR UPDATE lock.
        await self.db.commit()
        return await self.get_by_id(reservation.id)  # type: ignore[return-value]

    async def cancel(self, reservation: Reservation) -> Reservation:
        """Cancel a pending reservation and release the held tickets.

        Locks the ``ticket_types`` row to keep the counter update
        consistent with concurrent reservations.
        Raises ``ValueError`` if the reservation is not in PENDING state.
        """
        if reservation.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot cancel a reservation with status '{reservation.status.value}'"
            )

        # Lock the ticket_type row
        result = await self.db.execute(
            select(TicketType)
            .where(TicketType.id == reservation.ticket_type_id)
            .with_for_update()
        )
        ticket_type = result.scalar_one()

        # Release the held tickets
        ticket_type.reserved_quantity -= reservation.quantity
        reservation.status = ReservationStatus.CANCELLED

        self.db.add(reservation)
        await self.db.commit()
        return await self.get_by_id(reservation.id)  # type: ignore[return-value]

    async def confirm(self, reservation: Reservation) -> Reservation:
        """Confirm a pending reservation (payment succeeded).

        Moves the ticket count from *reserved* to *sold* on the
        ``ticket_types`` row.  The row is locked for consistency.
        Raises ``ValueError`` if the reservation is not PENDING.
        """
        if reservation.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot confirm a reservation with status '{reservation.status.value}'"
            )

        # Lock the ticket_type row
        result = await self.db.execute(
            select(TicketType)
            .where(TicketType.id == reservation.ticket_type_id)
            .with_for_update()
        )
        ticket_type = result.scalar_one()

        # Move from reserved → sold
        ticket_type.reserved_quantity -= reservation.quantity
        ticket_type.sold_quantity += reservation.quantity
        reservation.status = ReservationStatus.CONFIRMED

        self.db.add(reservation)
        await self.db.commit()
        return await self.get_by_id(reservation.id)  # type: ignore[return-value]

    async def expire(self, reservation: Reservation) -> Reservation:
        """Mark a pending reservation as expired and release the held tickets.

        Called by the background expiry worker.  Same logic as
        :meth:`cancel` but sets status to EXPIRED.
        """
        if reservation.status != ReservationStatus.PENDING:
            return reservation  # nothing to do

        # Lock the ticket_type row
        result = await self.db.execute(
            select(TicketType)
            .where(TicketType.id == reservation.ticket_type_id)
            .with_for_update()
        )
        ticket_type = result.scalar_one()

        ticket_type.reserved_quantity -= reservation.quantity
        reservation.status = ReservationStatus.EXPIRED

        self.db.add(reservation)
        await self.db.commit()
        return await self.get_by_id(reservation.id)  # type: ignore[return-value]
