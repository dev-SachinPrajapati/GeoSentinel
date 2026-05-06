import { DisasterEvent, DisasterFilters, DisasterStats, HeatmapPoint, NearbyEvent, PaginatedResponse } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── HTTP Client ───────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Disaster Events ───────────────────────────────────────────────────────────

export function buildDisasterParams(filters: Partial<DisasterFilters>, limit = 500): URLSearchParams {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());

  if (filters.types?.length) {
    filters.types.forEach((t) => params.append('types', t));
  }
  if (filters.severities?.length) {
    filters.severities.forEach((s) => params.append('severities', s));
  }
  if (filters.country) params.set('country', filters.country);
  if (filters.radiusKm) params.set('radius_km', filters.radiusKm.toString());
  if (filters.centerLat != null) params.set('center_lat', filters.centerLat.toString());
  if (filters.centerLon != null) params.set('center_lon', filters.centerLon.toString());
  if (filters.fromDt) params.set('from_dt', filters.fromDt);
  if (filters.toDt) params.set('to_dt', filters.toDt);

  return params;
}

export async function fetchDisasters(filters: Partial<DisasterFilters> = {}): Promise<PaginatedResponse> {
  const params = buildDisasterParams(filters);
  return apiFetch<PaginatedResponse>(`/api/v1/disasters/?${params}`);
}

export async function fetchDisaster(id: string): Promise<DisasterEvent> {
  return apiFetch<DisasterEvent>(`/api/v1/disasters/${id}`);
}

export async function fetchHeatmap(
  filters: { fromDt?: string; toDt?: string; types?: string[] } = {}
): Promise<{ data: HeatmapPoint[] }> {
  const params = new URLSearchParams();
  if (filters.fromDt) params.set('from_dt', filters.fromDt);
  if (filters.toDt) params.set('to_dt', filters.toDt);
  filters.types?.forEach((t) => params.append('types', t));
  return apiFetch<{ data: HeatmapPoint[] }>(`/api/v1/disasters/heatmap?${params}`);
}

export async function fetchStats(): Promise<DisasterStats> {
  return apiFetch<DisasterStats>('/api/v1/disasters/stats');
}

export async function fetchNearby(
  lat: number,
  lon: number,
  radiusKm = 100
): Promise<{ data: NearbyEvent[] }> {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius_km: radiusKm.toString(),
  });
  return apiFetch<{ data: NearbyEvent[] }>(`/api/v1/disasters/nearby?${params}`);
}

// ── Query Keys ────────────────────────────────────────────────────────────────

export const queryKeys = {
  disasters: (filters: Partial<DisasterFilters>) => ['disasters', filters] as const,
  disaster: (id: string) => ['disaster', id] as const,
  heatmap: (filters: object) => ['heatmap', filters] as const,
  stats: () => ['stats'] as const,
  nearby: (lat: number, lon: number, radius: number) => ['nearby', lat, lon, radius] as const,
} as const;
