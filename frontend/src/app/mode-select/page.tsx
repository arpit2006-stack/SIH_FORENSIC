"use client";

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { Eraser, Puzzle, FileBadge } from 'lucide-react';

export default function ModeSelectPage() {
  const router = useRouter();
  const { selectedDrive, setSessionMode } = useSession();

  useEffect(() => {
    if (!selectedDrive) {
      router.push('/');
    }
  }, [selectedDrive, router]);

  if (!selectedDrive) return null;

  const handleSelectMode = (mode: 'erase' | 'recovery' | 'neutral', path: string) => {
    setSessionMode(mode);
    router.push(path);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-10 animate-in fade-in zoom-in-95 duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-slate-800">Engage Operation Mode</h2>
        <p className="text-slate-500 text-lg">Select the primary directive for the initialized target.</p>
      </div>

      <div className="mb-10">
        <DriveSummaryCard
          serial={selectedDrive.serial}
          model={selectedDrive.model}
          capacity={selectedDrive.capacity}
          interfaceType={selectedDrive.interfaceType}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Erase & Sanitize */}
        <button
          onClick={() => handleSelectMode('erase', '/erase/confirm')}
          className="relative flex flex-col items-center text-center p-10 bg-white border border-slate-200 shadow-sm border-t-4 border-t-red-500 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-16 h-16 rounded-2xl bg-red-50 text-red-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-all duration-300 z-10">
            <Eraser className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-4 tracking-tight z-10">Erase & Sanitize</h3>
          <p className="text-slate-500 text-sm leading-relaxed z-10">
            Permanently destroy data using <span className="font-mono text-slate-700 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">IEEE 2883 Purge</span>. Write-enabled.
          </p>
        </button>

        {/* Recover & Carve */}
        <button
          onClick={() => handleSelectMode('recovery', '/recovery/scan')}
          className="relative flex flex-col items-center text-center p-10 bg-white border border-slate-200 shadow-sm border-t-4 border-t-teal-500 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-all duration-300 z-10">
            <Puzzle className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-4 tracking-tight z-10">Recover & Carve</h3>
          <p className="text-slate-500 text-sm leading-relaxed z-10">
            Scan and reconstruct deleted files. Read-only, write-blocked.
          </p>
        </button>

        {/* Certify & Report */}
        <button
          onClick={() => handleSelectMode('neutral', '/certify/draft')}
          className="relative flex flex-col items-center text-center p-10 bg-white border border-slate-200 shadow-sm border-t-4 border-t-green-500 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-16 h-16 rounded-2xl bg-green-50 text-green-600 flex items-center justify-center mb-6 group-hover:scale-110 transition-all duration-300 z-10">
            <FileBadge className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-4 tracking-tight z-10">Certify & Report</h3>
          <p className="text-slate-500 text-sm leading-relaxed z-10">
            Generate a <span className="font-mono text-slate-700 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">Sec 63 BSA</span>-compliant certificate for a completed action.
          </p>
        </button>
      </div>
    </div>
  );
}
