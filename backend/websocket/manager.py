from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import WebSocket, WebSocketDisconnect
from schemas.disaster import WSMessage, WSSubscribePayload

logger = logging.getLogger(__name__)


@dataclass
class ConnectedClient:
    """Represents a single WebSocket connection with optional geo-subscription."""
    id: UUID
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.utcnow)
    # Optional: client's location for proximity alerts
    user_lat: Optional[float] = None
    user_lon: Optional[float] = None
    alert_radius_km: float = 100.0
    subscribed_types: Optional[list[str]] = None

    def matches_subscription(self, event_type: str) -> bool:
        if self.subscribed_types is None:
            return True
        return event_type in self.subscribed_types


class ConnectionManager:
    """
    Thread-safe WebSocket connection manager.
    Handles broadcast, targeted delivery, and geo-filtered notifications.
    """

    def __init__(self):
        self._clients: dict[UUID, ConnectedClient] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> ConnectedClient:
        await websocket.accept()
        client = ConnectedClient(id=uuid4(), websocket=websocket)
        async with self._lock:
            self._clients[client.id] = client
        logger.info(f"WebSocket connected: {client.id} | Total: {self.active_count}")
        return client

    async def disconnect(self, client_id: UUID) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
        logger.info(f"WebSocket disconnected: {client_id} | Total: {self.active_count}")

    async def update_subscription(
        self, client_id: UUID, payload: WSSubscribePayload
    ) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
            if client:
                client.user_lat = payload.user_lat
                client.user_lon = payload.user_lon
                client.alert_radius_km = payload.alert_radius_km
                client.subscribed_types = (
                    [t.value for t in payload.types] if payload.types else None
                )

    async def broadcast(self, message: WSMessage) -> None:
        """Send message to all connected clients."""
        payload = message.model_dump_json()
        dead = []
        async with self._lock:
            clients = list(self._clients.values())

        for client in clients:
            try:
                await client.websocket.send_text(payload)
            except Exception:
                dead.append(client.id)

        # Cleanup dead connections
        if dead:
            async with self._lock:
                for cid in dead:
                    self._clients.pop(cid, None)

    async def broadcast_event(self, event_data: dict) -> None:
        """Broadcast a new disaster event to all subscribers."""
        msg = WSMessage(
            type="new_event",
            payload=event_data,
        )
        await self.broadcast(msg)

    async def send_proximity_alerts(
        self, event_data: dict, event_lat: float, event_lon: float
    ) -> None:
        """
        Send alert only to clients whose location is within their alert radius.
        Distance check done in-process using Haversine (avoids extra DB round-trip).
        """
        import math

        def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1))
                * math.cos(math.radians(lat2))
                * math.sin(dlon / 2) ** 2
            )
            return R * 2 * math.asin(math.sqrt(a))

        payload = WSMessage(type="nearby_alert", payload=event_data).model_dump_json()
        dead = []

        async with self._lock:
            clients = list(self._clients.values())

        for client in clients:
            if client.user_lat is None or client.user_lon is None:
                continue
            dist = haversine_km(client.user_lat, client.user_lon, event_lat, event_lon)
            if dist <= client.alert_radius_km:
                try:
                    await client.websocket.send_text(payload)
                except Exception:
                    dead.append(client.id)

        if dead:
            async with self._lock:
                for cid in dead:
                    self._clients.pop(cid, None)

    async def send_heartbeat(self) -> None:
        """Periodic heartbeat to keep connections alive."""
        msg = WSMessage(
            type="heartbeat",
            payload={"server_time": datetime.utcnow().isoformat()},
        )
        await self.broadcast(msg)

    async def send_to_client(self, client_id: UUID, message: WSMessage) -> bool:
        async with self._lock:
            client = self._clients.get(client_id)
        if not client:
            return False
        try:
            await client.websocket.send_text(message.model_dump_json())
            return True
        except Exception:
            await self.disconnect(client_id)
            return False


# Singleton — shared across the app
manager = ConnectionManager()
