"use client";

import React, { useState, useEffect } from 'react';
import OfflineIndicator from './OfflineIndicator';
import { Activity } from 'lucide-react';

export default function ClientHeader() {
  const [cpu, setCpu] = useState(12);
  const [io, setIo] = useState(350);

  useEffect(() => {
    const interval = setInterval(() => {
      setCpu(prev => Math.max(5, Math.min(95, prev + (Math.random() * 10 - 5))));
      setIo(prev => Math.max(10, Math.min(900, prev + (Math.random() * 100 - 50))));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shrink-0 z-10 sticky top-0 shadow-sm">
      <div className="flex items-center space-x-6">
        <div className="text-sm font-semibold tracking-widest text-slate-500 uppercase flex items-center space-x-4">
          <Activity className="w-4 h-4 text-slate-400" />
          <span>Session Telemetry</span>
          <div className="h-4 w-px bg-slate-200"></div>
          <span className="text-emerald-600 font-mono font-bold flex items-center">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
            ACTIVE
          </span>
        </div>
        
        {/* Simulated Metrics */}
        <div className="hidden md:flex items-center space-x-4 text-xs font-mono text-slate-500">
          <div className="bg-slate-50 border border-slate-200 px-2 py-1 rounded">
            CPU: {cpu.toFixed(1)}%
          </div>
          <div className="bg-slate-50 border border-slate-200 px-2 py-1 rounded">
            RAM: 4.2GB / 16.0GB
          </div>
          <div className="bg-slate-50 border border-slate-200 px-2 py-1 rounded">
            DISK I/O: {Math.round(io)} MB/s
          </div>
        </div>
      </div>
      <OfflineIndicator />
    </header>
  );
}
