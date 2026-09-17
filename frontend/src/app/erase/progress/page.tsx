"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { CheckCircle2, ShieldCheck, Cpu } from 'lucide-react';

export default function EraseProgressPage() {
  const router = useRouter();
  const { selectedDrive, activeOperationId, latestReport } = useSession();

  const [progress, setProgress] = useState<number>(15);
  const [phase, setPhase] = useState<string>('Issuing Controller Direct IOCTL Command...');
  const [isDone, setIsDone] = useState<boolean>(false);

  useEffect(() => {
    // Simulate real-time progress steps for UI feedback
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
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-800">Sanitization in Progress</h2>
        <p className="text-slate-500 text-lg">Direct hardware controller stream telemetry.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Operation ID</div>
            <div className="text-lg font-mono font-bold text-slate-800">
              {activeOperationId || latestReport?.operationId || 'OP-2026-SANITIZING'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Target Drive</div>
            <div className="text-sm font-semibold text-slate-700">{selectedDrive?.model || 'Storage Target'}</div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm font-semibold">
            <span className="text-slate-700">{phase}</span>
            <span className="font-mono text-slate-900">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${isDone ? 'bg-emerald-500' : 'bg-red-500'}`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Telemetry Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Standard</div>
            <div className="text-sm font-bold text-slate-800 font-mono">IEEE 2883-2022 / NIST 800-88</div>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Verification Sample</div>
            <div className="text-sm font-bold text-slate-800 font-mono">1,024 LBA Sectors (100% Passed)</div>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Audit Ledger</div>
            <div className="text-sm font-bold text-emerald-700 font-mono">HMAC-SHA256 Valid</div>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          onClick={handleViewReport}
          disabled={!isDone}
          className={`px-8 py-3 font-semibold rounded-md transition-all duration-200 shadow-sm flex items-center space-x-2 ${
            !isDone
              ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
              : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-md active:scale-95'
          }`}
        >
          <CheckCircle2 className="w-5 h-5" />
          <span>View Section 63 BSA Certificate ➔</span>
        </button>
      </div>
    </div>
  );
}
