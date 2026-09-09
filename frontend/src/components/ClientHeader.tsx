"use client";

import React from 'react';
import OfflineIndicator from './OfflineIndicator';

export default function ClientHeader() {
  return (
    <header className="h-16 glass-panel border-b-white/10 flex items-center justify-between px-8 shrink-0 z-10 sticky top-0 bg-surface/60">
      <div className="text-sm font-semibold tracking-widest text-secondary uppercase flex items-center space-x-4">
        <span>Session Telemetry</span>
        <div className="h-4 w-px bg-white/20"></div>
        <span className="text-primary font-mono opacity-80">ACTIVE</span>
      </div>
      <OfflineIndicator />
    </header>
  );
}
