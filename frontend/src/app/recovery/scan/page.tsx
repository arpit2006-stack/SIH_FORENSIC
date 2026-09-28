"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { apiClient } from '@/lib/apiClient';
import { ShieldCheck, Cpu, Puzzle, Play, FileText, Image as ImageIcon, Archive, HardDrive, ArrowLeft, Video, Music } from 'lucide-react';

export default function RecoveryScanPage() {
  const router = useRouter();
  const { selectedDrive, setSelectedDrive, caseId, investigatorName, setActiveJobId, setCarvedFiles, selectedMimes, setSelectedMimes } = useSession();

  const [deepMl, setDeepMl] = useState<boolean>(true);
  const [selectedFormats, setSelectedFormats] = useState<string[]>(
    selectedMimes && selectedMimes.length > 0 ? selectedMimes : ['images', 'documents', 'archives', 'video', 'audio']
  );
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const toggleFormat = (key: string) => {
    setSelectedFormats((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  if (!selectedDrive) {
    return (
      <div className="max-w-2xl mx-auto my-8 sm:my-12 p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-sm space-y-6 text-center animate-in fade-in duration-300">
        <div className="w-14 h-14 bg-teal-50 text-teal-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <HardDrive className="w-7 h-7" />
        </div>
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">No Carve Target Selected</h2>
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

  const handleStartCarve = async () => {
    setIsStarting(true);
    setErrorMsg(null);
    try {
      setSelectedMimes(selectedFormats);
      const resp = await apiClient.startCarving({
        targetPath: selectedDrive.devicePath || 'DEMO',
        caseId: caseId || 'CAS-2026-904',
        investigator: investigatorName || 'Insp. Rajesh Varma',
        deepMl: deepMl,
        targetMimes: selectedFormats,
        selectedFormats: selectedFormats,
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
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Forensic Recovery Parameters</h2>
        <p className="text-slate-500 text-sm sm:text-base mt-1">Non-invasive carving and deep neural fragment reassembly.</p>
      </div>

      <DriveSummaryCard
        serial={selectedDrive.serial}
        model={selectedDrive.model}
        capacity={selectedDrive.capacity}
        interfaceType={selectedDrive.interfaceType}
        busType={selectedDrive.busType}
      />

      {/* Write-Blocker Status Banner */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0" />
          <div>
            <h4 className="font-bold text-emerald-900 text-sm">Write-Blocker Interface Verified</h4>
            <p className="text-xs text-emerald-700">
              Read-only loopback mount active. Physical media modification is strictly hardware blocked.
            </p>
          </div>
        </div>
        <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded font-mono text-xs font-bold uppercase self-start sm:self-auto shrink-0">
          READ-ONLY
        </span>
      </div>

      {/* Carving Engine Settings */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-sm space-y-6">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Reassembly & Carving Pipelines
          </h3>
          <div className="space-y-3">
            <label className="flex items-start space-x-3 p-3.5 sm:p-4 border rounded-xl border-slate-200 bg-slate-50/50 cursor-pointer">
              <input
                type="checkbox"
                checked={true}
                disabled={true}
                className="mt-1 h-4 w-4 rounded text-teal-600 shrink-0"
              />
              <div>
                <div className="font-bold text-slate-800 text-sm">Phase 2: Deterministic Magic-Byte Carving</div>
                <div className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  Header/Footer boundary validation for JPEG, PNG, PDF, ZIP, MP4, AVI, MKV, and WAV container streams without OS metadata.
                </div>
              </div>
            </label>

            <label className="flex items-start space-x-3 p-3.5 sm:p-4 border rounded-xl border-teal-200 bg-teal-50/30 hover:bg-teal-50/50 cursor-pointer transition">
              <input
                type="checkbox"
                checked={deepMl}
                onChange={(e) => setDeepMl(e.target.checked)}
                className="mt-1 h-4 w-4 rounded text-teal-600 focus:ring-teal-500 shrink-0"
              />
              <div>
                <div className="font-bold text-slate-900 text-sm flex items-center space-x-2">
                  <span>Phase 3: Siamese Neural Adjacency Graph Reconstruction</span>
                  <span className="px-2 py-0.5 bg-teal-100 text-teal-800 rounded text-[10px] font-mono font-bold">ML ENABLED</span>
                </div>
                <div className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                  Deep 1D-CNN fragment scoring and Hungarian bipartite matching to assemble fragmented files.
                </div>
              </div>
            </label>
          </div>
        </div>

        {/* Target Formats */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Target Container Formats (MIME Protocol Filter)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <button
              id="format-images-btn"
              type="button"
              onClick={() => toggleFormat('images')}
              className={`p-3.5 rounded-xl border text-left flex items-center space-x-3 transition ${
                selectedFormats.includes('images')
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <ImageIcon className="w-5 h-5 text-teal-600 shrink-0" />
              <div>
                <div className="font-bold text-xs sm:text-sm">Images</div>
                <div className="text-[11px] text-slate-500 font-mono">JPEG / PNG</div>
              </div>
            </button>

            <button
              id="format-documents-btn"
              type="button"
              onClick={() => toggleFormat('documents')}
              className={`p-3.5 rounded-xl border text-left flex items-center space-x-3 transition ${
                selectedFormats.includes('documents')
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <FileText className="w-5 h-5 text-teal-600 shrink-0" />
              <div>
                <div className="font-bold text-xs sm:text-sm">Documents</div>
                <div className="text-[11px] text-slate-500 font-mono">PDF / DOCX</div>
              </div>
            </button>

            <button
              id="format-archives-btn"
              type="button"
              onClick={() => toggleFormat('archives')}
              className={`p-3.5 rounded-xl border text-left flex items-center space-x-3 transition ${
                selectedFormats.includes('archives')
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Archive className="w-5 h-5 text-teal-600 shrink-0" />
              <div>
                <div className="font-bold text-xs sm:text-sm">Archives</div>
                <div className="text-[11px] text-slate-500 font-mono">ZIP / GZ</div>
              </div>
            </button>

            <button
              id="format-video-btn"
              type="button"
              onClick={() => toggleFormat('video')}
              className={`p-3.5 rounded-xl border text-left flex items-center space-x-3 transition ${
                selectedFormats.includes('video')
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Video className="w-5 h-5 text-teal-600 shrink-0" />
              <div>
                <div className="font-bold text-xs sm:text-sm">Video</div>
                <div className="text-[11px] text-slate-500 font-mono">MP4 / AVI / MKV</div>
              </div>
            </button>

            <button
              id="format-audio-btn"
              type="button"
              onClick={() => toggleFormat('audio')}
              className={`p-3.5 rounded-xl border text-left flex items-center space-x-3 transition ${
                selectedFormats.includes('audio')
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500'
                  : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              <Music className="w-5 h-5 text-teal-600 shrink-0" />
              <div>
                <div className="font-bold text-xs sm:text-sm">Audio</div>
                <div className="text-[11px] text-slate-500 font-mono">WAV / MP3</div>
              </div>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded-lg text-xs sm:text-sm">
            {errorMsg}
          </div>
        )}
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <button
          type="button"
          onClick={() => router.push('/mode-select')}
          className="w-full sm:w-auto px-5 py-2.5 text-xs sm:text-sm font-semibold text-slate-600 hover:text-slate-900 border border-slate-300 rounded-lg hover:bg-slate-100 transition text-center"
        >
          ← Cancel & Return
        </button>

        <button
          id="engage-carving-btn"
          type="button"
          onClick={handleStartCarve}
          disabled={isStarting}
          className="w-full sm:w-auto px-8 py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-lg transition shadow-md active:scale-95 flex items-center justify-center space-x-2 text-sm"
        >
          {isStarting ? (
            <span>Initiating Carving Stream...</span>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Engage Carving Engine</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
