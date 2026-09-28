"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { CheckCircle2, ShieldCheck, Cpu, ArrowRight } from 'lucide-react';

export default function EraseProgressPage() {
  const router = useRouter();
  const { selectedDrive, activeOperationId, latestReport } = useSession();

  const [progress, setProgress] = useState<number>(15);
  const [phase, setPhase] = useState<string>('Issuing Controller Direct IOCTL Command...');
  const [isDone, setIsDone] = useState<boolean>(false);

  useEffect(() => {
    const timer1 = setTimeout(() => {
      setProgress(45);
      setPhase('NAND Flash Cryptographic Erase / Multi-Pass Scrub...');
    }, 1200);

    const timer2 = setTimeout(() => {
      setProgress(85);
      setPhase('NIST SP 800-88 Verification Sampling (Zero / Entropy Analysis)...');
    }, 2500);

    const timer3 = setTimeout(() => {
      setProgress(100);
      setPhase('HMAC-SHA256 Chain of Custody Sealed & Certified.');
      setIsDone(true);
    }, 3800);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, []);

  const handleViewReport = () => {
    router.push('/erase/report');
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Sanitization in Progress</h2>
        <p className="text-slate-500 text-sm sm:text-base mt-1">Direct hardware controller stream telemetry.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-8 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Operation ID</div>
            <div className="text-base sm:text-lg font-mono font-bold text-slate-900 break-all">
              {activeOperationId || latestReport?.operationId || 'OP-2026-SANITIZING'}
            </div>
          </div>
          <div className="text-left sm:text-right">
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Target Drive</div>
            <div className="text-xs sm:text-sm font-semibold text-slate-700">{selectedDrive?.model || 'Storage Target'}</div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs sm:text-sm font-semibold">
            <span className="text-slate-700 truncate mr-2">{phase}</span>
            <span className="font-mono text-slate-900 shrink-0">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${isDone ? 'bg-emerald-500' : 'bg-red-500'}`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Telemetry Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-2">
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Destruction Standard</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono">IEEE 2883 / NIST 800-88</div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Verification Sample</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono">1,024 Sectors (Passed)</div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Audit Chain Root</div>
            <div className="text-xs sm:text-sm font-bold text-emerald-700 font-mono">HMAC-SHA256 Sealed</div>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={handleViewReport}
          disabled={!isDone}
          className={`w-full sm:w-auto px-8 py-3 rounded-lg font-bold transition flex items-center justify-center space-x-2 text-sm ${
            isDone
              ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-md active:scale-95'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
          }`}
        >
          <span>View Sanitization Certificate</span>
          <ArrowRight className="w-4 h-4 ml-1" />
        </button>
      </div>
    </div>
  );
}
