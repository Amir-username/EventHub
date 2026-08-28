from typing import Annotated

from app.schemas.reservation import (
    PaginatedAdminReservations,
    PaginatedReservations,
    ReservationCreate,
    ReservationRead,
    ReservationReadWithUser,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.reservation import ReservationStatus
from app.models.user import User, UserRole
from app.services.reservation_service import ReservationService

router = APIRouter(prefix="/reservations", tags=["reservations"])

_query_none = Query(None)


# ------------------------------------------------------------------
# Customer endpoints (require authenticated user)
# ------------------------------------------------------------------


@router.post(
    "",
    response_model=ReservationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    data: ReservationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ReservationService(db)
    try:
        return await service.create_reservation(
            user_id=current_user.id,
            ticket_type_id=data.ticket_type_id,
            quantity=data.quantity,
            idempotency_key=data.idempotency_key,
        )
    except ValueError as e:
        msg = str(e).lower()
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        if (
            "not enough" in msg
            or "sales have not started" in msg
            or "sales have ended" in msg
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
            )
        if "idempotency" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/mine", response_model=PaginatedReservations)
async def list_my_reservations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: ReservationStatus | None = _query_none,
):
    service = ReservationService(db)
    reservations, total = await service.list_my_reservations(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
        status=status_filter,
    )
    return PaginatedReservations(
        items=reservations, total=total, offset=offset, limit=limit
    )


@router.get("/mine/{reservation_id}", response_model=ReservationRead)
async def get_my_reservation(
    reservation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ReservationService(db)
    try:
        reservation = await service.get_reservation(reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if reservation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found"
        )
    return reservation


@router.post("/mine/{reservation_id}/cancel", response_model=ReservationRead)
async def cancel_my_reservation(
    reservation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ReservationService(db)
    try:
        return await service.cancel_reservation(reservation_id, user_id=current_user.id)
    except ValueError as e:
        msg = str(e).lower()
        if "not found" in msg or "not your" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        # e.g. "Cannot cancel a reservation with status 'confirmed'"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


# ------------------------------------------------------------------
# Admin endpoints
# ------------------------------------------------------------------


@router.get("", response_model=PaginatedAdminReservations)
async def list_all_reservations(
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: ReservationStatus | None = _query_none,
    user_id: int | None = _query_none,
    ticket_type_id: int | None = _query_none,
):
    service = ReservationService(db)
    reservations, total = await service.list_all_reservations(
        offset=offset,
        limit=limit,
        status=status_filter,
        user_id=user_id,
        ticket_type_id=ticket_type_id,
    )
    return PaginatedAdminReservations(
        items=reservations, total=total, offset=offset, limit=limit
    )


@router.get("/{reservation_id}", response_model=ReservationReadWithUser)
async def get_reservation(
    reservation_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ReservationService(db)
    try:
        return await service.get_reservation(reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{reservation_id}/confirm", response_model=ReservationReadWithUser)
async def confirm_reservation(
    reservation_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ReservationService(db)
    try:
        return await service.confirm_reservation(reservation_id)
    except ValueError as e:
        msg = str(e).lower()
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        # e.g. "Cannot confirm a reservation with status 'cancelled'"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
