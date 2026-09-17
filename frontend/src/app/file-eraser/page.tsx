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
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-800">Targeted File & Slack Space Eraser</h2>
          <p className="text-slate-500 text-lg">Granular file, directory, and cluster slack scrub complying with IEEE 2883-2022.</p>
        </div>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 border border-slate-300 rounded-md text-sm font-semibold text-slate-700 hover:bg-slate-100 flex items-center space-x-2"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return</span>
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm space-y-6">
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
            className="w-full px-4 py-3 border border-slate-300 rounded-md font-mono text-slate-800 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 shadow-sm"
          />
          <p className="text-xs text-slate-400 mt-1">
            Tip: Enter a mock path (e.g. <code className="bg-slate-100 px-1 py-0.5 rounded font-mono">MOCK:/demo/secret.doc</code>) for non-destructive demonstration.
          </p>
        </div>

        {/* Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Overwrite Algorithm
            </label>
            <select
              value={passes}
              onChange={(e) => setPasses(Number(e.target.value))}
              className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-md text-slate-800 shadow-sm"
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
            <label className="flex items-center space-x-3 p-2.5 border border-slate-200 rounded-md bg-slate-50 cursor-pointer">
              <input
                type="checkbox"
                checked={wipeSlack}
                onChange={(e) => setWipeSlack(e.target.checked)}
                className="h-4 w-4 rounded text-red-600 focus:ring-red-500"
              />
              <span className="text-sm text-slate-700 font-medium">
                Wipe remnant bytes up to 4KB cluster boundary
              </span>
            </label>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded text-sm">
            {errorMsg}
          </div>
        )}

        <div className="flex justify-end pt-4">
          <button
            onClick={handleExecuteFileWipe}
            disabled={isWiping || !targetPath.trim()}
            className="px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-md shadow-md active:scale-95 transition-all flex items-center space-x-2"
          >
            <Eraser className="w-5 h-5" />
            <span>{isWiping ? 'Scrubbing File & Slack Space...' : 'Purge Target File & Slack Space'}</span>
          </button>
        </div>
      </div>

      {/* Result Display */}
      {result && (
        <div className="bg-white border-2 border-emerald-500 rounded-xl p-6 shadow-sm space-y-4 animate-in fade-in duration-300">
          <div className="flex items-center space-x-3 text-emerald-700 font-bold border-b border-slate-100 pb-3">
            <CheckCircle2 className="w-6 h-6" />
            <span>Target Sanitized and Cryptographically Logged</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <div className="text-slate-500 mb-1">Target Path</div>
              <div className="text-slate-800 font-bold truncate">{result.target_path}</div>
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <div className="text-slate-500 mb-1">Bytes Scrubbed</div>
              <div className="text-slate-800 font-bold">{result.bytes_scrubbed} bytes</div>
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <div className="text-slate-500 mb-1">Slack Space Scrubbed</div>
              <div className="text-emerald-700 font-bold">{result.slack_bytes_scrubbed} bytes</div>
            </div>
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <div className="text-slate-500 mb-1">Passes Completed</div>
              <div className="text-slate-800 font-bold">{result.passes_completed} Passes</div>
            </div>
          </div>

          <div>
            <div className="text-xs uppercase font-semibold text-slate-500 mb-1">HMAC-SHA256 Audit Hash:</div>
            <div className="font-mono text-xs bg-slate-50 p-2.5 rounded border border-slate-200 text-slate-700 break-all">
              {result.audit_hash}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
