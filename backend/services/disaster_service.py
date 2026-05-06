from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.disaster import DisasterEvent, DisasterType, SeverityLevel
from schemas.disaster import (
    DisasterEventCreate,
    DisasterEventUpdate,
    DisasterFilter,
    PaginatedResponse,
    DisasterEventRead,
)

logger = logging.getLogger(__name__)


class DisasterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────────────────────────────────────

    async def create_event(self, data: DisasterEventCreate) -> DisasterEvent:
        if data.external_id:
            existing = await self._get_by_external_id(data.external_id)
            if existing:
                return existing

        event = DisasterEvent(
            external_id=data.external_id,
            type=data.type,
            severity=data.severity,
            title=data.title,
            description=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
            country=data.country,
            region=data.region,
            occurred_at=data.occurred_at,
            expires_at=data.expires_at,
            event_metadata=data.event_metadata,
            source=data.source,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def _get_by_external_id(self, external_id: str) -> Optional[DisasterEvent]:
        result = await self.db.execute(
            select(DisasterEvent).where(DisasterEvent.external_id == external_id)
        )
        return result.scalar_one_or_none()

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_event(self, event_id: UUID) -> Optional[DisasterEvent]:
        result = await self.db.execute(
            select(DisasterEvent).where(DisasterEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_events(self, filters: DisasterFilter) -> PaginatedResponse:
        """
        List events with optional PostGIS radius filter via raw SQL.
        ST_DWithin uses the GIST index on the location column.
        """
        conditions = []

        if filters.types:
            conditions.append(DisasterEvent.type.in_(filters.types))
        if filters.severities:
            conditions.append(DisasterEvent.severity.in_(filters.severities))
        if filters.country:
            conditions.append(DisasterEvent.country.ilike(f"%{filters.country}%"))
        if filters.from_dt:
            conditions.append(DisasterEvent.occurred_at >= filters.from_dt)
        if filters.to_dt:
            conditions.append(DisasterEvent.occurred_at <= filters.to_dt)

        radius_condition = None
        if (
            filters.radius_km is not None
            and filters.center_lat is not None
            and filters.center_lon is not None
        ):
            radius_m = filters.radius_km * 1000
            radius_condition = text(
                "ST_DWithin("
                "  ST_SetSRID(ST_MakePoint(disaster_events.longitude, disaster_events.latitude), 4326)::geography,"
                "  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,"
                "  :radius_m,"
                "  true"
                ")"
            ).bindparams(
                lon=filters.center_lon,
                lat=filters.center_lat,
                radius_m=radius_m,
            )

        query = select(DisasterEvent)
        count_query = select(func.count(DisasterEvent.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        if radius_condition is not None:
            query = query.where(radius_condition)
            count_query = count_query.where(radius_condition)

        query = (
            query.order_by(DisasterEvent.occurred_at.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )

        events_result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)

        events = events_result.scalars().all()
        total = count_result.scalar_one()

        return PaginatedResponse(
            data=[DisasterEventRead.model_validate(e) for e in events],
            total=total,
            limit=filters.limit,
            offset=filters.offset,
        )

    async def get_events_near_point(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        limit: int = 50,
    ) -> list[tuple[DisasterEvent, float]]:
        """PostGIS ST_DWithin + ST_Distance via raw SQL."""
        radius_m = radius_km * 1000
        stmt = text("""
            SELECT
                de.*,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(de.longitude, de.latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    true
                ) AS distance_m
            FROM disaster_events de
            WHERE ST_DWithin(
                ST_SetSRID(ST_MakePoint(de.longitude, de.latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m,
                true
            )
            ORDER BY distance_m
            LIMIT :limit
        """).bindparams(lat=lat, lon=lon, radius_m=radius_m, limit=limit)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        events_with_dist: list[tuple[DisasterEvent, float]] = []
        for row in rows:
            event = await self.get_event(row["id"])
            if event:
                events_with_dist.append((event, float(row["distance_m"])))
        return events_with_dist

    async def get_heatmap_data(
        self,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        types: Optional[list[DisasterType]] = None,
    ) -> list[dict]:
        severity_weight = {
            SeverityLevel.LOW: 0.25,
            SeverityLevel.MEDIUM: 0.5,
            SeverityLevel.HIGH: 0.75,
            SeverityLevel.CRITICAL: 1.0,
        }

        conditions = []
        if from_dt:
            conditions.append(DisasterEvent.occurred_at >= from_dt)
        if to_dt:
            conditions.append(DisasterEvent.occurred_at <= to_dt)
        if types:
            conditions.append(DisasterEvent.type.in_(types))

        query = select(
            DisasterEvent.latitude,
            DisasterEvent.longitude,
            DisasterEvent.severity,
            DisasterEvent.type,
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "lat": r.latitude,
                "lon": r.longitude,
                "weight": severity_weight.get(r.severity, 0.5),
                "type": r.type,
            }
            for r in rows
        ]

    # ── Update ──────────────────────────────────────────────────────────────

    async def update_event(
        self, event_id: UUID, data: DisasterEventUpdate
    ) -> Optional[DisasterEvent]:
        event = await self.get_event(event_id)
        if not event:
            return None

        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(event, key, value)

        await self.db.commit()
        await self.db.refresh(event)
        return event

    # ── Stats ────────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        result = await self.db.execute(
            select(
                DisasterEvent.type,
                DisasterEvent.severity,
                func.count(DisasterEvent.id).label("event_count"),  # ← renamed
            ).group_by(DisasterEvent.type, DisasterEvent.severity)
        )
        rows = result.all()

        by_type_severity = [
            {
                "type": r.type,
                "severity": r.severity,
                "count": r.event_count,  # ← resolves to int scalar, not method
            }
            for r in rows
        ]
        total: int = sum(r["count"] for r in by_type_severity)

        return {
            "by_type_severity": by_type_severity,
            "total": total,
        }