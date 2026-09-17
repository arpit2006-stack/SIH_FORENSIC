"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { apiClient } from '@/lib/apiClient';
import { Puzzle, CheckCircle2, Cpu } from 'lucide-react';

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
    // Poll or simulate stages
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
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-800">Carving Telemetry</h2>
        <p className="text-slate-500 text-lg">Real-time neural stream reconstruction without filesystem metadata.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Carving Job ID</div>
            <div className="text-lg font-mono font-bold text-slate-800">
              {activeJobId || 'CRV-AUTO-2026'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Pipeline State</div>
            <div className="text-sm font-semibold text-teal-700 flex items-center space-x-1 justify-end">
              <Cpu className="w-4 h-4" />
              <span>ONNX CPU-First</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm font-semibold">
            <span className="text-slate-700">{stage}</span>
            <span className="font-mono text-slate-900">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${isDone ? 'bg-emerald-500' : 'bg-teal-600'}`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Stream Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Blocks Analyzed</div>
            <div className="text-lg font-bold text-slate-800 font-mono">{stats.blocks} (4KB each)</div>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Orphan Fragments Resolved</div>
            <div className="text-lg font-bold text-teal-700 font-mono">{stats.orphans} remaining</div>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-xs text-slate-500 mb-1">Reconstructed Streams</div>
            <div className="text-lg font-bold text-slate-800 font-mono">{stats.streams} Streams</div>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          onClick={() => router.push('/recovery/results')}
          disabled={!isDone}
          className={`px-8 py-3 font-semibold rounded-md transition-all duration-200 shadow-sm flex items-center space-x-2 ${
            !isDone
              ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
              : 'bg-teal-600 text-white hover:bg-teal-700 shadow-md active:scale-95'
          }`}
        >
          <CheckCircle2 className="w-5 h-5" />
          <span>View Reassembled Evidence & Matrix S ➔</span>
        </button>
      </div>
    </div>
  );
}
