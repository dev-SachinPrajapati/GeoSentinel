'use client';

import { DisasterEvent } from '@/types';
import {
  DISASTER_COLORS, DISASTER_EMOJI,
  SEVERITY_COLORS, SEVERITY_LABEL,
  formatMetadata, timeAgo,
} from '@/lib/mapUtils';

interface EventPopupProps { event: DisasterEvent; }

const SOURCE_META: Record<string, { label: string; color: string; window: string }> = {
  usgs:           { label: 'USGS',            color: '#6366f1', window: 'Past 1h feed'          },
  nasa_firms:     { label: 'NASA FIRMS',       color: '#f97316', window: 'Past 24h satellite'    },
  openweathermap: { label: 'OpenWeatherMap',   color: '#3b82f6', window: 'Current conditions'    },
  gdacs:          { label: 'GDACS (UN)',        color: '#10b981', window: 'Active events'         },
  noaa_nhc:       { label: 'NOAA NHC',         color: '#8b5cf6', window: 'Active storms'         },
  noaa_ptwc:      { label: 'NOAA PTWC',        color: '#06b6d4', window: 'Active warnings'       },
  manual:         { label: 'Manual',           color: '#6b7280', window: 'Manual entry'          },
};

export function EventPopup({ event }: EventPopupProps) {
  const color         = DISASTER_COLORS[event.type];
  const severityColor = SEVERITY_COLORS[event.severity];
  const metaLines     = formatMetadata(event.type, event.event_metadata as Record<string, unknown>);
  const src           = SOURCE_META[event.source] ?? { label: event.source, color: '#6b7280', window: '' };

  const diffHours = (Date.now() - new Date(event.occurred_at).getTime()) / 3_600_000;
  const freshness =
    diffHours < 1  ? 'Real-time (< 1h)'      :
    diffHours < 24 ? `${Math.floor(diffHours)}h ago` :
                     `${Math.floor(diffHours / 24)}d ago`;

  return (
    <div className="font-sans text-sm text-gray-100 min-w-[260px] max-w-[320px]">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-md"
        style={{ backgroundColor: color + '22', borderBottom: `2px solid ${color}` }}
      >
        <span className="text-xl flex-shrink-0">{DISASTER_EMOJI[event.type]}</span>
        <div className="min-w-0">
          <div className="font-bold text-white leading-tight truncate">{event.title}</div>
          <div className="text-xs opacity-70 capitalize">{event.type} · {timeAgo(event.occurred_at)}</div>
        </div>
      </div>

      {/* Body */}
      <div className="px-3 py-2 space-y-1.5 bg-gray-900 rounded-b-md">

        {/* Severity + Source */}
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
            style={{ backgroundColor: severityColor + '33', color: severityColor }}
          >
            {SEVERITY_LABEL[event.severity]}
          </span>
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full"
            style={{ backgroundColor: src.color + '25', color: src.color }}
          >
            {src.label}
          </span>
        </div>

        {/* Freshness */}
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <span>🕐</span>
          <span>{freshness}</span>
          {src.window && (
            <>
              <span className="text-gray-700">·</span>
              <span className="text-gray-600 italic">{src.window}</span>
            </>
          )}
        </div>

        {/* Location */}
        {(event.country || event.region) && (
          <div className="text-xs text-gray-400 flex items-center gap-1">
            <span>📍</span>
            <span className="truncate">
              {[event.region, event.country]
                .filter(Boolean)
                .filter((v, i, a) => a.indexOf(v) === i)
                .join(', ')}
            </span>
          </div>
        )}

        {/* Description */}
        {event.description && event.description !== event.region && (
          <p className="text-xs text-gray-300 leading-relaxed">{event.description}</p>
        )}

        {/* Metadata */}
        {metaLines.length > 0 && (
          <div className="border-t border-gray-700 pt-1.5 space-y-0.5">
            {metaLines.map((line, i) => (
              <div key={i} className="text-xs text-gray-300">{line}</div>
            ))}
          </div>
        )}

        {/* Coords */}
        <div className="text-xs text-gray-600 font-mono pt-0.5">
          {event.latitude.toFixed(4)}, {event.longitude.toFixed(4)}
        </div>
      </div>
    </div>
  );
}