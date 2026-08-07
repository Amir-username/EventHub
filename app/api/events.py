from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.database import get_db
from app.models.event import EventStatus
from app.models.user import User, UserRole
from app.schemas.event import (
    EventCreate,
    EventRead,
    EventUpdate,
    PaginatedEvents,
)
from app.services.event_service import EventService

_query_none = Query(None)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/public", response_model=PaginatedEvents)
async def list_public_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None, max_length=255),
):
    service = EventService(db)
    events, total = await service.list_public(offset=offset, limit=limit, search=search)
    return PaginatedEvents(items=events, total=total, offset=offset, limit=limit)


@router.get("/public/{event_id}", response_model=EventRead)
async def get_public_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = EventService(db)
    try:
        return await service.get_public(event_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=PaginatedEvents)
async def list_events(
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: EventStatus | None = _query_none,
    search: str | None = Query(None, max_length=255),
):
    service = EventService(db)
    events, total = await service.list_all(
        offset=offset, limit=limit, status=status, search=search
    )
    return PaginatedEvents(items=events, total=total, offset=offset, limit=limit)


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = EventService(db)
    try:
        return await service.get_event(event_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = EventService(db)
    try:
        return await service.create_event(data, created_by=admin.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.patch("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: int,
    data: EventUpdate,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = EventService(db)
    try:
        return await service.update_event(event_id, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = EventService(db)
    try:
        await service.delete_event(event_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
