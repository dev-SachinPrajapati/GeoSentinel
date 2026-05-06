import { DisasterType, SeverityLevel, DisasterEvent } from '@/types';

// ── Color Palette ─────────────────────────────────────────────────────────────

export const DISASTER_COLORS: Record<DisasterType, string> = {
  earthquake: '#F97316',
  flood:      '#3B82F6',
  fire:       '#EF4444',
  hurricane:  '#8B5CF6',
  tsunami:    '#06B6D4',
};

export const SEVERITY_COLORS: Record<SeverityLevel, string> = {
  low:      '#22C55E',
  medium:   '#EAB308',
  high:     '#F97316',
  critical: '#EF4444',
};

export const SEVERITY_RADIUS: Record<SeverityLevel, number> = {
  low: 8,
  medium: 11,
  high: 15,
  critical: 20,
};

export const DISASTER_EMOJI: Record<DisasterType, string> = {
  earthquake: '🌍',
  flood:      '🌊',
  fire:       '🔥',
  hurricane:  '🌀',
  tsunami:    '🌊',
};

export const DISASTER_ICON: Record<DisasterType, string> = {
  earthquake: 'seismic',
  flood:      'water',
  fire:       'fire',
  hurricane:  'wind',
  tsunami:    'wave',
};

export const SEVERITY_LABEL: Record<SeverityLevel, string> = {
  low:      'Low',
  medium:   'Medium',
  high:     'High',
  critical: 'Critical',
};

// ── MapLibre GeoJSON Feature Builder ─────────────────────────────────────────

export function eventsToGeoJSON(events: DisasterEvent[]) {
  return {
    type: 'FeatureCollection' as const,
    features: events.map((e) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [e.longitude, e.latitude],
      },
      properties: {
        id: e.id,
        type: e.type,
        severity: e.severity,
        title: e.title,
        country: e.country,
        occurred_at: e.occurred_at,
        color: DISASTER_COLORS[e.type],
        severityColor: SEVERITY_COLORS[e.severity],
        radius: SEVERITY_RADIUS[e.severity],
        severityScore:
          e.severity === 'critical' ? 4
          : e.severity === 'high' ? 3
          : e.severity === 'medium' ? 2
          : 1,
      },
    })),
  };
}

// ── Heatmap Color Gradient ────────────────────────────────────────────────────

export const HEATMAP_COLOR_GRADIENT = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0,   'rgba(33,102,172,0)',
  0.2, 'rgb(103,169,207)',
  0.4, 'rgb(209,229,240)',
  0.6, 'rgb(253,219,199)',
  0.8, 'rgb(239,138,98)',
  1,   'rgb(178,24,43)',
];

// ── Cluster Color ─────────────────────────────────────────────────────────────

export function getClusterCountColor(count: number): string {
  if (count >= 50) return '#EF4444';
  if (count >= 20) return '#F97316';
  if (count >= 10) return '#EAB308';
  return '#22C55E';
}

// ── Metadata Formatter ────────────────────────────────────────────────────────

export function formatMetadata(
  type: DisasterType,
  metadata: Record<string, unknown>,
): string[] {
  const lines: string[] = [];

  if (type === 'earthquake') {
    if (metadata.magnitude != null)  lines.push(`Magnitude: ${metadata.magnitude}`);
    if (metadata.depth_km != null)   lines.push(`Depth: ${metadata.depth_km} km`);
    if (metadata.tsunami)            lines.push('⚠️ Tsunami warning issued');
    if (metadata.alert)              lines.push(`Alert level: ${metadata.alert}`);
    if (metadata.felt != null)       lines.push(`Felt reports: ${metadata.felt}`);

  } else if (type === 'flood') {
    if (metadata.rain_1h_mm != null)   lines.push(`Rainfall: ${metadata.rain_1h_mm} mm/h`);
    if (metadata.rain_3h_mm != null)   lines.push(`3-hour rain: ${metadata.rain_3h_mm} mm`);
    if (metadata.humidity_pct != null) lines.push(`Humidity: ${metadata.humidity_pct}%`);
    if (metadata.water_level_m != null)        lines.push(`Water level: ${metadata.water_level_m}m`);
    if (metadata.affected_area_km2 != null)    lines.push(`Affected area: ${metadata.affected_area_km2} km²`);
    if (metadata.evacuation_order)             lines.push('🚨 Evacuation order in effect');

  } else if (type === 'fire') {
    if (metadata.total_frp_mw != null)    lines.push(`Fire power: ${metadata.total_frp_mw} MW`);
    if (metadata.detection_count != null) lines.push(`Detections: ${metadata.detection_count}`);
    if (metadata.confidence != null)      lines.push(`Confidence: ${metadata.confidence}`);
    if (metadata.source_satellite)        lines.push(`Satellite: ${metadata.source_satellite}`);
    // Legacy fields
    if (metadata.area_hectares != null)   lines.push(`Area: ${metadata.area_hectares} ha`);
    if (metadata.containment_pct != null) lines.push(`Containment: ${metadata.containment_pct}%`);
    if (metadata.wind_speed_kmh != null)  lines.push(`Wind: ${metadata.wind_speed_kmh} km/h`);

  } else if (type === 'hurricane') {
    if (metadata.wind_speed_ms != null) {
      const kmh = Math.round(Number(metadata.wind_speed_ms) * 3.6);
      lines.push(`Wind speed: ${metadata.wind_speed_ms} m/s (${kmh} km/h)`);
    }
    if (metadata.wind_gust_ms != null) {
      const kmh = Math.round(Number(metadata.wind_gust_ms) * 3.6);
      lines.push(`Gusts: ${metadata.wind_gust_ms} m/s (${kmh} km/h)`);
    }
    if (metadata.category != null)       lines.push(`Category: ${metadata.category}`);
    if (metadata.pressure_hpa != null)   lines.push(`Pressure: ${metadata.pressure_hpa} hPa`);
    if (metadata.diameter_km != null)    lines.push(`Diameter: ${metadata.diameter_km} km`);

  } else if (type === 'tsunami') {
    if (metadata.wave_height_m != null)    lines.push(`Wave height: ${metadata.wave_height_m}m`);
    if (metadata.eta_minutes != null)      lines.push(`ETA: ${metadata.eta_minutes} minutes`);
    if (metadata.source_magnitude != null) lines.push(`Source magnitude: ${metadata.source_magnitude}`);
  }

  return lines;
}

// ── Time Helper ───────────────────────────────────────────────────────────────

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}