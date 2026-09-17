import React from 'react';

interface DriveSummaryCardProps {
  serial: string;
  model: string;
  capacity: string;
  interfaceType: string;
}

export default function DriveSummaryCard({
  serial,
  model,
  capacity,
  interfaceType,
}: DriveSummaryCardProps) {
  return (
    <div className="bg-slate-100/50 border border-dashed border-slate-300 shadow-inner rounded-xl p-5 flex flex-col space-y-4 relative overflow-hidden transition-all duration-200">
      
      <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
        <h3 className="font-semibold text-slate-800 text-lg tracking-tight">{model}</h3>
        <span className="px-3 py-1 text-xs font-mono font-medium bg-white rounded text-slate-600 border border-slate-200 shadow-sm">
          {interfaceType}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-6 pt-1">
        <div>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-1">Serial Number</p>
          <p className="font-mono text-sm font-semibold text-slate-800 bg-white shadow-sm px-3 py-1.5 rounded inline-block border border-slate-200">{serial}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-1">Capacity</p>
          <p className="font-mono text-sm font-semibold text-slate-800 bg-white shadow-sm px-3 py-1.5 rounded inline-block border border-slate-200">{capacity}</p>
        </div>
      </div>
    </div>
  );
}
