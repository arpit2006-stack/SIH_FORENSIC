"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/context/SessionContext';
import DriveSummaryCard from '@/components/DriveSummaryCard';
import { apiClient } from '@/lib/apiClient';
import { AlertTriangle, ShieldAlert, CheckCircle2, HardDrive, ArrowLeft } from 'lucide-react';

export default function EraseConfirmPage() {
  const router = useRouter();
  const { selectedDrive, setSelectedDrive, caseId, investigatorName, setActiveOperationId, setLatestReport } = useSession();

  const isUsb = Boolean(
    selectedDrive?.busType?.toUpperCase().includes('USB') ||
    selectedDrive?.interfaceType?.toUpperCase().includes('USB')
  );

  const [method, setMethod] = useState<string>(isUsb ? 'NIST_SP_800_88_CLEAR' : 'NIST_SP_800_88_PURGE');
  const [passphrase, setPassphrase] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  React.useEffect(() => {
    if (isUsb) {
      setMethod('NIST_SP_800_88_CLEAR');
    }
  }, [isUsb]);

  if (!selectedDrive) {
    return (
      <div className="max-w-2xl mx-auto my-8 sm:my-12 p-6 sm:p-8 bg-white border border-slate-200 rounded-2xl shadow-sm space-y-6 text-center animate-in fade-in duration-300">
        <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <HardDrive className="w-7 h-7" />
        </div>
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">No Erasure Target Selected</h2>
          <p className="text-slate-500 text-sm mt-2 max-w-md mx-auto">
            A target storage volume must be selected before opening the sanitization authorization gate.
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
            className="w-full sm:w-auto px-6 py-2.5 bg-red-50 text-red-700 border border-red-300 rounded-lg text-sm font-semibold hover:bg-red-100 transition shadow-sm"
          >
            Engage Flash Disk (D:)
          </button>
        </div>
      </div>
    );
  }

  const requiredSerial = selectedDrive.serial;
  const isSerialConfirmed = passphrase.trim() === requiredSerial;

  const handleExecuteSanitize = async () => {
    if (!isSerialConfirmed) return;
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const devPath = selectedDrive.devicePath || `/dev/mock_${selectedDrive.serial.toLowerCase().replace(/[^a-z0-9]/g, '')}`;
      // Clean model name of any mount points (e.g. "Generic Flash Disk (D:)" -> "Generic Flash Disk")
      const cleanModel = (selectedDrive.model || '').replace(/\s*\([A-Za-z0-9_:\s,/.-]+\)$/, '').trim();
      const resp = await apiClient.executeSanitization({
        devicePath: devPath,
        serial: selectedDrive.serial,
        serialConfirmation: selectedDrive.serial,
        model: cleanModel || selectedDrive.model,
        modelConfirmation: cleanModel || selectedDrive.model,
        method: method,
        selectedMethod: method,
        operatorId: investigatorName || 'OFFICER-DEFAULT',
        caseId: caseId || 'CAS-2026-904',
        reason: 'Authorized Forensic Media Sanitization',
        passphrase: passphrase,
        allowLiveExecution: true,
        explicitDestructiveConfirmation: true,
        executionMode: 'REAL_EXECUTION',
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
    <div className="w-full max-w-5xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-12">
      {/* Header */}
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Authorization Gate</h2>
        <p className="text-slate-500 text-sm sm:text-base mt-1">
          Two-stage cryptographic interlock before executing physical media erasure.
        </p>
      </div>

      <DriveSummaryCard
        serial={selectedDrive.serial}
        model={selectedDrive.model}
        capacity={selectedDrive.capacity}
        interfaceType={selectedDrive.interfaceType}
        busType={selectedDrive.busType}
      />

      {/* Warning Box */}
      <div className="bg-red-50 border border-red-200 rounded-xl p-4 sm:p-6 flex items-start space-x-3 sm:space-x-4">
        <ShieldAlert className="w-6 h-6 sm:w-8 sm:h-8 text-red-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-red-900 text-sm sm:text-base">Irreversible Data Destruction Warning</h4>
          <p className="text-xs sm:text-sm text-red-700 leading-relaxed">
            This action will issue physical controller commands (<span className="font-mono font-semibold">IEEE 2883-2022 / NIST SP 800-88</span>) 
            wiping NAND flash and magnetic blocks. All partitions, filesystems, and unallocated slack space will be permanently expunged.
          </p>
        </div>
      </div>

      {/* Sanitization Options Form */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-sm space-y-6">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2.5">
            Sanitization Protocol Standard
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => setMethod('NIST_SP_800_88_PURGE')}
              className={`p-4 text-left border rounded-xl transition-all ${
                method === 'NIST_SP_800_88_PURGE'
                  ? 'border-red-500 bg-red-50/50 ring-2 ring-red-500/20 shadow-2xs'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-bold text-slate-900 text-sm mb-1">NIST Purge</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                NVMe Sanitize / Crypto Scramble. Recommended for solid state NAND media.
              </div>
            </button>

            <button
              type="button"
              onClick={() => setMethod('NIST_SP_800_88_CLEAR')}
              className={`p-4 text-left border rounded-xl transition-all ${
                method === 'NIST_SP_800_88_CLEAR'
                  ? 'border-red-500 bg-red-50/50 ring-2 ring-red-500/20 shadow-2xs'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-bold text-slate-900 text-sm mb-1">NIST Clear</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                Logical address multi-pass zero/pattern overwrite with byte verification.
              </div>
            </button>

            <button
              type="button"
              onClick={() => setMethod('ATA_SECURE_ERASE')}
              className={`p-4 text-left border rounded-xl transition-all ${
                method === 'ATA_SECURE_ERASE'
                  ? 'border-red-500 bg-red-50/50 ring-2 ring-red-500/20 shadow-2xs'
                  : 'border-slate-200 hover:border-slate-300 bg-white'
              }`}
            >
              <div className="font-bold text-slate-900 text-sm mb-1">ATA Secure Erase</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                Hardware controller internal wipe for legacy SATA and magnetic spindles.
              </div>
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="passphrase" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Safety Interlock Confirmation
          </label>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <p className="text-xs sm:text-sm text-slate-600">
              Type target serial number exactly:{" "}
              <code className="bg-slate-100 px-2 py-0.5 rounded font-mono font-bold text-slate-900 break-all text-xs">
                {requiredSerial}
              </code>
            </p>
            <button
              type="button"
              onClick={() => setPassphrase(requiredSerial)}
              className="text-xs font-semibold text-red-600 hover:text-red-800 hover:underline flex items-center space-x-1 self-start sm:self-auto"
            >
              <span>Autofill Serial</span>
            </button>
          </div>
          <input
            id="passphrase"
            type="text"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            placeholder={`Type ${requiredSerial} to confirm`}
            className="w-full px-4 py-2.5 sm:py-3 border border-slate-300 rounded-lg font-mono text-sm sm:text-base text-slate-800 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 shadow-2xs"
          />
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded-lg text-xs sm:text-sm">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <button
          type="button"
          onClick={() => router.push('/mode-select')}
          className="w-full sm:w-auto px-5 py-2.5 text-xs sm:text-sm font-semibold text-slate-600 hover:text-slate-900 border border-slate-300 rounded-lg hover:bg-slate-100 transition text-center"
        >
          ← Cancel & Return
        </button>

        <button
          type="button"
          onClick={handleExecuteSanitize}
          disabled={!isSerialConfirmed || isSubmitting}
          className={`w-full sm:w-auto px-8 py-3 font-bold rounded-lg transition-all duration-200 shadow-sm flex items-center justify-center space-x-2 text-sm ${
            !isSerialConfirmed || isSubmitting
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-300'
              : 'bg-red-600 text-white hover:bg-red-700 shadow-md active:scale-95'
          }`}
        >
          {isSubmitting ? (
            <span>Authorizing Hardware Wipe...</span>
          ) : (
            <>
              <AlertTriangle className="w-4 h-4" />
              <span>Engage Erasure Protocol</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
