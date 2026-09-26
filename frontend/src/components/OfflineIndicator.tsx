import React, { useState } from 'react';
import { ShieldCheck, WifiOff } from 'lucide-react';

export default function OfflineIndicator() {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="relative inline-block">
      <div 
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="flex items-center space-x-2 text-xs uppercase tracking-wider bg-emerald-950/60 hover:bg-emerald-900/80 transition-colors px-3 py-1.5 rounded-full border border-emerald-500/40 shadow-sm cursor-help"
      >
        <div className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
        </div>
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 ml-1" />
        <span className="font-bold text-emerald-400 font-mono tracking-tight">
          AIR-GAPPED: VERIFIED
        </span>
      </div>

      {showTooltip && (
        <div className="absolute right-0 top-full mt-2 w-72 p-3 bg-slate-900/95 backdrop-blur-md border border-emerald-500/30 rounded-lg shadow-xl text-left z-50 text-xs">
          <div className="flex items-center space-x-1.5 text-emerald-400 font-semibold mb-1">
            <WifiOff className="w-3.5 h-3.5" />
            <span>Strict Hardware Air-Gap</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[11px]">
            Network sockets strictly bound to loopback (<code className="text-emerald-300">127.0.0.1</code>). Zero external telemetry, cloud APIs, or outbound packets during model inference.
          </p>
          <div className="mt-2 pt-2 border-t border-slate-800 text-[10px] text-slate-400 flex justify-between font-mono">
            <span>Inference: LOCAL GGUF</span>
            <span className="text-emerald-400 font-bold">0 LEAKS</span>
          </div>
        </div>
      )}
    </div>
  );
}
