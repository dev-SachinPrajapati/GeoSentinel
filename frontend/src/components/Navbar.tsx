'use client';

import { useState } from 'react';
import { LogOut, User, Shield } from 'lucide-react';
import Image from 'next/image';
import { clsx } from 'clsx';
import { useAppStore } from '@/store';
import { useAuthStore } from '@/store/authStore';
import { authApi } from '@/lib/authApi';
import { AuthModal } from '@/components/auth/AuthModal';

export function Navbar() {
  const {
    wsStatus, unreadCount,
    toggleSidebar, toggleNotifications, toggleTimeline,
    showNotifications, timelineActive,
  } = useAppStore();

  const { token, user, clearAuth } = useAuthStore();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showUserMenu, setShowUserMenu]   = useState(false);

  const handleLogout = async () => {
    if (token) {
      try { await authApi.logout(token); } catch { /* ignore */ }
    }
    clearAuth();
    setShowUserMenu(false);
  };

  const wsColors: Record<string, string> = {
    connected:    'bg-green-500',
    connecting:   'bg-yellow-500 animate-pulse',
    disconnected: 'bg-gray-500',
    error:        'bg-red-500',
    failed:       'bg-red-700',
  };
  const wsLabels: Record<string, string> = {
    connected: 'Live', connecting: 'Connecting…',
    disconnected: 'Offline', error: 'Error', failed: 'Failed',
  };

  return (
    <>
      <nav className="absolute top-0 left-0 right-0 z-40 h-12 flex items-center
                      justify-between px-4 bg-gray-950/90 backdrop-blur-sm border-b border-gray-800">

        {/* Left — sidebar toggle + brand */}
        <div className="flex items-center gap-3">
          <button onClick={toggleSidebar}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800"
            title="Toggle Sidebar">
            ☰
          </button>
          <div className="flex items-center gap-2">
             <Image
              src="/logo.png"
              alt="GeoSentinel logo"
              width={110}
              height={90}
              className="rounded-sm"
              priority
            />
            {/* <span className="text-white font-bold text-sm tracking-tight hidden sm:block"> GeoSentinel </span> */}
          </div>
        </div>

        {/* Right — controls */}
        <div className="flex items-center gap-2">
          {/* WS Status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full
                          bg-gray-800 border border-gray-700">
            <span className={clsx('w-2 h-2 rounded-full', wsColors[wsStatus] ?? 'bg-gray-500')} />
            <span className="text-xs text-gray-400 hidden sm:block">
              {wsLabels[wsStatus] ?? wsStatus}
            </span>
          </div>

          {/* Timeline */}
          <button onClick={toggleTimeline}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
              timelineActive
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
                : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'
            )}>
            🕐 History
          </button>

          {/* Notifications */}
          <button onClick={toggleNotifications}
            className={clsx(
              'relative p-2 rounded-lg text-sm transition-all border',
              showNotifications
                ? 'bg-gray-700 text-white border-gray-600'
                : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'
            )}>
            🔔
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 bg-red-500
                               text-white text-[10px] font-bold rounded-full flex
                               items-center justify-center px-0.5">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* ── Auth section ── */}
          {!user ? (
            /* Not logged in — show Sign In button */
            <button
              onClick={() => setShowAuthModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                         bg-blue-600 hover:bg-blue-500 text-white transition-colors border
                         border-blue-500/50">
              <Shield className="w-3.5 h-3.5" />
              Sign In
            </button>
          ) : (
            /* Logged in — avatar + dropdown */
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs
                           bg-gray-800 border border-gray-700 hover:border-gray-600
                           text-gray-300 transition-colors">
                <div className="w-5 h-5 bg-blue-600 rounded-full flex items-center justify-center">
                  <User className="w-3 h-3 text-white" />
                </div>
                <span className="hidden sm:block max-w-[100px] truncate font-medium text-white">
                  {user.name}
                </span>
              </button>

              {showUserMenu && (
                <div className="absolute right-0 top-full mt-2 w-56 bg-gray-900 border
                                border-gray-700 rounded-xl shadow-2xl py-2 z-50">
                  <div className="px-4 py-2 border-b border-gray-800">
                    <p className="text-white text-sm font-semibold truncate">{user.name}</p>
                    <p className="text-gray-500 text-xs truncate">{user.email}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm
                               text-red-400 hover:bg-red-500/10 transition-colors text-left">
                    <LogOut className="w-4 h-4" />
                    Sign Out
                  </button>
                </div>
              )}

              {/* Close menu on outside click */}
              {showUserMenu && (
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
              )}
            </div>
          )}
        </div>
      </nav>

      {/* Auth Modal */}
      {showAuthModal && <AuthModal onClose={() => setShowAuthModal(false)} />}
    </>
  );
}