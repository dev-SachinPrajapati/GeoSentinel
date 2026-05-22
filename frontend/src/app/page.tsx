'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import dynamic from 'next/dynamic';

import { fetchDisasters, fetchHeatmap, fetchStats } from '@/lib/api';
import { useAppStore } from '@/store';
import { useDisasterWebSocket } from '@/hooks/useWebSocket';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { NotificationPanel } from '@/components/notifications/NotificationPanel';
import { Timeline } from '@/components/timeline/Timeline';

const DisasterMap = dynamic(
  () => import('@/components/map/DisasterMap').then((m) => m.DisasterMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center bg-gray-900">
        <div className="text-center text-gray-400">
          <div className="text-4xl mb-3 animate-spin">🌍</div>
          <p className="text-sm">Loading map…</p>
        </div>
      </div>
    ),
  },
);

export default function DashboardPage() {
  useDisasterWebSocket();
  const { filters, showSidebar } = useAppStore();

  const { data: eventsData, error: eventsError, isLoading: eventsLoading } = useQuery({
    queryKey: ['disasters', filters],
    queryFn:  async () => {
      const res = await fetchDisasters(filters);
      if (typeof window !== 'undefined') {
        try {
          sessionStorage.setItem('cache_disasters_' + JSON.stringify(filters), JSON.stringify(res));
        } catch (e) {
          console.warn('[sessionStorage] error writing cache:', e);
        }
      }
      return res;
    },
    initialData: () => {
      if (typeof window !== 'undefined') {
        try {
          const cached = sessionStorage.getItem('cache_disasters_' + JSON.stringify(filters));
          return cached ? JSON.parse(cached) : undefined;
        } catch (e) {
          return undefined;
        }
      }
      return undefined;
    },
    refetchInterval: 30_000,
    retry:    3,
    staleTime: 15_000,
  });

  const timelineFilters = useMemo(() => {
    const { fromDt, toDt, ...rest } = filters;
    return rest;
  }, [filters]);

  const { data: unfilteredEventsData } = useQuery({
    queryKey: ['disasters', timelineFilters],
    queryFn:  async () => {
      const res = await fetchDisasters(timelineFilters);
      if (typeof window !== 'undefined') {
        try {
          sessionStorage.setItem('cache_unfiltered_' + JSON.stringify(timelineFilters), JSON.stringify(res));
        } catch (e) {
          console.warn('[sessionStorage] error writing cache:', e);
        }
      }
      return res;
    },
    initialData: () => {
      if (typeof window !== 'undefined') {
        try {
          const cached = sessionStorage.getItem('cache_unfiltered_' + JSON.stringify(timelineFilters));
          return cached ? JSON.parse(cached) : undefined;
        } catch (e) {
          return undefined;
        }
      }
      return undefined;
    },
    refetchInterval: 30_000,
    retry:    3,
    staleTime: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn:  async () => {
      const res = await fetchStats();
      if (typeof window !== 'undefined') {
        try {
          sessionStorage.setItem('cache_stats', JSON.stringify(res));
        } catch (e) {
          console.warn('[sessionStorage] error writing cache:', e);
        }
      }
      return res;
    },
    initialData: () => {
      if (typeof window !== 'undefined') {
        try {
          const cached = sessionStorage.getItem('cache_stats');
          return cached ? JSON.parse(cached) : undefined;
        } catch (e) {
          return undefined;
        }
      }
      return undefined;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const heatmapFilters = {
    fromDt: filters.fromDt ?? undefined,
    toDt:   filters.toDt   ?? undefined,
    types:  filters.types.length > 0 ? filters.types : undefined,
  };
  const { data: heatmapData } = useQuery({
    queryKey: ['heatmap', heatmapFilters],
    queryFn:  async () => {
      const res = await fetchHeatmap(heatmapFilters);
      if (typeof window !== 'undefined') {
        try {
          sessionStorage.setItem('cache_heatmap_' + JSON.stringify(heatmapFilters), JSON.stringify(res));
        } catch (e) {
          console.warn('[sessionStorage] error writing cache:', e);
        }
      }
      return res;
    },
    initialData: () => {
      if (typeof window !== 'undefined') {
        try {
          const cached = sessionStorage.getItem('cache_heatmap_' + JSON.stringify(heatmapFilters));
          return cached ? JSON.parse(cached) : undefined;
        } catch (e) {
          return undefined;
        }
      }
      return undefined;
    },
    staleTime: 60_000,
  });

  if (eventsError) console.error('[page] events error:', eventsError);

  const events        = eventsData?.data  ?? [];
  const totalEvents   = eventsData?.total ?? 0;
  const heatmapPoints = heatmapData?.data ?? [];
  const unfilteredEvents = unfilteredEventsData?.data ?? [];

  const timelineDates = useMemo(() => {
    if (!unfilteredEvents.length) {
      const now = new Date().toISOString();
      return { min: now, max: now };
    }
    const ts = unfilteredEvents.map((e) => new Date(e.occurred_at).getTime());
    return {
      min: new Date(Math.min(...ts)).toISOString(),
      max: new Date(Math.max(...ts)).toISOString(),
    };
  }, [unfilteredEvents]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-gray-950 flex flex-col">
      <Navbar />

      <div className="flex flex-1 overflow-hidden pt-12">
        {showSidebar && <Sidebar stats={stats} totalEvents={totalEvents} />}

        <div className="relative flex-1">
          {/* Loading spinner */}
          {eventsLoading && events.length === 0 && (
            <div className="absolute inset-0 z-10 flex items-center justify-center
                            bg-gray-950/70 pointer-events-none">
              <div className="text-center text-gray-300">
                <div className="text-4xl mb-3 animate-pulse">⏳</div>
                <p className="text-sm font-medium">Fetching live events…</p>
                <p className="text-xs text-gray-500 mt-1">
                  Connecting to {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
                </p>
              </div>
            </div>
          )}

          {/* Backend unreachable banner */}
          {eventsError && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-md w-full px-4">
              <div className="bg-red-950/95 border border-red-700 text-red-200 text-xs
                              px-4 py-3 rounded-xl shadow-2xl">
                <div className="font-semibold mb-1">⚠️ Cannot reach backend API</div>
                <div className="text-red-300/80">
                  Make sure uvicorn is running:
                  <code className="ml-1 bg-red-900/50 px-1.5 py-0.5 rounded font-mono">
                    uvicorn main:app --reload
                  </code>
                </div>
                <div className="text-red-400/60 mt-1 font-mono text-[10px]">
                  {String(eventsError)}
                </div>
              </div>
            </div>
          )}

          <DisasterMap events={events} heatmapPoints={heatmapPoints} />
          <NotificationPanel />
          <Timeline minDate={timelineDates.min} maxDate={timelineDates.max} />
        </div>
      </div>
    </div>
  );
}