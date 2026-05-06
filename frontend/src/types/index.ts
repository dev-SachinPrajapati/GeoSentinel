export type DisasterType = 'earthquake' | 'flood' | 'fire' | 'hurricane' | 'tsunami';
export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

export interface DisasterEvent {
  id: string;
  external_id: string | null;
  type: DisasterType;
  severity: SeverityLevel;
  title: string;
  description: string | null;
  latitude: number;
  longitude: number;
  country: string | null;
  region: string | null;
  occurred_at: string;
  expires_at: string | null;
  event_metadata: Record<string, unknown>;
  source: string;
  created_at: string;
}

export interface PaginatedResponse {
  data: DisasterEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface HeatmapPoint {
  lat: number;
  lon: number;
  weight: number;
  type: DisasterType;
}

export interface DisasterStats {
  by_type_severity: Array<{
    type: DisasterType;
    severity: SeverityLevel;
    count: number;
  }>;
  total: number;
}

export interface NearbyEvent extends DisasterEvent {
  distance_km: number;
}

// ── WebSocket Types ───────────────────────────────────────────────────────────

export type WSMessageType =
  | 'connected'
  | 'new_event'
  | 'event_update'
  | 'nearby_alert'
  | 'heartbeat'
  | 'subscribed'
  | 'pong'
  | 'error';

export interface WSMessage<T = unknown> {
  type: WSMessageType;
  payload: T;
  timestamp: string;
}

export interface WSSubscribePayload {
  user_lat?: number;
  user_lon?: number;
  alert_radius_km?: number;
  types?: DisasterType[];
}

// ── Filter State ──────────────────────────────────────────────────────────────

export interface DisasterFilters {
  types: DisasterType[];
  severities: SeverityLevel[];
  country: string;
  radiusKm: number | null;
  centerLat: number | null;
  centerLon: number | null;
  fromDt: string | null;
  toDt: string | null;
}

export const defaultFilters: DisasterFilters = {
  types: [],
  severities: [],
  country: '',
  radiusKm: null,
  centerLat: null,
  centerLon: null,
  fromDt: null,
  toDt: null,
};

// ── UI State ──────────────────────────────────────────────────────────────────

export interface MapViewState {
  longitude: number;
  latitude: number;
  zoom: number;
}

export interface Notification {
  id: string;
  event: DisasterEvent;
  type: 'new_event' | 'nearby_alert';
  timestamp: string;
  read: boolean;
}