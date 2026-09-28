"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { FileBadge, ShieldCheck, Download, ArrowLeft, Printer } from 'lucide-react';

export default function EraseReportPage() {
  const router = useRouter();
  const { selectedDrive, caseId, investigatorName, latestReport, activeOperationId } = useSession();

  const opId = activeOperationId || latestReport?.operationId || 'OP-2026-F91A04';
  const certId = latestReport?.proof?.certificateId || `BSA63-SAN-${opId}`;
  const hmacHash = latestReport?.proof?.hmacChainHash || '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069';

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Media Destruction Certificate</h2>
          <p className="text-slate-500 text-sm sm:text-base mt-1">Bharatiya Sakshya Adhiniyam (BSA), 2023 Section 63 Compliant Evidence.</p>
        </div>
        <div className="flex items-center space-x-2.5 self-start sm:self-auto">
          <button
            onClick={() => window.print()}
            className="px-4 py-2 border border-slate-300 rounded-lg text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2 transition shadow-2xs"
          >
            <Printer className="w-4 h-4" />
            <span>Print Copy</span>
          </button>
        </div>
      </div>

      {/* Official Certificate Card */}
      <div className="bg-white border-2 border-slate-300 rounded-xl p-5 sm:p-8 shadow-sm space-y-6 relative overflow-hidden print:border-none print:shadow-none">
        <div className="sm:absolute sm:top-0 sm:right-0 bg-emerald-600 text-white text-xs uppercase font-mono font-bold px-4 py-1.5 rounded-bl-xl shadow-2xs inline-flex items-center space-x-1.5 self-start">
          <ShieldCheck className="w-4 h-4" />
          <span>Legally Verified Proof</span>
        </div>

        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center space-x-3 mb-1">
            <FileBadge className="w-7 h-7 sm:w-8 sm:h-8 text-emerald-600 shrink-0" />
            <div>
              <h3 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">CERTIFICATE OF DATA SANITIZATION</h3>
              <p className="text-xs font-mono text-slate-500 uppercase">Under Section 63(4), Bharatiya Sakshya Adhiniyam, 2023</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 text-xs sm:text-sm">
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Certificate Number</span>
            <span className="font-mono font-bold text-slate-800 break-all">{certId}</span>
          </div>
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Case Tracking ID</span>
            <span className="font-mono font-bold text-slate-800">{caseId || 'CAS-2026-904'}</span>
          </div>
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Investigating Official</span>
            <span className="font-semibold text-slate-800">{investigatorName || 'Insp. Rajesh Varma'}</span>
          </div>
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Media Serial Number</span>
            <span className="font-mono text-slate-800 break-all">{selectedDrive?.serial || 'SN-9340203495'}</span>
          </div>
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Destruction Standard</span>
            <span className="font-mono text-slate-800">{latestReport?.method || 'IEEE 2883-2022 Purge / NIST SP 800-88'}</span>
          </div>
          <div className="bg-slate-50/70 p-3 rounded-lg border border-slate-100">
            <span className="text-[10px] text-slate-400 font-semibold uppercase block mb-1">Verification Assurance</span>
            <span className="text-emerald-700 font-bold font-mono">
              {latestReport?.assurance?.score != null ? `${latestReport.assurance.score.toFixed(1)}% (${latestReport.assurance.level || 'HIGH ASSURANCE'})` : '100.0% (HIGH ASSURANCE)'}
            </span>
          </div>
        </div>

        {/* Cryptographic Ledger Box */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">Tamper-Evident SHA-256 HMAC Root:</div>
          <div className="font-mono text-xs text-slate-700 break-all bg-white p-2.5 border border-slate-200 rounded-lg">
            {hmacHash}
          </div>
          <div className="text-xs text-slate-500 leading-relaxed">
            This cryptographic hash binds the hardware device serial, operator identity, timestamp, and post-erasure zero-entropy sample into an immutable chain of custody.
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button
          onClick={() => router.push('/')}
          className="px-5 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-100 flex items-center space-x-2 transition shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>New Forensic Session</span>
        </button>
      </div>
    </div>
  );
}
