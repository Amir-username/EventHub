from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.venue import (
    PaginatedVenues,
    VenueCreate,
    VenueRead,
    VenueUpdate,
)
from app.services.venue_service import VenueService

router = APIRouter(prefix="/venues", tags=["venues"])

_query_none = Query(None)


@router.get("/public", response_model=PaginatedVenues)
async def list_public_venues(
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = _query_none,
):
    service = VenueService(db)
    venues, total = await service.list_public(offset=offset, limit=limit, search=search)
    return PaginatedVenues(items=venues, total=total, offset=offset, limit=limit)


@router.get("/public/{venue_id}", response_model=VenueRead)
async def get_public_venue(
    venue_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = VenueService(db)
    try:
        return await service.get_public(venue_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=PaginatedVenues)
async def list_venues(
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = _query_none,
):
    service = VenueService(db)
    venues, total = await service.list_all(offset=offset, limit=limit, search=search)
    return PaginatedVenues(items=venues, total=total, offset=offset, limit=limit)


@router.get("/{venue_id}", response_model=VenueRead)
async def get_venue(
    venue_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = VenueService(db)
    try:
        return await service.get_venue(venue_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=VenueRead, status_code=status.HTTP_201_CREATED)
async def create_venue(
    data: VenueCreate,
    admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = VenueService(db)
    try:
        return await service.create_venue(data, created_by=admin.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{venue_id}", response_model=VenueRead)
async def update_venue(
    venue_id: int,
    data: VenueUpdate,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = VenueService(db)
    try:
        return await service.update_venue(venue_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venue(
    venue_id: int,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = VenueService(db)
    try:
        await service.delete_venue(venue_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
