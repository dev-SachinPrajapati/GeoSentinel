"""
WebSocket endpoint for real-time disaster updates.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from schemas.disaster import WSMessage, WSSubscribePayload
from websocket.manager import manager
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/disasters")
async def disaster_websocket(websocket: WebSocket):
    client = await manager.connect(websocket)

    # Send initial connection confirmation
    await manager.send_to_client(
        client.id,
        WSMessage(
            type="connected",
            payload={
                "client_id": str(client.id),
                "message": "Connected to Disaster Monitor WebSocket",
            },
        ),
    )

    # Heartbeat task — keeps connection alive, detects dead clients
    async def heartbeat():
        while True:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
            sent = await manager.send_to_client(
                client.id,
                WSMessage(
                    type="heartbeat",
                    payload={"active_connections": manager.active_count},
                ),
            )
            if not sent:
                break

    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "subscribe":
                    # Client sends location + preferences
                    payload = WSSubscribePayload(**msg.get("payload", {}))
                    await manager.update_subscription(client.id, payload)
                    await manager.send_to_client(
                        client.id,
                        WSMessage(
                            type="subscribed",
                            payload={"alert_radius_km": payload.alert_radius_km},
                        ),
                    )

                elif msg_type == "ping":
                    await manager.send_to_client(
                        client.id,
                        WSMessage(type="pong", payload={}),
                    )

                else:
                    logger.debug(f"Unknown WS message type: {msg_type}")

            except (json.JSONDecodeError, ValueError) as e:
                await manager.send_to_client(
                    client.id,
                    WSMessage(type="error", payload={"detail": str(e)}),
                )

    except WebSocketDisconnect:
        logger.info(f"Client {client.id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for {client.id}: {e}")
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(client.id)
