"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession, Drive } from '@/context/SessionContext';

const MOCK_DRIVES: Drive[] = [
  { serial: 'SN-9340203495', model: 'Samsung 980 PRO', capacity: '1.0 TB', interfaceType: 'NVMe', health: '98%', temp: '34°C', busType: 'PCIe 4.0 x4' },
  { serial: 'WD-WCC6Y6XNXE44', model: 'WD Blue 3D NAND', capacity: '500 GB', interfaceType: 'SATA SSD', health: '82%', temp: '29°C', busType: 'SATA III' },
  { serial: 'ST-9X0023423A', model: 'Seagate Barracuda', capacity: '2.0 TB', interfaceType: 'SATA HDD', health: '100%', temp: '41°C', busType: 'SATA III' },
];

export default function DriveSelectionPage() {
  const router = useRouter();
  const { 
    caseId, setCaseId, 
    investigatorName, setInvestigatorName, 
    targetSource, setTargetSource,
    selectedDrive, setSelectedDrive, 
    setSessionMode 
  } = useSession();
  
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

  const isNextDisabled = !caseId.trim() || !localSelectedDrive || !investigatorName.trim();

  return (
    <div className="max-w-6xl mx-auto space-y-10 animate-in fade-in duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-slate-800">Initialize Session</h2>
        <p className="text-slate-500 text-lg">Define telemetry identifiers and select target media.</p>
      </div>

      {/* Expanded Form Area */}
      <div className="bg-white border border-slate-200 shadow-sm p-6 rounded-xl relative group transition-all duration-300">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label htmlFor="caseId" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Case ID <span className="text-red-500 ml-1">*</span>
            </label>
            <input
              id="caseId"
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="e.g. CAS-2026-904"
              className="w-full px-4 py-2 bg-white border border-slate-300 rounded-md focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 font-mono shadow-sm"
            />
          </div>
          <div>
            <label htmlFor="investigator" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Investigator Name <span className="text-red-500 ml-1">*</span>
            </label>
            <input
              id="investigator"
              type="text"
              value={investigatorName}
              onChange={(e) => setInvestigatorName(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full px-4 py-2 bg-white border border-slate-300 rounded-md focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 shadow-sm"
            />
          </div>
          <div>
            <label htmlFor="targetSource" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Target Source
            </label>
            <select
              id="targetSource"
              value={targetSource}
              onChange={(e) => setTargetSource(e.target.value)}
              className="w-full px-4 py-2 bg-white border border-slate-300 rounded-md focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 shadow-sm appearance-none"
            >
              <option>Local Drive</option>
              <option>Network Share</option>
              <option>Image File (.E01 / .DD)</option>
              <option>Cloud Bucket</option>
            </select>
          </div>
        </div>
      </div>

      {/* Drives Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold tracking-tight text-slate-800">Detected Interfaces</h3>
          <button 
            onClick={handleRefresh}
            className="px-4 py-2 text-sm font-medium bg-slate-100 text-slate-700 border border-slate-200 rounded-md hover:bg-slate-200 transition-all active:scale-95 shadow-sm"
          >
            Rescan Bus
          </button>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                <th className="px-6 py-4">Model</th>
                <th className="px-6 py-4">Serial Number</th>
                <th className="px-6 py-4">Capacity</th>
                <th className="px-6 py-4">Health / Temp</th>
                <th className="px-6 py-4">Bus Type</th>
                <th className="px-6 py-4">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {drives.map((drive) => {
                const isSelected = localSelectedDrive?.serial === drive.serial;
                return (
                  <tr 
                    key={drive.serial}
                    onClick={() => setLocalSelectedDrive(drive)}
                    className={`cursor-pointer transition-colors duration-200 border-b border-slate-100 last:border-0
                      ${isSelected 
                        ? 'bg-slate-50 border-l-4 border-l-slate-800' 
                        : 'hover:bg-slate-50 border-l-4 border-l-transparent'}`}
                  >
                    <td className="px-6 py-4 font-semibold text-slate-800">{drive.model}</td>
                    <td className="px-6 py-4 font-mono text-sm text-slate-500">{drive.serial}</td>
                    <td className="px-6 py-4 font-mono text-sm text-slate-800">{drive.capacity}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      <span className="font-semibold text-slate-700">{drive.health}</span> <span className="text-slate-400 mx-1">|</span> {drive.temp}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600 font-mono text-xs">{drive.busType}</td>
                    <td className="px-6 py-4">
                      <span className="px-3 py-1 text-xs font-semibold tracking-wide bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
                        CLEAN
                      </span>
                    </td>
                  </tr>
                );
              })}
              {drives.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500 font-mono">
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
          className={`px-8 py-3 font-semibold rounded-md transition-all duration-200 shadow-sm tracking-wide
            ${isNextDisabled 
              ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed' 
              : 'bg-slate-900 text-white hover:bg-slate-800 hover:shadow-md'
            }`}
        >
          Start Session ➔
        </button>
      </div>
    </div>
  );
}
