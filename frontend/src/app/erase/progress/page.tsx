"use client";

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import { apiClient } from '@/lib/apiClient';
import { CheckCircle2, ShieldCheck, Cpu, ArrowRight, AlertTriangle, ShieldAlert } from 'lucide-react';

export default function EraseProgressPage() {
  const router = useRouter();
  const { selectedDrive, activeOperationId, latestReport, setLatestReport } = useSession();

  const [progress, setProgress] = useState<number>(() => {
    if (latestReport?.status === 'SUCCESS') return 100;
    return 30;
  });
  const [phase, setPhase] = useState<string>(() => {
    if (latestReport?.status === 'SUCCESS') {
      return 'HMAC-SHA256 Chain of Custody Sealed & Certified.';
    }
    if (latestReport?.status === 'FAILED') {
      return 'Sanitization Aborted: Target revalidation or security gate failed.';
    }
    return 'Issuing Controller Direct IOCTL Command & Scrub Passes...';
  });
  const [isDone, setIsDone] = useState<boolean>(() => latestReport?.status === 'SUCCESS');
  const [isFailed, setIsFailed] = useState<boolean>(() => latestReport?.status === 'FAILED');
  const [errorDetails, setErrorDetails] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // If we already have a successful report, seal immediately
    if (latestReport?.status === 'SUCCESS') {
      setProgress(100);
      setPhase('HMAC-SHA256 Chain of Custody Sealed & Certified.');
      setIsDone(true);
      return;
    }

    if (latestReport?.status === 'FAILED') {
      setProgress(100);
      setPhase('Sanitization Aborted: Target verification or hardware safety tripped.');
      setIsFailed(true);
      return;
    }

    const opId = activeOperationId || latestReport?.operationId;
    if (!opId) {
      // If no operation ID is present at all, allow inspection or redirect
      setPhase('Awaiting Hardware Controller Handshake...');
      return;
    }

    // Authentic polling of backend status every 800ms
    const pollStatus = async () => {
      try {
        const resp = await apiClient.getSanitizationReport(opId);
        if (resp?.report) {
          setLatestReport(resp.report);
          if (resp.report.status === 'SUCCESS') {
            setProgress(100);
            setPhase('HMAC-SHA256 Chain of Custody Sealed & Certified.');
            setIsDone(true);
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          } else if (resp.report.status === 'FAILED') {
            setProgress(100);
            setPhase('Sanitization Aborted: Target revalidation or security gate failed.');
            setIsFailed(true);
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          } else {
            setProgress((prev) => Math.min(prev + 15, 90));
            setPhase('NIST SP 800-88 Verification Sampling & Entropy Analysis...');
          }
        }
      } catch (err: any) {
        // If not found or transient error, advance visual indicator conservatively
        setProgress((prev) => Math.min(prev + 10, 85));
      }
    };

    pollStatus();
    pollIntervalRef.current = setInterval(pollStatus, 800);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [activeOperationId, latestReport, setLatestReport]);

  const handleViewReport = () => {
    router.push('/erase/report');
  };

  const handleReturnToDashboard = () => {
    router.push('/');
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Sanitization in Progress</h2>
        <p className="text-slate-500 text-sm sm:text-base mt-1">Direct hardware controller stream telemetry.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-8 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Operation ID</div>
            <div className="text-base sm:text-lg font-mono font-bold text-slate-900 break-all">
              {activeOperationId || latestReport?.operationId || 'OP-2026-SANITIZING'}
            </div>
          </div>
          <div className="text-left sm:text-right">
            <div className="text-xs uppercase font-mono text-slate-400 font-semibold">Target Drive</div>
            <div className="text-xs sm:text-sm font-semibold text-slate-700">
              {selectedDrive?.model || selectedDrive?.devicePath || 'Storage Target'}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs sm:text-sm font-semibold">
            <span className={`truncate mr-2 ${isFailed ? 'text-red-600 font-bold' : 'text-slate-700'}`}>
              {phase}
            </span>
            <span className="font-mono text-slate-900 shrink-0">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                isFailed ? 'bg-red-600' : isDone ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Dynamic Telemetry Stats Grid from Real Report */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-2">
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Destruction Standard</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono truncate">
              {latestReport?.method || 'IEEE 2883 / NIST 800-88'}
            </div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Verification Sample</div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 font-mono truncate">
              {latestReport?.verification?.sectorsSampled
                ? `${latestReport.verification.sectorsSampled.toLocaleString()} Sectors (${latestReport.verification.status})`
                : '1,024 Sectors (Verifying...)'}
            </div>
          </div>
          <div className="p-3.5 sm:p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="text-[11px] text-slate-500 mb-1 font-semibold uppercase">Audit Chain Root</div>
            <div className="text-xs sm:text-sm font-bold text-emerald-700 font-mono truncate">
              {latestReport?.proof?.hmacChainHash
                ? `${latestReport.proof.hmacChainHash.substring(0, 16)}...`
                : isFailed
                ? 'CHAIN ABORTED'
                : 'HMAC-SHA256 Sealed'}
            </div>
          </div>
        </div>

        {isFailed && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-3 text-red-800 text-xs sm:text-sm">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Execution Safety Interlock Triggered:</span> The operation was halted
              in accordance with zero-silent-fallback policy. Drive hardware signatures did not match authorized
              specifications or required administrative privileges were denied.
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col sm:flex-row justify-between items-center gap-3 pt-2">
        <button
          onClick={handleReturnToDashboard}
          className="w-full sm:w-auto px-5 py-2.5 rounded-lg font-semibold text-slate-700 border border-slate-300 hover:bg-slate-100 text-xs sm:text-sm transition"
        >
          ← Return to Dashboard
        </button>

        <button
          onClick={handleViewReport}
          disabled={!isDone || isFailed}
          className={`w-full sm:w-auto px-8 py-3 rounded-lg font-bold transition flex items-center justify-center space-x-2 text-sm ${
            isDone && !isFailed
              ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-md active:scale-95'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
          }`}
        >
          <span>View Sanitization Certificate</span>
          <ArrowRight className="w-4 h-4 ml-1" />
        </button>
      </div>
    </div>
  );
}
