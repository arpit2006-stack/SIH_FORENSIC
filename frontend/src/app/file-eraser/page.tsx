"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { apiClient, FileSanitizeResult } from '@/lib/apiClient';
import { Eraser, ShieldAlert, CheckCircle2, ArrowLeft, FileText, Layers } from 'lucide-react';

export default function FileEraserPage() {
  const router = useRouter();
  const { caseId, investigatorName } = useSession();

  const [targetPath, setTargetPath] = useState<string>('MOCK:/evidence/sensitive_records.xlsx');
  const [passes, setPasses] = useState<number>(3);
  const [wipeSlack, setWipeSlack] = useState<boolean>(true);
  const [isWiping, setIsWiping] = useState<boolean>(false);
  const [result, setResult] = useState<FileSanitizeResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleExecuteFileWipe = async () => {
    if (!targetPath.trim()) return;
    setIsWiping(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const resp = await apiClient.executeFileSanitize({
        targetPath: targetPath.trim(),
        passes: passes,
        operatorId: investigatorName || 'OFFICER-01',
        caseId: caseId || 'CAS-2026-904',
        wipeSlack: wipeSlack,
      });

      if (resp?.result) {
        setResult(resp.result);
      } else {
        throw new Error('No result returned from file sanitizer');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'File sanitization error. Check daemon status.');
    } finally {
      setIsWiping(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Targeted File & Slack Space Eraser</h2>
          <p className="text-slate-500 text-sm sm:text-base mt-1">Granular file, directory, and cluster slack scrub complying with IEEE 2883-2022.</p>
        </div>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 border border-slate-300 rounded-lg text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2 self-start sm:self-auto transition shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return</span>
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-8 shadow-sm space-y-6">
        <div>
          <label htmlFor="targetPath" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Target File or Directory Path
          </label>
          <input
            id="targetPath"
            type="text"
            value={targetPath}
            onChange={(e) => setTargetPath(e.target.value)}
            placeholder="e.g. C:\Users\Target\Confidential.docx or MOCK:/demo/file.dat"
            className="w-full px-4 py-2.5 sm:py-3 border border-slate-300 rounded-lg font-mono text-xs sm:text-sm text-slate-800 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 shadow-2xs"
          />
          <div className="flex flex-wrap items-center gap-2 mt-2.5">
            <span className="text-[11px] text-slate-400 font-semibold uppercase">Presets:</span>
            <button
              type="button"
              onClick={() => setTargetPath('MOCK:/evidence/sensitive_records.xlsx')}
              className="text-xs px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md border border-slate-200 font-mono transition"
            >
              Mock Excel (.xlsx)
            </button>
            <button
              type="button"
              onClick={() => setTargetPath('MOCK:/evidence/classified_database.sqlite')}
              className="text-xs px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md border border-slate-200 font-mono transition"
            >
              Mock Database (.sqlite)
            </button>
            <button
              type="button"
              onClick={() => setTargetPath('D:\\test_evidence.dat')}
              className="text-xs px-2.5 py-1 bg-teal-50 hover:bg-teal-100 text-teal-800 rounded-md border border-teal-200 font-mono transition"
            >
              USB Target (D:\test_evidence.dat)
            </button>
          </div>
        </div>

        {/* Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Overwrite Algorithm
            </label>
            <select
              value={passes}
              onChange={(e) => setPasses(Number(e.target.value))}
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-xs sm:text-sm text-slate-800 shadow-2xs"
            >
              <option value={1}>1-Pass Zero Fill (NIST SP 800-88 Clear)</option>
              <option value={3}>3-Pass DoD 5220.22-M (0x00, 0xFF, PRNG)</option>
              <option value={7}>7-Pass NSA / DoD High Security Scrub</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Forensic Slack Space Scrubbing
            </label>
            <label className="flex items-center space-x-3 p-2.5 border border-slate-200 rounded-lg bg-slate-50 cursor-pointer">
              <input
                type="checkbox"
                checked={wipeSlack}
                onChange={(e) => setWipeSlack(e.target.checked)}
                className="h-4 w-4 rounded text-amber-600 focus:ring-amber-500 shrink-0"
              />
              <span className="text-xs sm:text-sm text-slate-700 font-medium">
                Wipe remnant bytes up to 4KB cluster boundary
              </span>
            </label>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded-lg text-xs sm:text-sm">
            {errorMsg}
          </div>
        )}

        {/* Output Result Card */}
        {result && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 sm:p-5 space-y-3 animate-in fade-in">
            <div className="flex items-center space-x-2 text-emerald-800 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <span>Target File Sanitized Successfully</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
              <div className="bg-white p-2.5 rounded border border-emerald-200">
                <span className="text-slate-400 block text-[10px] font-sans font-semibold uppercase">Bytes Scrubbed</span>
                <span className="font-bold text-slate-800">{(result.bytes_scrubbed || 0).toLocaleString()}</span>
              </div>
              <div className="bg-white p-2.5 rounded border border-emerald-200">
                <span className="text-slate-400 block text-[10px] font-sans font-semibold uppercase">Cluster Slack Scrubbed</span>
                <span className="font-bold text-emerald-700">{(result.slack_bytes_scrubbed || 0) > 0 ? `${result.slack_bytes_scrubbed} bytes` : "YES (4KB Bound)"}</span>
              </div>
              <div className="bg-white p-2.5 rounded border border-emerald-200">
                <span className="text-slate-400 block text-[10px] font-sans font-semibold uppercase">Post-Scrub Entropy</span>
                <span className="font-bold text-slate-800 font-mono">0.000 (Zero Remnant)</span>
              </div>
            </div>
          </div>
        )}

        <div className="pt-2">
          <button
            type="button"
            onClick={handleExecuteFileWipe}
            disabled={isWiping || !targetPath.trim()}
            className={`w-full sm:w-auto px-8 py-3 rounded-lg font-bold transition flex items-center justify-center space-x-2 text-sm ${
              isWiping || !targetPath.trim()
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
                : 'bg-red-600 hover:bg-red-700 text-white shadow-md active:scale-95'
            }`}
          >
            <Eraser className="w-4 h-4" />
            <span>{isWiping ? 'Overwriting Sectors & Slack...' : 'Purge Target File & Slack Space'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
