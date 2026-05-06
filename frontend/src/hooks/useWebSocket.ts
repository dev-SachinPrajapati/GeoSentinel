import { useEffect, useRef, useCallback } from 'react';
import { DisasterEvent, WSMessage, WSSubscribePayload } from '@/types';
import { useAppStore } from '@/store';

const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000').replace(/\/$/, '');
const RECONNECT_BASE_DELAY   = 1_000;
const RECONNECT_MAX_DELAY    = 30_000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useDisasterWebSocket() {
  // ── Refs: mutable state that never triggers re-renders ────────────────────
  const wsRef               = useRef<WebSocket | null>(null);
  const activeRef           = useRef(false);   // false while cleanup is running
  const attemptsRef         = useRef(0);
  const timerRef            = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep store actions in a ref so the effect closure always sees current ones
  const storeRef = useRef(useAppStore.getState());
  useEffect(() => {
    // Sync on every render without adding store to effect deps
    storeRef.current = useAppStore.getState();
  });

  // ── Core logic (all inside refs — no useCallback deps needed) ────────────

  // scheduleReconnect and connect are defined as plain functions inside the
  // effect below so they share closure over the same activeRef / wsRef.
  // They are exposed via connectRedf so sendMessage can call connect if needed.
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    activeRef.current = true;

    function handleMessage(msg: WSMessage) {
      const { addLiveEvent, addNotification } = storeRef.current;
      switch (msg.type) {
        case 'new_event': {
          const event = msg.payload as DisasterEvent;
          addLiveEvent(event);
          addNotification({ event, type: 'new_event', timestamp: msg.timestamp });
          break;
        }
        case 'nearby_alert': {
          const event = msg.payload as DisasterEvent;
          addNotification({ event, type: 'nearby_alert', timestamp: msg.timestamp });
          break;
        }
        case 'heartbeat':
          wsRef.current?.send(JSON.stringify({ type: 'ping' }));
          break;
        default:
          break;
      }
    }

    function scheduleReconnect() {
      if (!activeRef.current) return;
      if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        storeRef.current.setWsStatus('failed');
        return;
      }
      const delay = Math.min(
        RECONNECT_BASE_DELAY * 2 ** attemptsRef.current,
        RECONNECT_MAX_DELAY,
      );
      attemptsRef.current += 1;
      timerRef.current = setTimeout(() => {
        if (activeRef.current) connect();
      }, delay);
    }

    function connect() {
      if (!activeRef.current) return;

      // Guard: don't open a second socket while one is already live
      const prev = wsRef.current;
      if (
        prev &&
        (prev.readyState === WebSocket.CONNECTING ||
          prev.readyState === WebSocket.OPEN)
      ) {
        return;
      }

      storeRef.current.setWsStatus('connecting');

      let ws: WebSocket;
      try {
        ws = new WebSocket(`${WS_URL}/ws/disasters`);
      } catch {
        storeRef.current.setWsStatus('error');
        scheduleReconnect();
        return;
      }

      wsRef.current = ws;

      ws.onopen = () => {
        // If cleanup ran while we were connecting, close immediately
        if (!activeRef.current) {
          ws.close(1000, 'unmounted');
          return;
        }
        attemptsRef.current = 0;
        storeRef.current.setWsStatus('connected');

        const send = (payload: WSSubscribePayload | Record<string, never>) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'subscribe', payload }));
          }
        };

        if (typeof navigator !== 'undefined' && navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            (pos) =>
              send({
                user_lat: pos.coords.latitude,
                user_lon: pos.coords.longitude,
                alert_radius_km: 200,
              }),
            () => send({}),
          );
        } else {
          send({});
        }
      };

      ws.onmessage = (raw) => {
        try {
          handleMessage(JSON.parse(raw.data) as WSMessage);
        } catch (e) {
          console.error('[WS] parse error:', e);
        }
      };

      ws.onclose = (evt) => {
        if (!activeRef.current) return; // our own cleanup — ignore
        storeRef.current.setWsStatus('disconnected');
        console.info(`[WS] closed (code=${evt.code}), reconnecting…`);
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (!activeRef.current) return;
        storeRef.current.setWsStatus('error');
        // onclose always fires after onerror — reconnect handled there
      };
    }

    // Expose connect so sendMessage can re-open if needed
    connectRef.current = connect;

    connect();

    return () => {
      // Set dead BEFORE closing so onclose doesn't trigger scheduleReconnect
      activeRef.current = false;

      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }

      wsRef.current?.close(1000, 'component unmounted');
      wsRef.current = null;
    };
  }, []); // ← intentionally empty: effect runs once per mount

  const sendMessage = useCallback((type: string, payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  return { sendMessage };
}