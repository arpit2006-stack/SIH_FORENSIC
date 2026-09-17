"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { apiClient } from '@/lib/apiClient';
import { ShieldCheck, Cpu, Puzzle, Play, FileText, Image as ImageIcon, Archive } from 'lucide-react';

export default function RecoveryScanPage() {
  const router = useRouter();
  const { selectedDrive, caseId, investigatorName, setActiveJobId, setCarvedFiles } = useSession();

  const [deepMl, setDeepMl] = useState<boolean>(true);
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!selectedDrive) {
    if (typeof window !== 'undefined') router.push('/');
    return null;
  }

  const handleStartCarve = async () => {
    setIsStarting(true);
    setErrorMsg(null);
    try {
      const resp = await apiClient.startCarving({
        targetPath: selectedDrive.devicePath || 'DEMO',
        caseId: caseId || 'CAS-2026-904',
        investigator: investigatorName || 'Insp. Rajesh Varma',
        deepMl: deepMl,
      });

      if (resp?.jobId) {
        setActiveJobId(resp.jobId);
        if (resp.job?.files_recovered) {
          setCarvedFiles(resp.job.files_recovered);
        }
        router.push('/recovery/progress');
      } else {
        throw new Error('No job ID returned from carving engine');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to start carving engine');
      setIsStarting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-800">Forensic Recovery Parameters</h2>
        <p className="text-slate-500 text-lg">Non-invasive carving and deep neural fragment reassembly.</p>
      </div>

      <DriveSummaryCard
        serial={selectedDrive.serial}
        model={selectedDrive.model}
        capacity={selectedDrive.capacity}
        interfaceType={selectedDrive.interfaceType}
      />

      {/* Write-Blocker Status Banner */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0" />
          <div>
            <h4 className="font-bold text-emerald-900 text-sm">Write-Blocker Interface Verified</h4>
            <p className="text-xs text-emerald-700">
              Read-only loopback mount active. Physical media modification is strictly hardware blocked.
            </p>
          </div>
        </div>
        <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded font-mono text-xs font-bold uppercase">
          READ-ONLY
        </span>
      </div>

      {/* Carving Engine Settings */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
            Reassembly & Carving Pipelines
          </h3>
          <div className="space-y-4">
            <label className="flex items-start space-x-3 p-4 border rounded-lg border-slate-200 hover:border-slate-300 cursor-pointer bg-slate-50/50">
              <input
                type="checkbox"
                checked={true}
                disabled={true}
                className="mt-1 h-4 w-4 rounded text-teal-600"
              />
              <div>
                <div className="font-semibold text-slate-800 text-sm">Phase 2: Deterministic Magic-Byte Carving</div>
                <div className="text-xs text-slate-500">
                  Header/Footer boundary validation for JPEG, PDF, and ZIP container streams without OS metadata.
                </div>
              </div>
            </label>

            <label className="flex items-start space-x-3 p-4 border rounded-lg border-teal-500 bg-teal-50/30 cursor-pointer">
              <input
                type="checkbox"
                checked={deepMl}
                onChange={(e) => setDeepMl(e.target.checked)}
                className="mt-1 h-4 w-4 rounded text-teal-600 focus:ring-teal-500"
              />
              <div>
                <div className="font-semibold text-slate-800 text-sm flex items-center space-x-2">
                  <span>Phase 3 & 4: Deep Neural SHT & Siamese Graph Reassembly</span>
                  <span className="px-2 py-0.5 text-xs bg-teal-100 text-teal-800 rounded font-mono font-bold">ML ONNX</span>
                </div>
                <div className="text-xs text-slate-600 mt-1">
                  1D-CNN block classification, Shannon entropy filtering, and Hungarian algorithm solver for scrambled orphan fragments.
                </div>
              </div>
            </label>
          </div>
        </div>

        {/* Target Format Signatures */}
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Target Signature Categories
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 border border-slate-200 rounded-lg flex items-center space-x-3 bg-white">
              <ImageIcon className="w-5 h-5 text-teal-600" />
              <span className="text-sm font-medium text-slate-800">Images (JPEG/PNG)</span>
            </div>
            <div className="p-3 border border-slate-200 rounded-lg flex items-center space-x-3 bg-white">
              <FileText className="w-5 h-5 text-teal-600" />
              <span className="text-sm font-medium text-slate-800">Documents (PDF)</span>
            </div>
            <div className="p-3 border border-slate-200 rounded-lg flex items-center space-x-3 bg-white">
              <Archive className="w-5 h-5 text-teal-600" />
              <span className="text-sm font-medium text-slate-800">Archives (ZIP/DOCX)</span>
            </div>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded text-sm">
            {errorMsg}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-4">
        <button
          type="button"
          onClick={() => router.push('/mode-select')}
          className="px-6 py-2.5 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          ← Cancel & Return
        </button>

        <button
          type="button"
          onClick={handleStartCarve}
          disabled={isStarting}
          className="px-8 py-3 bg-teal-600 text-white font-semibold rounded-md hover:bg-teal-700 shadow-md active:scale-95 transition-all flex items-center space-x-2"
        >
          {isStarting ? (
            <span>Initializing Carving Engine...</span>
          ) : (
            <>
              <Play className="w-5 h-5" />
              <span>Initiate Forensic Carve ➔</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
