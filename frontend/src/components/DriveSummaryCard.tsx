"use client";

import React, { useState } from 'react';
import { HardDrive, Copy, Check, ShieldCheck } from 'lucide-react';

interface DriveSummaryCardProps {
  serial: string;
  model: string;
  capacity: string;
  interfaceType: string;
  busType?: string;
}

export default function DriveSummaryCard({
  serial,
  model,
  capacity,
  interfaceType,
  busType,
}: DriveSummaryCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(serial);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 sm:p-5 relative overflow-hidden transition-all duration-200">
      {/* Header with Model and Interface Tag */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="p-2 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 shrink-0">
            <HardDrive className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 block">
              Active Storage Target
            </span>
            <h3 className="font-bold text-slate-900 text-base sm:text-lg tracking-tight truncate" title={model}>
              {model}
            </h3>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0 self-start sm:self-auto">
          <span className="px-2.5 py-1 text-xs font-mono font-semibold bg-slate-100 rounded-md text-slate-700 border border-slate-200 shadow-2xs">
            {interfaceType || 'Block Storage'}
          </span>
          {busType && (
            <span className="px-2.5 py-1 text-xs font-mono font-medium bg-slate-50 rounded-md text-slate-600 border border-slate-200">
              {busType}
            </span>
          )}
        </div>
      </div>
      
      {/* Metadata Grid with Screen-Scaling Protection */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-3 text-xs">
        {/* Serial Number with Copy Action */}
        <div className="bg-slate-50/70 p-2.5 rounded-lg border border-slate-100 min-w-0">
          <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold mb-1">
            Media Serial Number
          </p>
          <div className="flex items-center justify-between bg-white px-2.5 py-1 rounded border border-slate-200 shadow-2xs min-w-0">
            <span className="font-mono text-xs font-semibold text-slate-800 truncate" title={serial}>
              {serial}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              title="Copy Serial Number"
              className="text-slate-400 hover:text-slate-700 p-0.5 ml-1 transition shrink-0"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Capacity */}
        <div className="bg-slate-50/70 p-2.5 rounded-lg border border-slate-100 min-w-0">
          <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold mb-1">
            Storage Capacity
          </p>
          <div className="bg-white px-2.5 py-1 rounded border border-slate-200 shadow-2xs font-mono text-xs font-bold text-slate-800">
            {capacity}
          </div>
        </div>

        {/* Integrity Status */}
        <div className="bg-slate-50/70 p-2.5 rounded-lg border border-slate-100 min-w-0">
          <p className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold mb-1">
            Chain of Custody
          </p>
          <div className="bg-white px-2.5 py-1 rounded border border-slate-200 shadow-2xs flex items-center space-x-1.5 text-emerald-700 font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[11px] truncate">Hardware Bound</span>
          </div>
        </div>
      </div>
    </div>
  );
}
