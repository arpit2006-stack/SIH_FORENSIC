import React from 'react';

export default function OfflineIndicator() {
  return (
    <div className="flex items-center space-x-3 text-xs uppercase tracking-widest text-secondary glass-panel px-4 py-2 rounded-full border border-safe/20 shadow-inner shadow-safe/10">
      <div className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-safe opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-safe glow-safe"></span>
      </div>
      <span className="font-bold text-safe/80">Local — No Network</span>
    </div>
  );
}
