import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { DisasterEvent, DisasterFilters, MapViewState, Notification, defaultFilters } from '@/types';
import { nanoid } from 'nanoid';

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'failed';

interface AppState {
  // Map
  viewState: MapViewState;
  setViewState: (vs: MapViewState) => void;
  selectedEvent: DisasterEvent | null;
  setSelectedEvent: (e: DisasterEvent | null) => void;

  // Filters
  filters: DisasterFilters;
  setFilters: (f: Partial<DisasterFilters>) => void;
  resetFilters: () => void;

  // UI toggles
  showHeatmap: boolean;
  toggleHeatmap: () => void;
  showSidebar: boolean;
  toggleSidebar: () => void;
  showNotifications: boolean;
  toggleNotifications: () => void;

  // Live events (from WebSocket)
  liveEvents: DisasterEvent[];
  addLiveEvent: (e: DisasterEvent) => void;
  clearLiveEvents: () => void;

  // Notifications
  notifications: Notification[];
  addNotification: (n: Omit<Notification, 'id' | 'read'>) => void;
  markAllRead: () => void;
  unreadCount: number;

  // Timeline
  timelineActive: boolean;
  timelineValue: number; // 0-100 percent
  setTimelineValue: (v: number) => void;
  toggleTimeline: () => void;

  // WebSocket status
  wsStatus: WsStatus;
  setWsStatus: (s: WsStatus) => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    (set, get) => ({
      // Map
      viewState: { longitude: 20, latitude: 20, zoom: 2 },
      setViewState: (viewState) => set({ viewState }),
      selectedEvent: null,
      setSelectedEvent: (selectedEvent) => set({ selectedEvent }),

      // Filters
      filters: defaultFilters,
      setFilters: (partial) =>
        set((s) => ({ filters: { ...s.filters, ...partial } })),
      resetFilters: () => set({ filters: defaultFilters }),

      // UI toggles
      showHeatmap: false,
      toggleHeatmap: () => set((s) => ({ showHeatmap: !s.showHeatmap })),
      showSidebar: true,
      toggleSidebar: () => set((s) => ({ showSidebar: !s.showSidebar })),
      showNotifications: false,
      toggleNotifications: () =>
        set((s) => ({ showNotifications: !s.showNotifications })),

      // Live events
      liveEvents: [],
      addLiveEvent: (event) =>
        set((s) => ({
          liveEvents: [event, ...s.liveEvents].slice(0, 200), // cap at 200
        })),
      clearLiveEvents: () => set({ liveEvents: [] }),

      // Notifications
      notifications: [],
      addNotification: (n) =>
        set((s) => {
          const notification: Notification = {
            ...n,
            id: nanoid(),
            read: false,
          };
          const notifications = [notification, ...s.notifications].slice(0, 50);
          return { notifications, unreadCount: s.unreadCount + 1 };
        }),
      markAllRead: () =>
        set((s) => ({
          notifications: s.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        })),
      unreadCount: 0,

      // Timeline
      timelineActive: false,
      timelineValue: 100,
      setTimelineValue: (timelineValue) => set({ timelineValue }),
      toggleTimeline: () =>
        set((s) => ({ timelineActive: !s.timelineActive })),

      // WebSocket
      wsStatus: 'connecting',
      setWsStatus: (wsStatus) => set({ wsStatus }),
    }),
    { name: 'disaster-monitor' }
  )
);
