'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Shield, Lock } from 'lucide-react';
import { useAppStore } from '@/store';
import { useAuthStore } from '@/store/authStore';
import { DisasterType, SeverityLevel, DisasterStats } from '@/types';
import { DISASTER_COLORS, DISASTER_EMOJI, SEVERITY_COLORS, SEVERITY_LABEL } from '@/lib/mapUtils';
import { AuthModal } from '@/components/auth/AuthModal';
import { clsx } from 'clsx';


const DISASTER_TYPES: DisasterType[]   = ['earthquake','flood','fire','hurricane','tsunami'];
const SEVERITY_LEVELS: SeverityLevel[] = ['low','medium','high','critical'];

const DATA_SOURCES = [
  { color: '#6366f1', label: 'USGS',          detail: 'Earthquakes · past 1h'        },
  { color: '#f97316', label: 'NASA FIRMS',     detail: 'Wildfires · past 24h'         },
  { color: '#3b82f6', label: 'OpenWeatherMap', detail: 'Floods & storms · current'    },
  { color: '#10b981', label: 'GDACS (UN)',      detail: 'Floods / cyclones / tsunamis' },
  { color: '#8b5cf6', label: 'NOAA NHC',       detail: 'Hurricanes · active storms'   },
  { color: '#06b6d4', label: 'NOAA PTWC',      detail: 'Tsunamis · active warnings'   },
];

interface SidebarProps { stats?: DisasterStats; totalEvents: number; }

