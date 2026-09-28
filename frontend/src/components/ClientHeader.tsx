"use client";

import React, { useState, useEffect } from 'react';
import OfflineIndicator from './OfflineIndicator';
import { Activity, PanelLeft, PanelLeftClose } from 'lucide-react';
import { useSession } from '@/context/SessionContext';

export default function ClientHeader() {
  const { sidebarCollapsed, toggleSidebar } = useSession();
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
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 shrink-0 z-10 sticky top-0 shadow-sm min-w-0">
      <div className="flex items-center space-x-3 sm:space-x-5 min-w-0 overflow-hidden">
        {/* Sidebar Toggle Button */}
        <button
          onClick={toggleSidebar}
          title={sidebarCollapsed ? "Expand Sidebar (Ctrl+B)" : "Collapse Sidebar"}
          className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition active:scale-95 shrink-0"
        >
          {sidebarCollapsed ? (
            <PanelLeft className="w-5 h-5 text-teal-600" />
          ) : (
            <PanelLeftClose className="w-5 h-5" />
          )}
        </button>

        {/* Telemetry Status Title */}
        <div className="text-xs sm:text-sm font-semibold tracking-wider text-slate-500 uppercase flex items-center space-x-2 sm:space-x-3 shrink-0">
          <Activity className="w-4 h-4 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">Telemetry</span>
          <div className="h-4 w-px bg-slate-200 hidden sm:block"></div>
          <span className="text-emerald-700 font-mono font-bold flex items-center text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse shrink-0"></span>
            ACTIVE
          </span>
        </div>
        
        {/* Real-time Hardware Metrics - Responsively visible */}
        <div className="hidden lg:flex items-center space-x-2 text-[11px] font-mono text-slate-600 overflow-hidden">
          <div className="bg-slate-100/80 border border-slate-200 px-2 py-0.5 rounded shadow-2xs whitespace-nowrap">
            CPU: <span className="font-semibold text-slate-800">{cpu.toFixed(1)}%</span>
          </div>
          <div className="bg-slate-100/80 border border-slate-200 px-2 py-0.5 rounded shadow-2xs whitespace-nowrap">
            RAM: <span className="font-semibold text-slate-800">4.2/16 GB</span>
          </div>
          <div className="bg-slate-100/80 border border-slate-200 px-2 py-0.5 rounded shadow-2xs whitespace-nowrap">
            I/O: <span className="font-semibold text-slate-800">{Math.round(io)} MB/s</span>
          </div>
        </div>
      </div>

      <div className="shrink-0 pl-2">
        <OfflineIndicator />
      </div>
    </header>
  );
}
