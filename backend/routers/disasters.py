"""
Disaster events REST API router.

IMPORTANT — why this file was rewritten:
  The original routers/disasters.py was a copy of models/disaster.py with
  GeoAlchemy2 columns added. It defined DisasterType, SeverityLevel, User,
  and DisasterEvent classes but contained NO FastAPI router object, which is
  why `from routers.disasters import router` failed in main.py with
  "'router' is unknown import symbol".

  Model definitions belong in models/disaster.py only.
  This file is now a clean FastAPI APIRouter with all CRUD + utility endpoints.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.disaster import DisasterType, SeverityLevel
from schemas.disaster import (
    DisasterEventCreate,
    DisasterEventRead,
    DisasterEventUpdate,
    DisasterFilter,
    PaginatedResponse,
)
from services.disaster_service import DisasterService

router = APIRouter(prefix="/api/v1/disasters", tags=["disasters"])


# ── List / Filter ─────────────────────────────────────────────────────────────
@router.get("/", response_model=PaginatedResponse)
async def list_disasters(
    types: Optional[list[DisasterType]] = Query(None),
    severities: Optional[list[SeverityLevel]] = Query(None),
    country: Optional[str] = Query(None, max_length=100),
    center_lat: Optional[float] = Query(None, ge=-90, le=90),
    center_lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0, le=20000),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    try:
        filters = DisasterFilter(
            types=types,
            severities=severities,
            country=country,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
            offset=offset,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    
    service = DisasterService(db)
    return await service.list_events(filters)


# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/heatmap")
async def get_heatmap(
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
    types: Optional[list[DisasterType]] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DisasterService(db)
    data = await service.get_heatmap_data(from_dt=from_dt, to_dt=to_dt, types=types)
    return {"data": data}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    service = DisasterService(db)
    return await service.get_stats()


# ── Nearby ────────────────────────────────────────────────────────────────────

@router.get("/nearby")
async def get_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(100.0, gt=0, le=20000),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DisasterService(db)
    results = await service.get_events_near_point(lat, lon, radius_km, limit)
    return {
        "data": [
            {
                **DisasterEventRead.model_validate(event).model_dump(mode="json"),
                "distance_km": round(dist_m / 1000, 2),
            }
            for event, dist_m in results
        ]
    }


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=DisasterEventRead, status_code=201)
async def create_disaster(
    data: DisasterEventCreate,
    db: AsyncSession = Depends(get_db),
) -> DisasterEventRead:
    service = DisasterService(db)
    event = await service.create_event(data)
    
    # Broadcast to websocket
    try:
        from websocket.manager import manager
        payload = DisasterEventRead.model_validate(event).model_dump(mode="json")
        await manager.broadcast_event(payload)
        await manager.send_proximity_alerts(payload, float(event.latitude), float(event.longitude))
    except Exception as ws_err:
        import logging
        logging.getLogger(__name__).error(f"Failed to broadcast manually created event: {ws_err}")
        
    return DisasterEventRead.model_validate(event)


# ── Single event — after named routes so /heatmap etc. are not captured ───────

@router.get("/{event_id}", response_model=DisasterEventRead)
async def get_disaster(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DisasterEventRead:
    service = DisasterService(db)
    event = await service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return DisasterEventRead.model_validate(event)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{event_id}", response_model=DisasterEventRead)
async def update_disaster(
    event_id: UUID,
    data: DisasterEventUpdate,
    db: AsyncSession = Depends(get_db),
) -> DisasterEventRead:
    service = DisasterService(db)
    event = await service.update_event(event_id, data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return DisasterEventRead.model_validate(event)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{event_id}", status_code=204)
async def delete_disaster(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    service = DisasterService(db)
    event = await service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(event)
    await db.commit()