export function Sidebar({ stats, totalEvents }: SidebarProps) {
  const {
    filters, setFilters, resetFilters,
    showHeatmap, toggleHeatmap, showSidebar,
  } = useAppStore();

  const { user } = useAuthStore();
  const isLoggedIn = !!user;

  const [showAuth, setShowAuth] = useState(false);

  // ── Debounced location input ──────────────────────────────────────────────
  const [locationInput, setLocationInput] = useState(filters.country);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => { setLocationInput(filters.country); }, [filters.country]);
  const handleLocation = (val: string) => {
    setLocationInput(val);
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(() => setFilters({ country: val }), 400);
  };
  useEffect(() => () => { if (debRef.current) clearTimeout(debRef.current); }, []);

  const toggleType = useCallback((t: DisasterType) => {
    setFilters({
      types: filters.types.includes(t)
        ? filters.types.filter((x) => x !== t)
        : [...filters.types, t],
    });
  }, [filters.types, setFilters]);

  const toggleSeverity = useCallback((s: SeverityLevel) => {
    setFilters({
      severities: filters.severities.includes(s)
        ? filters.severities.filter((x) => x !== s)
        : [...filters.severities, s],
    });
  }, [filters.severities, setFilters]);

  const countForType = (t: DisasterType): number =>
    stats?.by_type_severity.filter((r) => r.type === t).reduce((s, r) => s + r.count, 0) ?? 0;

  if (!showSidebar) return null;

  return (
    <>
      <aside className="w-72 bg-gray-950/95 backdrop-blur-sm border-r border-gray-800
                        flex flex-col h-full overflow-hidden relative flex-shrink-0">

        {/* Header — always visible */}
        <div className="px-4 py-4 border-b border-gray-800 flex-shrink-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <p>Disaster Montior</p>
            </div>
            {/* Auth status indicator */}
            <div className="flex items-center gap-1">
              {isLoggedIn ? (
                <span className="text-green-400" title="Logged in">
                  <Shield className="w-4 h-4" />
                </span>
              ) : (
                <span className="text-gray-600" title="Login to interact">
                  <Lock className="w-4 h-4" />
                </span>
              )}
            </div>
          </div>
          <p className="text-gray-400 text-xs">{totalEvents.toLocaleString()} active events worldwide</p>
        </div>

        {/* Scrollable body — blurred when not logged in */}
        <div className={clsx(
          'flex-1 overflow-y-auto px-4 py-4 space-y-5 scrollbar-thin scrollbar-thumb-gray-700',
          !isLoggedIn && 'blur-sm pointer-events-none select-none'
        )}>

          {/* Heatmap */}
          <section>
            <button onClick={toggleHeatmap}
              className={clsx(
                'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all',
                showHeatmap
                  ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
                  : 'bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-600',
              )}>
              <span className="flex items-center gap-2">🔥 Heatmap Layer</span>
              <span className={clsx('w-8 h-4 rounded-full transition-colors flex items-center px-0.5',
                showHeatmap ? 'bg-orange-500' : 'bg-gray-600')}>
                <span className={clsx('w-3 h-3 bg-white rounded-full shadow transition-transform',
                  showHeatmap ? 'translate-x-4' : 'translate-x-0')} />
              </span>
            </button>
          </section>

          {/* Event type filter */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Event Type
            </h3>
            <div className="space-y-1.5">
              {DISASTER_TYPES.map((type) => {
                const active = filters.types.includes(type);
                const color  = DISASTER_COLORS[type];
                return (
                  <button key={type} onClick={() => toggleType(type)}
                    className={clsx(
                      'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all',
                      active
                        ? 'border text-white'
                        : 'bg-gray-800/60 text-gray-400 border border-transparent hover:border-gray-700',
                    )}
                    style={active ? { backgroundColor: color+'20', borderColor: color+'60', color } : {}}>
                    <span className="flex items-center gap-2 capitalize">
                      <span>{DISASTER_EMOJI[type]}</span>{type}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700/60 text-gray-400">
                      {countForType(type)}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Severity filter */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Severity
            </h3>
            <div className="grid grid-cols-2 gap-1.5">
              {SEVERITY_LEVELS.map((level) => {
                const active = filters.severities.includes(level);
                const color  = SEVERITY_COLORS[level];
                return (
                  <button key={level} onClick={() => toggleSeverity(level)}
                    className={clsx(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize',
                      active
                        ? 'border'
                        : 'bg-gray-800 text-gray-400 border border-transparent hover:border-gray-700',
                    )}
                    style={active ? { backgroundColor: color+'20', borderColor: color+'50', color } : {}}>
                    {SEVERITY_LABEL[level]}
                  </button>
                );
              })}
            </div>
          </section>

          {/* ── Location filter ─────────────────────────────────────────────
              Searches across country, state/province, and city columns.
              Examples: "Japan"  "California"  "Mumbai"  "Osaka"  "Texas"
          ──────────────────────────────────────────────────────────────── */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Location
            </h3>
            <input
              type="text"
              value={locationInput}
              onChange={(e) => handleLocation(e.target.value)}
              placeholder="Country, state, city…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                         text-sm text-white placeholder-gray-500 focus:outline-none
                         focus:border-gray-500 transition-colors"
            />
            <p className="text-xs text-gray-600 mt-1">
              e.g. &quot;Japan&quot;, &quot;California&quot;, &quot;Mumbai&quot;, &quot;Maharashtra&quot;
            </p>
          </section>

          {/* Radius */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Radius Filter (km)
            </h3>
            <div className="flex gap-2">
              <input type="number" value={filters.radiusKm ?? ''}
                onChange={(e) => setFilters({ radiusKm: e.target.value ? Number(e.target.value) : null })}
                placeholder="Radius"
                className="w-24 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm
                           text-white placeholder-gray-500 focus:outline-none focus:border-gray-500" />
              <button
                onClick={() => {
                  if (!navigator.geolocation) return;
                  navigator.geolocation.getCurrentPosition((pos) =>
                    setFilters({ centerLat: pos.coords.latitude, centerLon: pos.coords.longitude,
                                 radiusKm: filters.radiusKm ?? 200 })
                  );
                }}
                className="flex-1 bg-gray-800 border border-gray-700 hover:border-gray-600
                           text-gray-300 text-xs rounded-lg px-2 py-2 transition-colors">
                📍 Use My Location
              </button>
            </div>
          </section>


          {/* Time range */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">
              Time Range
            </h3>
            <div className="space-y-2">
              {(['fromDt','toDt'] as const).map((key) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 block mb-1">
                    {key === 'fromDt' ? 'From' : 'To'}
                  </label>
                  <input type="datetime-local" value={filters[key] ?? ''}
                    onChange={(e) => setFilters({ [key]: e.target.value || null })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5
                               text-xs text-white focus:outline-none focus:border-gray-500" />
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* ── Lock overlay — shown when NOT logged in ── */}
        {!isLoggedIn && (
          <div className="absolute inset-0 top-[73px] flex flex-col items-center justify-center
                          bg-gray-950/40 backdrop-blur-[1px] z-10 px-6">
            <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 text-center
                            shadow-2xl w-full max-w-[220px]">
              <div className="w-12 h-12 bg-blue-500/15 rounded-full flex items-center
                              justify-center mx-auto mb-3">
                <Lock className="w-6 h-6 text-blue-400" />
              </div>
              <h3 className="text-white font-semibold text-sm mb-1">Sign In Required</h3>
              <p className="text-gray-400 text-xs leading-relaxed mb-4">
                Log in to filter events, set alerts, and interact with the map.
              </p>
              <button
                onClick={() => setShowAuth(true)}
                className="w-full py-2 rounded-lg text-xs font-semibold bg-blue-600
                           hover:bg-blue-500 text-white transition-colors flex items-center
                           justify-center gap-1.5">
                <Shield className="w-3.5 h-3.5" />
                Sign In / Register
              </button>
            </div>
          </div>
        )}

        {/* Footer reset */}
        {isLoggedIn && (
          <div className="px-4 py-3 border-t border-gray-800 flex-shrink-0">
            <button
              onClick={() => { resetFilters(); setLocationInput(''); }}
              className="w-full text-xs text-gray-500 hover:text-gray-300 transition-colors py-1">
              Reset all filters
            </button>
          </div>
        )}
      </aside>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </>
  );
}