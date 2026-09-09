"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession, Drive } from '@/context/SessionContext';

const MOCK_DRIVES: Drive[] = [
  { serial: 'SN-9340203495', model: 'Samsung 980 PRO', capacity: '1.0 TB', interfaceType: 'NVMe' },
  { serial: 'WD-WCC6Y6XNXE44', model: 'WD Blue 3D NAND', capacity: '500 GB', interfaceType: 'SATA SSD' },
  { serial: 'ST-9X0023423A', model: 'Seagate Barracuda', capacity: '2.0 TB', interfaceType: 'SATA HDD' },
];

export default function DriveSelectionPage() {
  const router = useRouter();
  const { caseId, setCaseId, selectedDrive, setSelectedDrive, setSessionMode } = useSession();
  const [drives, setDrives] = useState<Drive[]>(MOCK_DRIVES);
  const [localSelectedDrive, setLocalSelectedDrive] = useState<Drive | null>(null);
  
  React.useEffect(() => {
    setSessionMode('neutral');
    setSelectedDrive(null);
  }, [setSessionMode, setSelectedDrive]);

  const handleRefresh = () => {
    setDrives([...MOCK_DRIVES]);
  };

  const handleSelectDrive = () => {
    if (caseId.trim() && localSelectedDrive) {
      setSelectedDrive(localSelectedDrive);
      router.push('/mode-select');
    }
  };

  const isNextDisabled = !caseId.trim() || !localSelectedDrive;

  return (
    <div className="max-w-5xl mx-auto space-y-10 animate-in fade-in duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-primary">Initialize Session</h2>
        <p className="text-secondary text-lg">Define telemetry identifiers and select target media.</p>
      </div>

      {/* Case ID Header Area */}
      <div className="glass-panel p-6 rounded-xl relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1 h-full bg-safe group-focus-within:glow-safe transition-all"></div>
        <label htmlFor="caseId" className="block text-xs font-bold uppercase tracking-widest text-secondary mb-3">
          Case ID <span className="text-danger ml-1">*</span>
        </label>
        <input
          id="caseId"
          type="text"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
          placeholder="e.g. CAS-2026-904"
          className="w-full max-w-md px-5 py-3 bg-black/40 border border-white/10 rounded-lg focus:outline-none focus:border-safe focus:ring-1 focus:ring-safe text-primary font-mono text-lg transition-all"
        />
      </div>

      {/* Drives Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold tracking-tight">Detected Interfaces</h3>
          <button 
            onClick={handleRefresh}
            className="px-5 py-2 text-sm font-bold uppercase tracking-widest bg-white/5 border border-white/10 rounded hover:bg-white/10 hover:border-white/30 transition-all active:scale-95"
          >
            Rescan Bus
          </button>
        </div>

        <div className="glass-panel rounded-xl overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/40 text-secondary text-[10px] uppercase tracking-widest border-b border-white/10">
                <th className="px-6 py-4 font-bold">Model</th>
                <th className="px-6 py-4 font-bold">Serial Number</th>
                <th className="px-6 py-4 font-bold">Capacity</th>
                <th className="px-6 py-4 font-bold">Interface</th>
                <th className="px-6 py-4 font-bold">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {drives.map((drive) => {
                const isSelected = localSelectedDrive?.serial === drive.serial;
                return (
                  <tr 
                    key={drive.serial}
                    onClick={() => setLocalSelectedDrive(drive)}
                    className={`cursor-pointer transition-all duration-200 
                      ${isSelected 
                        ? 'bg-safe/10 border-l-4 border-l-safe shadow-[inset_0_0_20px_rgba(20,184,166,0.1)]' 
                        : 'hover:bg-white/5 border-l-4 border-l-transparent'}`}
                  >
                    <td className="px-6 py-5 font-bold text-primary">{drive.model}</td>
                    <td className="px-6 py-5 font-mono text-sm text-secondary/80">{drive.serial}</td>
                    <td className="px-6 py-5 font-mono text-sm text-primary">{drive.capacity}</td>
                    <td className="px-6 py-5 text-sm">
                       <span className="px-2 py-1 bg-black/30 border border-white/10 rounded font-mono text-xs">{drive.interfaceType}</span>
                    </td>
                    <td className="px-6 py-5">
                      <span className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest bg-success/10 text-success border border-success/30 rounded-full glow-success">
                        CLEAN
                      </span>
                    </td>
                  </tr>
                );
              })}
              {drives.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-secondary font-mono">
                    NO TARGETS DETECTED ON BUS
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex justify-end pt-6">
        <button
          onClick={handleSelectDrive}
          disabled={isNextDisabled}
          className={`px-8 py-4 font-bold tracking-widest uppercase rounded transition-all duration-300
            ${isNextDisabled 
              ? 'bg-white/5 text-secondary/50 border border-white/10 cursor-not-allowed' 
              : 'bg-safe text-black hover:bg-safe/90 glow-safe hover:scale-[1.02] active:scale-95 shadow-lg shadow-safe/20'
            }`}
        >
          Initialize Target ➔
        </button>
      </div>
    </div>
  );
}
