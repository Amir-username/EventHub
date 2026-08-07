from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.ticket_type import (
    PaginatedTicketTypes,
    TicketTypeCreate,
    TicketTypeRead,
    TicketTypeUpdate,
)
from app.services.ticket_type_service import TicketTypeService

router = APIRouter(prefix="/ticket-types", tags=["ticket-types"])

_query_none = Query(None)


@router.get("/public/events/{event_id}", response_model=PaginatedTicketTypes)
async def list_public_ticket_types(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    service = TicketTypeService(db)
    try:
        items, total = await service.list_public_by_event(
            event_id, offset=offset, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return PaginatedTicketTypes(items=items, total=total, offset=offset, limit=limit)


@router.get("/public/{ticket_type_id}", response_model=TicketTypeRead)
async def get_public_ticket_type(
    ticket_type_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = TicketTypeService(db)
    try:
        return await service.get_public(ticket_type_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=PaginatedTicketTypes)
async def list_ticket_types(
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    event_id: int | None = _query_none,
):
    service = TicketTypeService(db)
    items, total = await service.list_all(offset=offset, limit=limit, event_id=event_id)
    return PaginatedTicketTypes(items=items, total=total, offset=offset, limit=limit)


@router.get("/{ticket_type_id}", response_model=TicketTypeRead)
async def get_ticket_type(
    ticket_type_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = TicketTypeService(db)
    try:
        return await service.get_ticket_type(ticket_type_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=TicketTypeRead, status_code=status.HTTP_201_CREATED)
async def create_ticket_type(
    data: TicketTypeCreate,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = TicketTypeService(db)
    try:
        return await service.create_ticket_type(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.patch("/{ticket_type_id}", response_model=TicketTypeRead)
async def update_ticket_type(
    ticket_type_id: int,
    data: TicketTypeUpdate,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = TicketTypeService(db)
    try:
        return await service.update_ticket_type(ticket_type_id, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete("/{ticket_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_type(
    ticket_type_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = TicketTypeService(db)
    try:
        await service.delete_ticket_type(ticket_type_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
