'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

interface MRITimelineItem {
  id: string;
  date: string;
  timepoint: string;
}

interface MRIPlaybackModalProps {
  isOpen: boolean;
  onClose: () => void;
  mriScans: MRITimelineItem[];
  patientName: string;
}

export default function MRIPlaybackModal({
  isOpen,
  onClose,
  mriScans,
  patientName,
}: MRIPlaybackModalProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [loadedSet, setLoadedSet] = useState<Set<number>>(new Set());

  const n = mriScans.length;

  const goTo = useCallback(
    (index: number) => {
      setActiveIndex(Math.max(0, Math.min(n - 1, index)));
    },
    [n]
  );

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setActiveIndex(0);
      setLoadedSet(new Set());
    }
  }, [isOpen]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') goTo(activeIndex - 1);
      if (e.key === 'ArrowRight') goTo(activeIndex + 1);
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, activeIndex, goTo, onClose]);

  if (!isOpen || n === 0) return null;

  const activeScan = mriScans[activeIndex];
  const isMultiple = n > 1;
  const isActiveLoaded = loadedSet.has(activeIndex);

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
    });

  const formatTickLabel = (dateString: string) =>
    n > 6
      ? new Date(dateString).toLocaleDateString('en-US', {
          month: 'numeric',
          year: 'numeric',
        })
      : new Date(dateString).toLocaleDateString('en-US', {
          month: 'numeric',
          day: 'numeric',
          year: 'numeric',
        });

  const markLoaded = (index: number) =>
    setLoadedSet((prev) => new Set([...prev, index]));

  return (
    <div className="fixed inset-0 z-[200] bg-black flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center space-x-3 min-w-0">
          <span className="text-white font-semibold text-lg truncate max-w-xs">
            {patientName}
          </span>
          <span className="text-gray-400 text-sm flex-shrink-0">MRI Timeline</span>
        </div>
        <span className="text-gray-300 text-sm font-medium flex-shrink-0">
          Scan {activeIndex + 1} of {n}
        </span>
        <button
          onClick={onClose}
          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors flex-shrink-0"
          title="Close (Esc)"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Brain viewer area */}
      <div className="flex-1 relative overflow-hidden">
        {/* Loading overlay — sits on top while active iframe hasn't fired onLoad */}
        {!isActiveLoaded && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black space-y-3">
            <Loader2 className="w-10 h-10 text-[#2774AE] animate-spin" />
            <span className="text-gray-400 text-sm">Loading scan...</span>
          </div>
        )}

        {/* All iframes: active one is on top and visible; others are hidden but stay mounted */}
        {mriScans.map((scan, index) => {
          const isActive = index === activeIndex;
          return (
            <iframe
              key={scan.id}
              src={`/api/viewer/${scan.id}/test_db_nifti`}
              title={`MRI scan ${index + 1} — ${formatDate(scan.date)}`}
              onLoad={() => markLoaded(index)}
              sandbox="allow-scripts allow-same-origin allow-forms"
              style={{
                border: 'none',
                width: '100%',
                height: '100%',
                position: isActive ? 'relative' : 'absolute',
                top: 0,
                left: 0,
                opacity: isActive ? 1 : 0,
                pointerEvents: isActive ? 'auto' : 'none',
                zIndex: isActive ? 1 : 0,
              }}
            />
          );
        })}
      </div>

      {/* Bottom bar */}
      <div className="flex-shrink-0 bg-gray-900 border-t border-gray-700 px-6 py-4 space-y-3">
        {/* Metadata row */}
        <div className="flex items-center space-x-3 text-sm text-gray-300">
          <span className="font-medium text-white">{formatDate(activeScan.date)}</span>
          <span className="text-gray-600">·</span>
          <span>MRI</span>
          <span className="text-gray-600">·</span>
          <span>Scan {activeIndex + 1} of {n}</span>
          {activeScan.timepoint && (
            <>
              <span className="text-gray-600">·</span>
              <span className="text-gray-500">{activeScan.timepoint}</span>
            </>
          )}
        </div>

        {/* Scrubber — hidden when there is only one scan */}
        {isMultiple && (
          <div className="flex items-center space-x-3">
            <button
              onClick={() => goTo(activeIndex - 1)}
              disabled={activeIndex === 0}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
              title="Previous scan (←)"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>

            <div className="flex-1 space-y-2">
              <input
                type="range"
                min={0}
                max={n - 1}
                step={1}
                value={activeIndex}
                onChange={(e) => goTo(parseInt(e.target.value, 10))}
                className="w-full h-2 bg-gray-600 rounded-full appearance-none cursor-pointer accent-[#2774AE]"
              />
              {/* Date tick labels — positioned by percentage across the scrubber width */}
              <div className="relative h-4">
                {mriScans.map((scan, index) => (
                  <span
                    key={scan.id}
                    className={`absolute text-xs transform -translate-x-1/2 whitespace-nowrap transition-colors ${
                      index === activeIndex
                        ? 'text-[#2774AE] font-medium'
                        : 'text-gray-500'
                    }`}
                    style={{ left: `${(index / (n - 1)) * 100}%` }}
                  >
                    {formatTickLabel(scan.date)}
                  </span>
                ))}
              </div>
            </div>

            <button
              onClick={() => goTo(activeIndex + 1)}
              disabled={activeIndex === n - 1}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
              title="Next scan (→)"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
