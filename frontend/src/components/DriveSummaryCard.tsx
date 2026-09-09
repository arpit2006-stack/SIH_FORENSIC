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
    <div className="glass-panel rounded-xl p-5 flex flex-col space-y-4 relative overflow-hidden group">
      {/* Subtle ambient glow in the background */}
      <div className="absolute -inset-1 bg-gradient-to-r from-safe/0 via-safe/5 to-safe/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur"></div>
      
      <div className="flex items-center justify-between border-b border-white/10 pb-3 relative z-10">
        <h3 className="font-bold text-primary text-xl tracking-tight">{model}</h3>
        <span className="px-3 py-1 text-xs font-mono font-bold bg-white/5 rounded text-safe border border-safe/30 glow-safe shadow-inner shadow-safe/10">
          {interfaceType}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-6 pt-1 relative z-10">
        <div>
          <p className="text-[10px] text-secondary uppercase tracking-widest font-bold mb-1">Serial Number</p>
          <p className="font-mono text-sm text-primary bg-black/30 px-3 py-1.5 rounded inline-block border border-white/5">{serial}</p>
        </div>
        <div>
          <p className="text-[10px] text-secondary uppercase tracking-widest font-bold mb-1">Capacity</p>
          <p className="font-mono text-sm text-primary bg-black/30 px-3 py-1.5 rounded inline-block border border-white/5">{capacity}</p>
        </div>
      </div>
    </div>
  );
}
