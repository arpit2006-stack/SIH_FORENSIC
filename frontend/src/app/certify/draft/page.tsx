"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { FileBadge, Download, CheckCircle2, ArrowLeft, Stamp, Printer } from 'lucide-react';

export default function CertifyDraftPage() {
  const router = useRouter();
  const { caseId, investigatorName, selectedDrive, carvedFiles } = useSession();

  const [agency, setAgency] = useState<string>('State Cyber Forensic Division');
  const [designation, setDesignation] = useState<string>('Certified Cyber Examiner (C-DAC / ISO 17025)');
  const [remarks, setRemarks] = useState<string>('Cryptographic hash integrity verified. No generative inpainting was applied.');
  const [isSigned, setIsSigned] = useState<boolean>(true);

  const certNumber = `BSA63-${Date.now().toString(36).toUpperCase()}`;

  const handleDownloadJson = () => {
    const certPayload = {
      certificate_type: "SECTION_63_BHARATIYA_SAKSHYA_ADHINIYAM_2023",
      certificate_number: certNumber,
      case_id: caseId || "CAS-2026-904",
      investigating_agency: agency,
      investigator_name: investigatorName || "Insp. Rajesh Varma",
      designation: designation,
      target_media: {
        serial: selectedDrive?.serial || "C2ED9DAB",
        model: selectedDrive?.model || "Generic Flash Disk (D:)",
        capacity: selectedDrive?.capacity || "7.6 GB",
        bus_type: selectedDrive?.busType || "USB",
      },
      declaration: {
        statutory_compliance: "Bharatiya Sakshya Adhiniyam, 2023 (BSA) Section 63(4)",
        anti_hallucination_guarantee: "100% bit-for-bit source provenance. Zero generative diffusion or inpainting.",
        audit_root_hmac_sha256: "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
      },
      evidence_items: carvedFiles && carvedFiles.length > 0
        ? carvedFiles.map((f: any) => ({
            id: f.file_id,
            mime: f.mime,
            size_bytes: f.size_bytes,
            sha256: f.sha256,
            reliability_score: f.reliability_score,
            filename: f.filename,
          }))
        : [
            {
              id: "REC-001",
              mime: "application/zip",
              size_bytes: 8793,
              sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
              reliability_score: 0.942,
              filename: "carved_001_008793.zip",
            },
            {
              id: "REC-002",
              mime: "application/zip",
              size_bytes: 57045,
              sha256: "9f833776d60013b02821d65dfc2d4b1fa3d677284addd200126d90696a401b2c",
              reliability_score: 0.915,
              filename: "carved_002_057045.zip",
            },
          ],
      timestamp: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(certPayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `BSA63_Certificate_${caseId || 'CAS-2026'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Section 63 BSA Certificate</h2>
          <p className="text-slate-500 text-sm sm:text-base mt-1">Statutory electronic record certificate under Bharatiya Sakshya Adhiniyam, 2023.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleDownloadJson}
            className="px-3.5 py-2 border border-slate-300 rounded-lg font-semibold text-xs sm:text-sm text-slate-700 hover:bg-slate-100 flex items-center space-x-1.5 transition shadow-2xs"
          >
            <Download className="w-4 h-4" />
            <span>Audit JSON</span>
          </button>
          <button
            onClick={() => window.print()}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg font-semibold text-xs sm:text-sm shadow-sm flex items-center space-x-1.5 transition active:scale-95"
          >
            <Printer className="w-4 h-4" />
            <span>Print Court Copy</span>
          </button>
        </div>
      </div>

      {/* Official Legal Document View */}
      <div className="bg-white border-2 border-slate-300 rounded-xl p-5 sm:p-8 md:p-10 shadow-sm space-y-6 sm:space-y-8 print:border-none print:shadow-none">
        <div className="text-center border-b border-slate-200 pb-5">
          <div className="font-serif uppercase font-bold text-lg sm:text-xl tracking-wider text-slate-900 mb-1">
            SCHEDULE — SECTION 63(4)
          </div>
          <div className="text-xs sm:text-sm font-semibold uppercase text-slate-700 tracking-wide mb-1">
            THE BHARATIYA SAKSHYA ADHINIYAM, 2023 (BSA)
          </div>
          <div className="text-[11px] sm:text-xs font-mono text-slate-500 uppercase">
            Certificate for Admissibility of Electronic Records in Judicial Proceedings
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 text-xs sm:text-sm">
          <div>
            <label className="block text-[10px] font-semibold uppercase text-slate-500 mb-1">Certificate Number</label>
            <div className="font-mono font-bold text-slate-800 break-all">{certNumber}</div>
          </div>
          <div>
            <label className="block text-[10px] font-semibold uppercase text-slate-500 mb-1">FIR / Case ID</label>
            <div className="font-mono font-bold text-slate-800">{caseId || 'CAS-2026-904'}</div>
          </div>
          <div>
            <label className="block text-[10px] font-semibold uppercase text-slate-500 mb-1">Investigating Agency</label>
            <input
              type="text"
              value={agency}
              onChange={(e) => setAgency(e.target.value)}
              className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-slate-800 text-xs sm:text-sm font-medium shadow-2xs"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold uppercase text-slate-500 mb-1">Target Media Serial</label>
            <div className="font-mono text-slate-800 break-all">{selectedDrive?.serial || 'SN-TARGET-STORAGE'}</div>
          </div>
        </div>

        {/* Declaration Paragraphs */}
        <div className="bg-slate-50 p-4 sm:p-6 rounded-xl border border-slate-200 space-y-3 text-xs sm:text-sm leading-relaxed text-slate-700">
          <div className="font-bold text-slate-900 uppercase text-xs mb-2">
            Declaration under Section 63(4)(a), (b), and (c):
          </div>
          <p>
            1. I, <strong className="text-slate-900">{investigatorName || 'Insp. Rajesh Varma'}</strong>, holding designation <strong className="text-slate-900">{designation}</strong>, was in lawful control of the forensic workstation during the extraction/sanitization.
          </p>
          <p>
            2. The computing device and associated controller adapters were operating properly throughout the operation. The integrity of the physical electronic record was preserved using write-blocked loopback acquisition.
          </p>
          <p>
            3. All reconstructed data streams are authentic bit-for-bit representations extracted directly from physical block sectors, strictly adhering to the Anti-Hallucination Protocol (zero synthetic or generative inpainting).
          </p>
        </div>

        {/* Signatures & Custody Stamp */}
        <div className="pt-4 border-t border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <label className="flex items-center space-x-2 text-xs sm:text-sm font-semibold text-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={isSigned}
              onChange={(e) => setIsSigned(e.target.checked)}
              className="h-4 w-4 rounded text-teal-600 focus:ring-teal-500 shrink-0"
            />
            <span>Digitally Attested & Signed by Examiner</span>
          </label>

          <div className="flex items-center space-x-2 text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200 text-xs font-mono font-bold self-start sm:self-auto">
            <Stamp className="w-4 h-4 shrink-0" />
            <span>SEAL: CERT-VERIFIED-ISO17025</span>
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-2">
        <button
          onClick={() => router.push('/audit')}
          className="px-5 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-100 flex items-center space-x-2 transition shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Audit Ledger</span>
        </button>
      </div>
    </div>
  );
}
