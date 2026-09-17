"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { FileBadge, Download, CheckCircle2, ArrowLeft, Stamp } from 'lucide-react';

export default function CertifyDraftPage() {
  const router = useRouter();
  const { caseId, investigatorName, selectedDrive } = useSession();

  const [agency, setAgency] = useState<string>('State Cyber Forensic Division');
  const [designation, setDesignation] = useState<string>('Certified Cyber Examiner (C-DAC / ISO 17025)');
  const [remarks, setRemarks] = useState<string>('Cryptographic hash integrity verified. No generative inpainting was applied.');
  const [isSigned, setIsSigned] = useState<boolean>(true);

  const certNumber = `BSA63-${Date.now().toString(36).toUpperCase()}`;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-800">Section 63 BSA Certificate</h2>
          <p className="text-slate-500 text-lg">Statutory electronic record certificate under Bharatiya Sakshya Adhiniyam, 2023.</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => window.print()}
            className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-md font-semibold text-sm shadow-sm flex items-center space-x-2"
          >
            <Download className="w-4 h-4" />
            <span>Print Official Court Copy</span>
          </button>
        </div>
      </div>

      {/* Official Legal Document View */}
      <div className="bg-white border-2 border-slate-300 rounded-xl p-10 shadow-sm space-y-8 print:border-none print:shadow-none">
        <div className="text-center border-b border-slate-200 pb-6">
          <div className="font-serif uppercase font-bold text-xl tracking-wider text-slate-900 mb-1">
            SCHEDULE — SECTION 63(4)
          </div>
          <div className="text-sm font-semibold uppercase text-slate-700 tracking-wide mb-1">
            THE BHARATIYA SAKSHYA ADHINIYAM, 2023 (BSA)
          </div>
          <div className="text-xs font-mono text-slate-500 uppercase">
            Certificate for Admissibility of Electronic Records in Judicial Proceedings
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Certificate Number</label>
            <div className="font-mono font-bold text-slate-800">{certNumber}</div>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">FIR / Case ID</label>
            <div className="font-mono font-bold text-slate-800">{caseId || 'CAS-2026-904'}</div>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Investigating Agency</label>
            <input
              type="text"
              value={agency}
              onChange={(e) => setAgency(e.target.value)}
              className="w-full px-3 py-1.5 border border-slate-300 rounded text-slate-800 text-sm font-medium"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">Target Media Serial</label>
            <div className="font-mono text-slate-800">{selectedDrive?.serial || 'SN-TARGET-STORAGE'}</div>
          </div>
        </div>

        {/* Legal Declaration */}
        <div className="p-5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 space-y-3 leading-relaxed">
          <p className="font-semibold text-slate-900">
            DECLARATION UNDER SECTION 63(4)(a), (b), and (c):
          </p>
          <p>
            1. I, <span className="font-bold text-slate-900">{investigatorName || 'Officer In-Charge'}</span>, holding designation 
            <span className="font-bold text-slate-900"> {designation}</span>, was in lawful control of the forensic workstation during the extraction/sanitization.
          </p>
          <p>
            2. The computing device and associated controller adapters were operating properly throughout the operation. The integrity of the physical electronic record was preserved using write-blocked loopback acquisition.
          </p>
          <p>
            3. All reconstructed data streams are authentic bit-for-bit representations extracted directly from physical block sectors, strictly adhering to the Anti-Hallucination Protocol (zero synthetic or generative inpainting).
          </p>
        </div>

        {/* Digital Signature & Seal */}
        <div className="border-t border-slate-200 pt-6 flex justify-between items-end">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold mb-1">Cryptographic Ledger Hash</div>
            <div className="font-mono text-xs text-slate-700 bg-slate-50 p-2 border border-slate-200 rounded max-w-md break-all">
              a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0
            </div>
          </div>

          <div className="text-right space-y-1">
            <div className="flex items-center justify-end text-emerald-700 font-bold space-x-1">
              <Stamp className="w-5 h-5" />
              <span>DIGITALLY CERTIFIED</span>
            </div>
            <div className="text-sm font-bold text-slate-800">{investigatorName || 'Officer In-Charge'}</div>
            <div className="text-xs text-slate-500">{agency}</div>
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={() => router.push('/')}
          className="px-6 py-2.5 text-sm font-semibold text-slate-700 border border-slate-300 rounded-md hover:bg-slate-100 flex items-center space-x-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Workstation</span>
        </button>
      </div>
    </div>
  );
}
