'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store';
import { clsx } from 'clsx';

interface TimelineProps {
  minDate: string;
  maxDate: string;
}

export function Timeline({ minDate, maxDate }: TimelineProps) {
  const { timelineActive, timelineValue, setTimelineValue, toggleTimeline, setFilters } = useAppStore();
  const [isPlaying, setIsPlaying] = useState(false);
  const playRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const sliderToDate = useCallback(
    (value: number): Date => {
      const min = new Date(minDate).getTime();
      const max = new Date(maxDate).getTime();
      return new Date(min + (value / 100) * (max - min));
    },
    [minDate, maxDate]
  );

  const formatDate = (value: number) => {
    const d = sliderToDate(value);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  // On slider change → update toDt filter
  const handleSliderChange = useCallback(
    (value: number) => {
      setTimelineValue(value);
      const cutoff = sliderToDate(value);
      setFilters({ toDt: cutoff.toISOString() });
    },
    [setTimelineValue, sliderToDate, setFilters]
  );

  // Auto-play
  const startPlay = useCallback(() => {
    setIsPlaying(true);
    playRef.current = setInterval(() => {
      setTimelineValue(
        useAppStore.getState().timelineValue >= 100
          ? 0
          : Math.min(100, useAppStore.getState().timelineValue + 0.5)
      );
    }, 100);
  }, [setTimelineValue]);

  const stopPlay = useCallback(() => {
    setIsPlaying(false);
    if (playRef.current) clearInterval(playRef.current);
  }, []);

  useEffect(() => {
    if (!timelineActive) {
      stopPlay();
      setFilters({ toDt: null }); // Reset time filter
    }
  }, [timelineActive, stopPlay, setFilters]);

  useEffect(() => () => stopPlay(), [stopPlay]);

  if (!timelineActive) return null;

  return (
    <div className="
      absolute bottom-10 left-1/2 -translate-x-1/2
      w-full max-w-2xl px-6 py-4
      bg-gray-950/95 backdrop-blur-sm
      border border-gray-700 rounded-2xl shadow-2xl
      mx-4
    ">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-white text-sm font-semibold">Historical Playback</span>
        <span className="text-blue-400 text-xs font-mono bg-blue-500/10 px-2 py-0.5 rounded">
          {formatDate(timelineValue)}
        </span>
        <button
          onClick={toggleTimeline}
          className="ml-auto text-gray-500 hover:text-gray-300 text-xs"
        >
          ✕ Close
        </button>
      </div>

      <div className="flex items-center gap-3">
        {/* Play/Pause */}
        <button
          onClick={isPlaying ? stopPlay : startPlay}
          className="
            w-8 h-8 flex items-center justify-center
            bg-blue-600 hover:bg-blue-500 rounded-full
            text-white text-sm transition-colors flex-shrink-0
          "
        >
          {isPlaying ? '⏸' : '▶'}
        </button>

        {/* Timeline labels */}
        <div className="text-xs text-gray-500 w-16 text-right flex-shrink-0">
          {new Date(minDate).toLocaleDateString()}
        </div>

        {/* Slider */}
        <div className="flex-1 relative">
          <input
            type="range"
            min={0}
            max={100}
            step={0.1}
            value={timelineValue}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className="w-full accent-blue-500 cursor-pointer h-2"
          />
        </div>

        <div className="text-xs text-gray-500 w-16 flex-shrink-0">
          {new Date(maxDate).toLocaleDateString()}
        </div>

        {/* Reset */}
        <button
          onClick={() => handleSliderChange(100)}
          className="text-gray-500 hover:text-gray-300 text-xs flex-shrink-0"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
