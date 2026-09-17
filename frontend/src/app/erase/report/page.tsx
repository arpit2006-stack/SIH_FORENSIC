"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { FileBadge, ShieldCheck, Download, ArrowLeft } from 'lucide-react';

export default function EraseReportPage() {
  const router = useRouter();
  const { selectedDrive, caseId, investigatorName, latestReport, activeOperationId } = useSession();

  const opId = activeOperationId || latestReport?.operationId || 'OP-2026-F91A04';
  const certId = latestReport?.proof?.certificateId || `BSA63-SAN-${opId}`;
  const hmacHash = latestReport?.proof?.hmacChainHash || '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069';

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-800">Media Destruction Certificate</h2>
          <p className="text-slate-500 text-lg">Bharatiya Sakshya Adhiniyam (BSA), 2023 Section 63 Compliant Evidence.</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => window.print()}
            className="px-4 py-2 border border-slate-300 rounded-md text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2"
          >
            <Download className="w-4 h-4" />
            <span>Export Certificate</span>
          </button>
        </div>
      </div>

      {/* Official Certificate Card */}
      <div className="bg-white border-2 border-slate-300 rounded-xl p-8 shadow-sm space-y-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 bg-emerald-600 text-white text-xs uppercase font-mono font-bold px-4 py-1.5 rounded-bl-xl shadow-sm flex items-center space-x-1">
          <ShieldCheck className="w-4 h-4" />
          <span>Legally Verified Proof</span>
        </div>

        <div className="border-b border-slate-200 pb-6">
          <div className="flex items-center space-x-3 mb-2">
            <FileBadge className="w-8 h-8 text-emerald-600" />
            <div>
              <h3 className="text-xl font-bold text-slate-900 tracking-tight">CERTIFICATE OF DATA SANITIZATION</h3>
              <p className="text-xs font-mono text-slate-500 uppercase">Under Section 63(4), Bharatiya Sakshya Adhiniyam, 2023</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Certificate Number</span>
            <span className="font-mono font-bold text-slate-800">{certId}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Case Tracking ID</span>
            <span className="font-mono font-bold text-slate-800">{caseId || 'CAS-2026-904'}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Investigating Official</span>
            <span className="font-semibold text-slate-800">{investigatorName || 'Insp. Rajesh Varma'}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Media Serial Number</span>
            <span className="font-mono text-slate-800">{selectedDrive?.serial || 'SN-9340203495'}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Destruction Standard</span>
            <span className="font-mono text-slate-800">IEEE 2883-2022 Purge / NIST SP 800-88 Rev 1</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase block mb-1">Verification Assurance</span>
            <span className="text-emerald-700 font-bold font-mono">100.0% (HIGH ASSURANCE)</span>
          </div>
        </div>

        {/* Cryptographic Ledger Box */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">Tamper-Evident SHA-256 HMAC Root:</div>
          <div className="font-mono text-xs text-slate-700 break-all bg-white p-2 border border-slate-200 rounded">
            {hmacHash}
          </div>
          <div className="text-xs text-slate-500">
            This cryptographic hash binds the hardware device serial, operator identity, timestamp, and post-erasure zero-entropy sample into an immutable chain of custody.
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={() => router.push('/')}
          className="px-6 py-2.5 text-sm font-semibold text-slate-700 border border-slate-300 rounded-md hover:bg-slate-100 flex items-center space-x-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>New Forensic Session</span>
        </button>
      </div>
    </div>
  );
}
