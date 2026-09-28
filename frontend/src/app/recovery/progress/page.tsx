"use client";

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { apiClient } from '@/lib/apiClient';
import { Puzzle, CheckCircle2, Cpu, ArrowRight, Radio, Disc } from 'lucide-react';

export default function RecoveryProgressPage() {
  const router = useRouter();
  const { activeJobId, setCarvedFiles } = useSession();

  const [progress, setProgress] = useState<number>(10);
  const [stage, setStage] = useState<string>('Streaming Raw 4KB Physical Blocks...');
  const [isDone, setIsDone] = useState<boolean>(false);
  const [stats, setStats] = useState({
    blocks: 0,
    orphans: 0,
    streams: 0,
  });
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!activeJobId) {
      // If entered directly without an active job, simulate demo progress or return
      setProgress(100);
      setIsDone(true);
      return;
    }

    const pollStatus = async () => {
      try {
        const data = await apiClient.getCarvingStatus(activeJobId);
        if (data) {
          if (data.progress !== undefined) {
            setProgress(data.progress);
          }
          if (data.stage) {
            setStage(data.stage);
          }
          setStats({
            blocks: data.blocksScanned ?? 0,
            orphans: data.orphansCount ?? 0,
            streams: data.filesFound ?? 0,
          });

          if (data.status === "COMPLETED" || (data.progress !== undefined && data.progress >= 100)) {
            setIsDone(true);
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            // Fetch authentic carved artifacts
            const results = await apiClient.getCarvingResults(activeJobId);
            if (results?.files) {
              setCarvedFiles(results.files);
            }
            // Smoothly auto-navigate to results page
            setTimeout(() => {
              router.push(`/recovery/results?jobId=${activeJobId}`);
            }, 900);
          }
        }
      } catch (err) {
        console.warn("[Carving Telemetry] Polling status error:", err);
      }
    };

    // Immediate first check
    pollStatus();
    // Poll continuously every 800ms
    pollingRef.current = setInterval(pollStatus, 800);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [activeJobId, router, setCarvedFiles]);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
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
            <div className="text-xs sm:text-sm font-semibold text-teal-700 flex items-center space-x-1.5 sm:justify-end">
              <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isDone ? 'bg-emerald-400' : 'bg-teal-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${isDone ? 'bg-emerald-500' : 'bg-teal-500'}`}></span>
              </span>
              <span>{isDone ? 'Analysis Complete' : 'Active Scanner'}</span>
            </div>
          </div>
        </div>

        {/* Circular Radar / Visual Telemetry Radar */}
        <div className="flex flex-col items-center justify-center py-4">
          <div className="relative w-36 h-36 flex items-center justify-center">
            {/* Outer pulse circles */}
            <div className={`absolute inset-0 rounded-full border border-teal-200 ${isDone ? '' : 'animate-ping opacity-25'}`}></div>
            <div className="absolute inset-2 rounded-full border border-dashed border-teal-300 animate-spin" style={{ animationDuration: '12s' }}></div>
            <div className="absolute inset-6 rounded-full border border-slate-200"></div>

            {/* Sweep radar beam when scanning */}
            {!isDone && (
              <div
                className="absolute inset-0 rounded-full animate-spin pointer-events-none"
                style={{
                  background: 'conic-gradient(from 0deg, transparent 0deg, transparent 270deg, rgba(20, 184, 166, 0.25) 360deg)',
                  animationDuration: '2.5s',
                }}
              ></div>
            )}

            {/* Center metric indicator */}
            <div className="z-10 flex flex-col items-center justify-center text-center">
              {isDone ? (
                <CheckCircle2 className="w-10 h-10 text-emerald-500 animate-in zoom-in-75 duration-300" />
              ) : (
                <Disc className="w-8 h-8 text-teal-600 animate-spin" style={{ animationDuration: '4s' }} />
              )}
              <span className="text-base font-mono font-bold text-slate-800 mt-1">{progress}%</span>
            </div>
          </div>

          <div className="mt-4 text-center">
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-teal-50 text-teal-800 border border-teal-200">
              <Radio className="w-3.5 h-3.5 text-teal-600 animate-pulse" />
              <span>{stage}</span>
            </span>
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
          onClick={() => router.push(`/recovery/results?jobId=${activeJobId || ''}`)}
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
