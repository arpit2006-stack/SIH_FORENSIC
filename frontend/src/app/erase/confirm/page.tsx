"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { apiClient } from '@/lib/apiClient';
import { AlertTriangle, ShieldAlert, CheckCircle2 } from 'lucide-react';

export default function EraseConfirmPage() {
  const router = useRouter();
  const { selectedDrive, caseId, investigatorName, setActiveOperationId, setLatestReport } = useSession();

  const [method, setMethod] = useState<string>('NIST_SP_800_88_PURGE');
  const [passphrase, setPassphrase] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!selectedDrive) {
    if (typeof window !== 'undefined') router.push('/');
    return null;
  }

  const requiredSerial = selectedDrive.serial;
  const isSerialConfirmed = passphrase.trim() === requiredSerial;

  const handleExecuteSanitize = async () => {
    if (!isSerialConfirmed) return;
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const devPath = selectedDrive.devicePath || `/dev/mock_${selectedDrive.serial.toLowerCase().replace(/[^a-z0-9]/g, '')}`;
      const resp = await apiClient.executeSanitization({
        devicePath: devPath,
        serial: selectedDrive.serial,
        method: method,
        operatorId: investigatorName || 'OFFICER-DEFAULT',
        caseId: caseId || 'CAS-2026-904',
        passphrase: passphrase,
        allowLiveExecution: true,
      });

      if (resp?.report) {
        setActiveOperationId(resp.report.operationId);
        setLatestReport(resp.report);
        router.push('/erase/progress');
      } else {
        throw new Error('No report received from sanitization engine');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Sanitization request failed. Check daemon status.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-800">Authorization Gate</h2>
        <p className="text-slate-500 text-lg">Two-stage cryptographic interlock before executing physical media erasure.</p>
      </div>

      <DriveSummaryCard
        serial={selectedDrive.serial}
        model={selectedDrive.model}
        capacity={selectedDrive.capacity}
        interfaceType={selectedDrive.interfaceType}
      />

      {/* Warning Box */}
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-start space-x-4">
        <ShieldAlert className="w-8 h-8 text-red-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-red-900 text-base">Irreversible Data Destruction Warning</h4>
          <p className="text-sm text-red-700 leading-relaxed">
            This action will issue physical controller commands (<span className="font-mono font-semibold">IEEE 2883-2022 / NIST SP 800-88</span>) 
            wiping NAND flash and magnetic blocks. All partitions, filesystems, and unallocated slack space will be permanently expunged.
          </p>
        </div>
      </div>

      {/* Sanitization Options Form */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Sanitization Protocol
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              type="button"
              onClick={() => setMethod('NIST_SP_800_88_PURGE')}
              className={`p-4 text-left border rounded-lg transition-all ${
                method === 'NIST_SP_800_88_PURGE'
                  ? 'border-red-500 bg-red-50/50 ring-1 ring-red-500'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-semibold text-slate-800 text-sm mb-1">NIST Purge</div>
              <div className="text-xs text-slate-500">NVMe Sanitize / Crypto Scramble. Recommended for SSD.</div>
            </button>

            <button
              type="button"
              onClick={() => setMethod('NIST_SP_800_88_CLEAR')}
              className={`p-4 text-left border rounded-lg transition-all ${
                method === 'NIST_SP_800_88_CLEAR'
                  ? 'border-red-500 bg-red-50/50 ring-1 ring-red-500'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-semibold text-slate-800 text-sm mb-1">NIST Clear</div>
              <div className="text-xs text-slate-500">Logical address multi-pass zero/pattern overwrite.</div>
            </button>

            <button
              type="button"
              onClick={() => setMethod('ATA_SECURE_ERASE')}
              className={`p-4 text-left border rounded-lg transition-all ${
                method === 'ATA_SECURE_ERASE'
                  ? 'border-red-500 bg-red-50/50 ring-1 ring-red-500'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-semibold text-slate-800 text-sm mb-1">ATA Secure Erase</div>
              <div className="text-xs text-slate-500">Hardware controller internal wipe for legacy SATA.</div>
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="passphrase" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Safety Interlock Confirmation
          </label>
          <p className="text-sm text-slate-600 mb-3">
            To unlock the execution trigger, type the target serial number exactly: <code className="bg-slate-100 px-2 py-0.5 rounded font-mono font-bold text-slate-800">{requiredSerial}</code>
          </p>
          <input
            id="passphrase"
            type="text"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            placeholder={`Type ${requiredSerial} to confirm`}
            className="w-full px-4 py-3 border border-slate-300 rounded-md font-mono text-slate-800 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
          />
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
          onClick={handleExecuteSanitize}
          disabled={!isSerialConfirmed || isSubmitting}
          className={`px-8 py-3 font-semibold rounded-md transition-all duration-200 shadow-sm flex items-center space-x-2 ${
            !isSerialConfirmed || isSubmitting
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
              : 'bg-red-600 text-white hover:bg-red-700 shadow-md active:scale-95'
          }`}
        >
          {isSubmitting ? (
            <span>Authorizing Hardware Wipe...</span>
          ) : (
            <>
              <AlertTriangle className="w-5 h-5" />
              <span>Engage Erasure Protocol</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
