'use client';

import { useAppStore } from '@/store';
import { DISASTER_COLORS, DISASTER_EMOJI, SEVERITY_COLORS, timeAgo } from '@/lib/mapUtils';
import { clsx } from 'clsx';

export function NotificationPanel() {
  const { notifications, markAllRead, showNotifications, unreadCount } = useAppStore();

  if (!showNotifications) return null;

  return (
    <div className="
      absolute top-14 right-4 z-50
      w-80 bg-gray-950/98 backdrop-blur-md
      border border-gray-700 rounded-xl shadow-2xl
      flex flex-col max-h-[480px] overflow-hidden
    ">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-white font-semibold text-sm">Alerts</span>
          {unreadCount > 0 && (
            <span className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
              {unreadCount}
            </span>
          )}
        </div>
        <button
          onClick={markAllRead}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Mark all read
        </button>
      </div>

      {/* Notification List */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-800/60">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-gray-500">
            <span className="text-3xl mb-2">🔕</span>
            <span className="text-sm">No alerts yet</span>
          </div>
        ) : (
          notifications.map((notif) => {
            const color = DISASTER_COLORS[notif.event.type];
            const severityColor = SEVERITY_COLORS[notif.event.severity];
            const isNearby = notif.type === 'nearby_alert';

            return (
              <div
                key={notif.id}
                className={clsx(
                  'px-4 py-3 transition-colors',
                  !notif.read ? 'bg-gray-800/40' : 'opacity-60'
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Icon */}
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm"
                    style={{ backgroundColor: color + '25' }}
                  >
                    {DISASTER_EMOJI[notif.event.type]}
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Badge row */}
                    <div className="flex items-center gap-1.5 mb-0.5">
                      {isNearby && (
                        <span className="text-xs bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded font-semibold">
                          NEARBY
                        </span>
                      )}
                      <span
                        className="text-xs px-1.5 py-0.5 rounded capitalize font-medium"
                        style={{ backgroundColor: severityColor + '20', color: severityColor }}
                      >
                        {notif.event.severity}
                      </span>
                    </div>

                    {/* Title */}
                    <p className="text-sm text-white font-medium leading-tight truncate">
                      {notif.event.title}
                    </p>

                    {/* Location + time */}
                    <p className="text-xs text-gray-500 mt-0.5">
                      {notif.event.country && `${notif.event.country} · `}
                      {timeAgo(notif.timestamp)}
                    </p>
                  </div>

                  {/* Unread dot */}
                  {!notif.read && (
                    <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1" />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
