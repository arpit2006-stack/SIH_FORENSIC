"use client";

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { Eraser, Puzzle, FileBadge, FileText, ArrowLeft } from 'lucide-react';

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
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in zoom-in-95 duration-500 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight mb-2 text-slate-800">Engage Operation Mode</h2>
          <p className="text-slate-500 text-lg">Select the primary directive for the initialized target.</p>
        </div>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 border border-slate-300 rounded-md text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Change Target</span>
        </button>
      </div>

      <div className="mb-6">
        <DriveSummaryCard
          serial={selectedDrive.serial}
          model={selectedDrive.model}
          capacity={selectedDrive.capacity}
          interfaceType={selectedDrive.interfaceType}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Erase & Sanitize (Drive - PS Req 1) */}
        <button
          onClick={() => handleSelectMode('erase', '/erase/confirm')}
          className="relative flex flex-col items-center text-center p-8 bg-white border border-slate-200 shadow-sm border-t-4 border-t-red-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300 text-left"
        >
          <div className="w-14 h-14 rounded-xl bg-red-50 text-red-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300 z-10">
            <Eraser className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-2 tracking-tight z-10">Drive Eraser</h3>
          <p className="text-slate-500 text-xs leading-relaxed z-10">
            Full physical media wipe using <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">IEEE 2883 Purge</span>. Direct controller IOCTLs.
          </p>
        </button>

        {/* File & Slack Eraser (Targeted - PS Req 2) */}
        <button
          onClick={() => handleSelectMode('erase', '/file-eraser')}
          className="relative flex flex-col items-center text-center p-8 bg-white border border-slate-200 shadow-sm border-t-4 border-t-amber-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300 text-left"
        >
          <div className="w-14 h-14 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300 z-10">
            <FileText className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-2 tracking-tight z-10">File & Slack Eraser</h3>
          <p className="text-slate-500 text-xs leading-relaxed z-10">
            Targeted file/directory sanitization with <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">4KB Slack Space</span> and metadata shredding.
          </p>
        </button>

        {/* Recover & Carve (PS Req 3) */}
        <button
          onClick={() => handleSelectMode('recovery', '/recovery/scan')}
          className="relative flex flex-col items-center text-center p-8 bg-white border border-slate-200 shadow-sm border-t-4 border-t-teal-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300 text-left"
        >
          <div className="w-14 h-14 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300 z-10">
            <Puzzle className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-2 tracking-tight z-10">Recover & Carve</h3>
          <p className="text-slate-500 text-xs leading-relaxed z-10">
            Non-invasive carving with <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">Siamese Neural Nets</span> & Hungarian graph reassembly.
          </p>
        </button>

        {/* Certify & Report */}
        <button
          onClick={() => handleSelectMode('neutral', '/certify/draft')}
          className="relative flex flex-col items-center text-center p-8 bg-white border border-slate-200 shadow-sm border-t-4 border-t-emerald-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-slate-300 text-left"
        >
          <div className="w-14 h-14 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300 z-10">
            <FileBadge className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-2 tracking-tight z-10">Certify & Report</h3>
          <p className="text-slate-500 text-xs leading-relaxed z-10">
            Generate court-ready <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">Sec 63 BSA</span> electronic record certificates.
          </p>
        </button>
      </div>
    </div>
  );
}
