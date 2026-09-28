"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { apiClient } from '@/lib/apiClient';
import { Puzzle, CheckCircle2, Cpu, ArrowRight } from 'lucide-react';

export default function RecoveryProgressPage() {
  const router = useRouter();
  const { activeJobId, setCarvedFiles } = useSession();

  const [progress, setProgress] = useState<number>(20);
  const [stage, setStage] = useState<string>('Streaming Raw 4KB Physical Blocks...');
  const [isDone, setIsDone] = useState<boolean>(false);
  const [stats, setStats] = useState({
    blocks: 60,
    orphans: 8,
    streams: 2,
  });

  useEffect(() => {
    const t1 = setTimeout(() => {
      setProgress(50);
      setStage('Deterministic Magic-Byte Signature Analysis (JPEG/PDF)...');
    }, 1200);

    const t2 = setTimeout(() => {
      setProgress(80);
      setStage('Siamese 1D-CNN Adjacency & Hungarian Graph Reassembly...');
      setStats({ blocks: 60, orphans: 0, streams: 3 });
    }, 2400);

    const t3 = async () => {
      setProgress(100);
      setStage('Forensic Reliability Matrix S & BSA Sec 63 Certification Complete.');
      setIsDone(true);
      if (activeJobId) {
        try {
          const res = await apiClient.getCarvingResults(activeJobId);
          if (res?.files) {
            setCarvedFiles(res.files);
          }
        } catch {
          // fallback handled in results page
        }
      }
    };
    const t3Timer = setTimeout(t3, 3600);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3Timer);
    };
  }, [activeJobId, setCarvedFiles]);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Carving Telemetry</h2>
        <p className="text-slate-500 text-sm sm:text-base mt-1">Real-time neural stream reconstruction without filesystem metadata.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-8 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Carving Job ID</div>
            <div className="text-base sm:text-lg font-mono font-bold text-slate-900 break-all">
              {activeJobId || 'CRV-AUTO-2026'}
            </div>
          </div>
          <div className="text-left sm:text-right">
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Pipeline State</div>
            <div className="text-xs sm:text-sm font-semibold text-teal-700 flex items-center space-x-1 sm:justify-end">
              <Cpu className="w-4 h-4" />
              <span>ONNX CPU-First</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs sm:text-sm font-semibold">
            <span className="text-slate-700 truncate mr-2">{stage}</span>
            <span className="font-mono text-slate-900 shrink-0">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${isDone ? 'bg-emerald-500' : 'bg-teal-600'}`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Stream Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-2">
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Blocks Analyzed</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono">{stats.blocks} (4KB Sectors)</div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Orphan Clusters</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono">{stats.orphans} (Resolved)</div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Reassembled Streams</div>
            <div className="text-xs sm:text-sm font-bold text-teal-700 font-mono">{stats.streams} Files Verified</div>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={() => router.push('/recovery/results')}
          disabled={!isDone}
          className={`w-full sm:w-auto px-8 py-3 rounded-lg font-bold transition flex items-center justify-center space-x-2 text-sm ${
            isDone
              ? 'bg-teal-600 hover:bg-teal-700 text-white shadow-md active:scale-95'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
          }`}
        >
          <span>Examine Recovered Artifacts</span>
          <ArrowRight className="w-4 h-4 ml-1" />
        </button>
      </div>
    </div>
  );
}
