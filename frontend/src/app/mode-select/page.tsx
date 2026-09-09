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
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-primary">Engage Operation Mode</h2>
        <p className="text-secondary text-lg">Select the primary directive for the initialized target.</p>
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
          className="relative flex flex-col items-center text-center p-10 glass-panel border-danger/30 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:-translate-y-1 hover:border-danger hover:shadow-[0_0_30px_-5px_rgba(244,63,94,0.3)]"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-danger/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-20 h-20 rounded-2xl bg-danger/10 border border-danger/30 flex items-center justify-center mb-6 group-hover:bg-danger/20 group-hover:scale-110 transition-all duration-500 glow-danger z-10">
            <Eraser className="w-10 h-10 text-danger drop-shadow-[0_0_8px_rgba(244,63,94,0.8)]" />
          </div>
          <h3 className="text-2xl font-bold text-danger mb-4 tracking-tight z-10 text-glow-danger">Erase & Sanitize</h3>
          <p className="text-secondary text-sm leading-relaxed z-10 font-medium">
            Permanently destroy data using <span className="font-mono text-primary/80 bg-black/40 px-1 rounded">IEEE 2883 Purge</span>. Write-enabled.
          </p>
        </button>

        {/* Recover & Carve */}
        <button
          onClick={() => handleSelectMode('recovery', '/recovery/scan')}
          className="relative flex flex-col items-center text-center p-10 glass-panel border-safe/30 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:-translate-y-1 hover:border-safe hover:shadow-[0_0_30px_-5px_rgba(20,184,166,0.3)]"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-safe/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-20 h-20 rounded-2xl bg-safe/10 border border-safe/30 flex items-center justify-center mb-6 group-hover:bg-safe/20 group-hover:scale-110 transition-all duration-500 glow-safe z-10">
            <Puzzle className="w-10 h-10 text-safe drop-shadow-[0_0_8px_rgba(20,184,166,0.8)]" />
          </div>
          <h3 className="text-2xl font-bold text-safe mb-4 tracking-tight z-10 text-glow-safe">Recover & Carve</h3>
          <p className="text-secondary text-sm leading-relaxed z-10 font-medium">
            Scan and reconstruct deleted files. Read-only, write-blocked.
          </p>
        </button>

        {/* Certify & Report */}
        <button
          onClick={() => handleSelectMode('neutral', '/certify/draft')}
          className="relative flex flex-col items-center text-center p-10 glass-panel border-success/30 rounded-2xl group cursor-pointer overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:-translate-y-1 hover:border-success hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.3)]"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-success/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="w-20 h-20 rounded-2xl bg-success/10 border border-success/30 flex items-center justify-center mb-6 group-hover:bg-success/20 group-hover:scale-110 transition-all duration-500 glow-success z-10">
            <FileBadge className="w-10 h-10 text-success drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
          </div>
          <h3 className="text-2xl font-bold text-success mb-4 tracking-tight z-10 text-glow-success">Certify & Report</h3>
          <p className="text-secondary text-sm leading-relaxed z-10 font-medium">
            Generate a <span className="font-mono text-primary/80 bg-black/40 px-1 rounded">Sec 63 BSA</span>-compliant certificate for a completed action.
          </p>
        </button>
      </div>
    </div>
  );
}
