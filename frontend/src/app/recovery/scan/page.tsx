"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { apiClient } from '@/lib/apiClient';
import { ShieldCheck, Cpu, Puzzle, Play, FileText, Image as ImageIcon, Archive, HardDrive } from 'lucide-react';

export default function RecoveryScanPage() {
  const router = useRouter();
  const { selectedDrive, setSelectedDrive, caseId, investigatorName, setActiveJobId, setCarvedFiles } = useSession();

  const [deepMl, setDeepMl] = useState<boolean>(true);
  const [selectedFormats, setSelectedFormats] = useState<string[]>(['images', 'documents', 'archives']);
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const toggleFormat = (key: string) => {
    setSelectedFormats((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  if (!selectedDrive) {
    return (
      <div className="max-w-2xl mx-auto my-12 p-8 bg-white border border-slate-200 rounded-2xl shadow-sm space-y-6 text-center animate-in fade-in duration-300">
        <div className="w-16 h-16 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <HardDrive className="w-8 h-8" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">No Carve Target Selected</h2>
          <p className="text-slate-500 text-sm mt-2 max-w-md mx-auto">
            Please choose a target storage volume or engage a connected USB flash drive to start carving.
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
                capacity: "7.5 GB",
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
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              Target Signature Categories
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              {selectedFormats.length} Active Filters
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => toggleFormat('images')}
              className={`p-3 border rounded-lg flex items-center justify-between transition-all text-left ${
                selectedFormats.includes('images')
                  ? 'border-teal-500 bg-teal-50/50 shadow-sm ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white opacity-60 hover:opacity-100 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center space-x-3">
                <ImageIcon className="w-5 h-5 text-teal-600" />
                <span className="text-sm font-medium text-slate-800">Images (JPEG/PNG)</span>
              </div>
              <span className={`w-4 h-4 rounded-full border text-[10px] font-bold flex items-center justify-center ${
                selectedFormats.includes('images') ? 'bg-teal-600 text-white border-teal-600' : 'border-slate-300'
              }`}>
                {selectedFormats.includes('images') && '✓'}
              </span>
            </button>

            <button
              type="button"
              onClick={() => toggleFormat('documents')}
              className={`p-3 border rounded-lg flex items-center justify-between transition-all text-left ${
                selectedFormats.includes('documents')
                  ? 'border-teal-500 bg-teal-50/50 shadow-sm ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white opacity-60 hover:opacity-100 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-teal-600" />
                <span className="text-sm font-medium text-slate-800">Documents (PDF)</span>
              </div>
              <span className={`w-4 h-4 rounded-full border text-[10px] font-bold flex items-center justify-center ${
                selectedFormats.includes('documents') ? 'bg-teal-600 text-white border-teal-600' : 'border-slate-300'
              }`}>
                {selectedFormats.includes('documents') && '✓'}
              </span>
            </button>

            <button
              type="button"
              onClick={() => toggleFormat('archives')}
              className={`p-3 border rounded-lg flex items-center justify-between transition-all text-left ${
                selectedFormats.includes('archives')
                  ? 'border-teal-500 bg-teal-50/50 shadow-sm ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white opacity-60 hover:opacity-100 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Archive className="w-5 h-5 text-teal-600" />
                <span className="text-sm font-medium text-slate-800">Archives (ZIP/DOCX)</span>
              </div>
              <span className={`w-4 h-4 rounded-full border text-[10px] font-bold flex items-center justify-center ${
                selectedFormats.includes('archives') ? 'bg-teal-600 text-white border-teal-600' : 'border-slate-300'
              }`}>
                {selectedFormats.includes('archives') && '✓'}
              </span>
            </button>
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
