"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { Eraser, Puzzle, FileBadge, FileText, ArrowLeft, HardDrive, ShieldAlert, Cpu } from 'lucide-react';

export default function ModeSelectPage() {
  const router = useRouter();
  const { selectedDrive, setSelectedDrive, setSessionMode } = useSession();

  const handleSelectMode = (mode: 'erase' | 'recovery' | 'neutral', path: string) => {
    setSessionMode(mode);
    router.push(path);
  };

  if (!selectedDrive) {
    return (
      <div className="max-w-2xl mx-auto my-8 sm:my-12 p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-sm space-y-6 text-center animate-in fade-in duration-300">
        <div className="w-14 h-14 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <HardDrive className="w-7 h-7" />
        </div>
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">No Target Storage Media Selected</h2>
          <p className="text-slate-500 text-sm mt-2 max-w-md mx-auto">
            Please choose an active target drive or engage a forensic demo media volume to begin operations.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={() => router.push('/')}
            className="w-full sm:w-auto px-6 py-2.5 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800 transition shadow-sm"
          >
            ← Select Target on Dashboard
          </button>
          <button
            onClick={() => {
              setSelectedDrive({
                serial: "C2ED9DAB",
                model: "Generic Flash Disk (D:)",
                capacity: "7.6 GB",
                interfaceType: "USB Disk",
                health: "100%",
                temp: "32°C",
                busType: "USB",
                devicePath: "D:",
                isSystem: false,
              });
            }}
            className="w-full sm:w-auto px-6 py-2.5 bg-teal-50 text-teal-700 border border-teal-300 rounded-lg text-sm font-semibold hover:bg-teal-100 transition shadow-sm"
          >
            Engage Flash Disk (D:)
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Engage Operation Mode</h2>
          <p className="text-slate-500 text-sm sm:text-base mt-1">
            Select the primary forensic directive for the initialized storage media.
          </p>
        </div>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 border border-slate-300 rounded-lg text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2 transition self-start sm:self-auto shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Change Target Media</span>
        </button>
      </div>

      {/* Target Media Summary Card */}
      <DriveSummaryCard
        serial={selectedDrive.serial}
        model={selectedDrive.model}
        capacity={selectedDrive.capacity}
        interfaceType={selectedDrive.interfaceType}
        busType={selectedDrive.busType}
      />

      {/* Operation Mode Cards - Responsive for screen scaling */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-6">
        {/* Erase & Sanitize (Drive - PS Req 1) */}
        <button
          onClick={() => handleSelectMode('erase', '/erase/confirm')}
          className="relative flex flex-col justify-between text-left p-6 sm:p-7 bg-white border border-slate-200 shadow-sm border-t-4 border-t-red-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-md hover:border-slate-300"
        >
          <div>
            <div className="w-12 h-12 rounded-xl bg-red-50 text-red-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-200">
              <Eraser className="w-6 h-6" />
            </div>
            <div className="flex items-center space-x-2 mb-1.5">
              <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">Drive Eraser</h3>
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-red-100 text-red-800 rounded">PURGE</span>
            </div>
            <p className="text-slate-500 text-xs leading-relaxed mb-4">
              Full physical media wipe using <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">IEEE 2883-2022</span>. Direct controller IOCTL commands and NIST SP 800-88 verification.
            </p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-red-600 group-hover:text-red-700">
            <span>Open Authorization Gate ➔</span>
          </div>
        </button>

        {/* File & Slack Eraser (Targeted - PS Req 2) */}
        <button
          onClick={() => handleSelectMode('erase', '/file-eraser')}
          className="relative flex flex-col justify-between text-left p-6 sm:p-7 bg-white border border-slate-200 shadow-sm border-t-4 border-t-amber-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-md hover:border-slate-300"
        >
          <div>
            <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-200">
              <FileText className="w-6 h-6" />
            </div>
            <div className="flex items-center space-x-2 mb-1.5">
              <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">File & Slack Eraser</h3>
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-amber-100 text-amber-800 rounded">TARGETED</span>
            </div>
            <p className="text-slate-500 text-xs leading-relaxed mb-4">
              Targeted file/directory sanitization with <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">4KB Slack Space</span> and file metadata scrub complying with DoD 5220.22-M.
            </p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-amber-600 group-hover:text-amber-700">
            <span>Configure File Shredder ➔</span>
          </div>
        </button>

        {/* Recover & Carve (PS Req 3) */}
        <button
          id="mode-recover-carve-btn"
          onClick={() => handleSelectMode('recovery', '/recovery/scan')}
          className="relative flex flex-col justify-between text-left p-6 sm:p-7 bg-white border border-slate-200 shadow-sm border-t-4 border-t-teal-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-md hover:border-slate-300"
        >
          <div>
            <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-200">
              <Puzzle className="w-6 h-6" />
            </div>
            <div className="flex items-center space-x-2 mb-1.5">
              <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">Recover & Carve</h3>
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-teal-100 text-teal-800 rounded">AI-ML</span>
            </div>
            <p className="text-slate-500 text-xs leading-relaxed mb-4">
              Non-invasive carving with <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">Siamese Neural Nets</span> & Hungarian graph reassembly. Anti-hallucination source bytes.
            </p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-teal-600 group-hover:text-teal-700">
            <span>Start Carving Engine ➔</span>
          </div>
        </button>

        {/* Certify & Report */}
        <button
          onClick={() => handleSelectMode('neutral', '/certify/draft')}
          className="relative flex flex-col justify-between text-left p-6 sm:p-7 bg-white border border-slate-200 shadow-sm border-t-4 border-t-emerald-500 rounded-xl group cursor-pointer overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-md hover:border-slate-300"
        >
          <div>
            <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-200">
              <FileBadge className="w-6 h-6" />
            </div>
            <div className="flex items-center space-x-2 mb-1.5">
              <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">Certify & Report</h3>
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-emerald-100 text-emerald-800 rounded">LEGAL</span>
            </div>
            <p className="text-slate-500 text-xs leading-relaxed mb-4">
              Generate court-ready <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">Sec 63 BSA</span> electronic record certificates with HMAC-SHA256 tamper-evident custody seal.
            </p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-emerald-600 group-hover:text-emerald-700">
            <span>Generate Certificate ➔</span>
          </div>
        </button>
      </div>
    </div>
  );
}
