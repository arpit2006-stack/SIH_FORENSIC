"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useSession, Drive } from '@/context/SessionContext';
import { apiClient } from '@/lib/apiClient';
import {
  HardDrive,
  Cpu,
  Usb,
  FileCode,
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  Copy,
  Check,
  Search,
  LayoutGrid,
  List,
  ArrowRight,
  Lock,
  Layers,
  Sparkles,
  AlertTriangle,
  FolderOpen,
  UserCheck
} from 'lucide-react';

const FALLBACK_DRIVES: Drive[] = [
  {
    serial: "C2ED9DAB",
    model: "Generic Flash Disk (D:)",
    capacity: "7.6 GB",
    interfaceType: "USB Disk",
    health: "100%",
    temp: "32°C",
    busType: "USB",
    devicePath: "D:",
    isSystem: false,
  },
  {
    serial: "E823_8FA6_BF53_0001_001B_448B_4CA0_2BAB",
    model: "PC SN740 NVMe WD 512GB (C:, A:)",
    capacity: "476.9 GB",
    interfaceType: "NVMe SSD",
    health: "99% (OS)",
    temp: "31°C",
    busType: "NVMe",
    devicePath: "\\\\.\\PhysicalDrive0",
    isSystem: true,
  },
  {
    serial: "CDAC-35B0DFAE",
    model: "C-DAC TrueImager Bitstream (damaged_drive.raw)",
    capacity: "0.0 GB",
    interfaceType: "Forensic Bitstream",
    health: "100%",
    temp: "31°C",
    busType: "Forensic Bitstream",
    devicePath: "A:\\SIH\\SIH_FORENSIC\\backend\\demo_data\\damaged_drive.raw",
    isSystem: false,
  },
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
  
  const [drives, setDrives] = useState<Drive[]>(FALLBACK_DRIVES);
  const [localSelectedDrive, setLocalSelectedDrive] = useState<Drive | null>(selectedDrive || null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [lastScannedTime, setLastScannedTime] = useState<string>("Just now");

  // Filtering & View state for screen scaling
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterType, setFilterType] = useState<'all' | 'ready' | 'protected'>('all');
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');
  const [copiedSerial, setCopiedSerial] = useState<string | null>(null);

  const fetchDrives = async () => {
    setIsLoading(true);
    try {
      const resp = await apiClient.listDevices(false);
      if (resp?.devices && resp.devices.length > 0) {
        const mapped: Drive[] = resp.devices.map((d: any) => {
          let cap = "512 GB";
          if (d.capacityFormatted) {
            cap = d.capacityFormatted;
          } else if (d.capacityBytes) {
            const gb = d.capacityBytes / (1024 * 1024 * 1024);
            cap = gb >= 1000 ? `${(gb / 1024).toFixed(1)} TB` : `${gb.toFixed(1)} GB`;
          }

          const isSys = Boolean(d.systemDisk || d.isSystemDrive);
          const mounts = d.mountPoints?.length ? ` (${d.mountPoints.join(', ')})` : '';

          return {
            serial: d.serial || `DEV-${d.devicePath}`,
            model: (d.model || 'Generic Storage Target') + mounts,
            capacity: cap,
            interfaceType: d.storageType || d.type || 'Block Device',
            health: isSys ? '99% (OS)' : (d.health || '100%'),
            temp: d.temp || '31°C',
            busType: d.interface || d.busType || 'USB/SATA',
            devicePath: d.devicePath,
            isSystem: isSys,
          };
        });
        setDrives(mapped);
        setBackendOnline(true);
        setLastScannedTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));

        // Default to first non-system drive if not already selected
        if (!localSelectedDrive) {
          const firstTarget = mapped.find((m) => !m.isSystem) || mapped[0];
          if (firstTarget) setLocalSelectedDrive(firstTarget);
        }
      } else {
        setDrives(FALLBACK_DRIVES);
        if (!localSelectedDrive) setLocalSelectedDrive(FALLBACK_DRIVES[0]);
      }
    } catch {
      setDrives(FALLBACK_DRIVES);
      setBackendOnline(false);
      if (!localSelectedDrive) setLocalSelectedDrive(FALLBACK_DRIVES[0]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setSessionMode('neutral');
    fetchDrives();
  }, [setSessionMode]);

  useEffect(() => {
    if (selectedDrive) {
      setLocalSelectedDrive(selectedDrive);
    }
  }, [selectedDrive]);

  const handleCopySerial = (serial: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(serial);
    setCopiedSerial(serial);
    setTimeout(() => setCopiedSerial(null), 2000);
  };

  const handleSelectDrive = () => {
    if (caseId.trim() && localSelectedDrive && investigatorName.trim()) {
      setSelectedDrive(localSelectedDrive);
      router.push('/mode-select');
    }
  };

  // Helper to get matching device icon
  const getDeviceIcon = (drive: Drive) => {
    const bus = (drive.busType || '').toLowerCase();
    const iface = (drive.interfaceType || '').toLowerCase();
    const model = (drive.model || '').toLowerCase();

    if (bus.includes('nvme') || iface.includes('nvme') || model.includes('nvme')) {
      return <Cpu className="w-5 h-5 text-indigo-500 shrink-0" />;
    }
    if (bus.includes('usb') || iface.includes('usb') || model.includes('flash')) {
      return <Usb className="w-5 h-5 text-teal-600 shrink-0" />;
    }
    if (bus.includes('bitstream') || model.includes('.raw') || model.includes('.dd')) {
      return <FileCode className="w-5 h-5 text-purple-600 shrink-0" />;
    }
    return <HardDrive className="w-5 h-5 text-slate-600 shrink-0" />;
  };

  // Filter drives based on search and status tabs
  const filteredDrives = useMemo(() => {
    return drives.filter((d) => {
      // Type filter
      if (filterType === 'ready' && d.isSystem) return false;
      if (filterType === 'protected' && !d.isSystem) return false;

      // Query filter
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        d.model.toLowerCase().includes(q) ||
        d.serial.toLowerCase().includes(q) ||
        (d.devicePath && d.devicePath.toLowerCase().includes(q)) ||
        d.busType.toLowerCase().includes(q) ||
        d.capacity.toLowerCase().includes(q)
      );
    });
  }, [drives, filterType, searchQuery]);

  const readyCount = drives.filter(d => !d.isSystem).length;
  const protectedCount = drives.filter(d => d.isSystem).length;
  const isNextDisabled = !caseId.trim() || !localSelectedDrive || !investigatorName.trim();

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-300 pb-24">
      {/* Page Title & Status Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Initialize Session</h2>
          <p className="text-slate-500 text-sm sm:text-base mt-1">
            Define forensic telemetry identifiers and select target storage media for processing.
          </p>
        </div>
        <div className="flex items-center space-x-2 bg-white px-3 py-1.5 rounded-lg border border-slate-200 shadow-2xs self-start sm:self-auto">
          <span className={`w-2.5 h-2.5 rounded-full ${backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'}`}></span>
          <span className="text-xs font-mono font-semibold text-slate-600">
            {backendOnline ? 'IPC Daemon Online (Port 8000)' : 'Standalone Safe Demo Mode'}
          </span>
        </div>
      </div>

      {/* Case Telemetry Metadata Card */}
      <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5 sm:p-6 transition-all">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
          <div className="flex items-center space-x-2 text-sm font-bold text-slate-800 uppercase tracking-wide">
            <FolderOpen className="w-4 h-4 text-teal-600" />
            <span>Forensic Case Identifiers</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setCaseId("CAS-2026-904");
              setInvestigatorName("Insp. Rajesh Varma");
              setTargetSource("Local Drive");
            }}
            className="text-xs font-medium text-teal-700 hover:text-teal-900 hover:underline flex items-center space-x-1"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Load Default Preset</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          <div>
            <label htmlFor="caseId" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Case ID / FIR Number <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="caseId"
                type="text"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                placeholder="e.g. CAS-2026-904"
                className="w-full px-3.5 py-2.5 bg-slate-50/50 hover:bg-white focus:bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 font-mono text-sm transition shadow-2xs"
              />
            </div>
          </div>

          <div>
            <label htmlFor="investigator" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Investigator Name / Badge <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                id="investigator"
                type="text"
                value={investigatorName}
                onChange={(e) => setInvestigatorName(e.target.value)}
                placeholder="e.g. Insp. Rajesh Varma"
                className="w-full px-3.5 py-2.5 bg-slate-50/50 hover:bg-white focus:bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 text-sm transition shadow-2xs"
              />
            </div>
          </div>

          <div className="sm:col-span-2 lg:col-span-1">
            <label htmlFor="targetSource" className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Acquisition Interface Source
            </label>
            <select
              id="targetSource"
              value={targetSource}
              onChange={(e) => setTargetSource(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50/50 hover:bg-white focus:bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 text-sm shadow-2xs"
            >
              <option>Local Drive</option>
              <option>Forensic Image (.RAW / .DD / .E01)</option>
              <option>Hardware Write-Blocked Bus</option>
              <option>Synthetic Demo Corpus</option>
            </select>
          </div>
        </div>
      </div>

      {/* Detected Interfaces Section */}
      <div className="space-y-4">
        {/* Section Header with Stats and Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-xl font-bold tracking-tight text-slate-800">Detected Interfaces</h3>
              <span className="px-2.5 py-0.5 text-xs font-semibold bg-slate-200 text-slate-700 rounded-full">
                {drives.length} Polled
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Kernel physical block storage devices and loopback mounts available for sanitization or forensic carving.
            </p>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            {/* View Mode Toggle */}
            <div className="hidden sm:flex items-center bg-slate-200/70 p-1 rounded-lg border border-slate-300/60">
              <button
                type="button"
                onClick={() => setViewMode('table')}
                title="Table View (Dense Forensic View)"
                className={`p-1.5 rounded-md transition ${viewMode === 'table' ? 'bg-white text-slate-800 shadow-2xs' : 'text-slate-500 hover:text-slate-800'}`}
              >
                <List className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                title="Card Grid View"
                className={`p-1.5 rounded-md transition ${viewMode === 'cards' ? 'bg-white text-slate-800 shadow-2xs' : 'text-slate-500 hover:text-slate-800'}`}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>

            {/* Rescan Button */}
            <button 
              type="button"
              onClick={fetchDrives}
              disabled={isLoading}
              className="px-3.5 py-2 text-xs font-semibold bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-100 hover:text-slate-900 transition active:scale-95 shadow-2xs flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-teal-600 ${isLoading ? 'animate-spin' : ''}`} />
              <span>{isLoading ? 'Scanning Bus...' : 'Rescan Bus'}</span>
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs">
          {/* Quick Filter Tabs */}
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
            <button
              type="button"
              onClick={() => setFilterType('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition whitespace-nowrap ${
                filterType === 'all'
                  ? 'bg-slate-900 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              All Interfaces ({drives.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterType('ready')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition whitespace-nowrap flex items-center space-x-1 ${
                filterType === 'ready'
                  ? 'bg-emerald-600 text-white shadow-2xs'
                  : 'text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Ready Targets ({readyCount})</span>
            </button>
            <button
              type="button"
              onClick={() => setFilterType('protected')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition whitespace-nowrap flex items-center space-x-1 ${
                filterType === 'protected'
                  ? 'bg-amber-600 text-white shadow-2xs'
                  : 'text-amber-700 hover:bg-amber-50'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>System Protected ({protectedCount})</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="relative min-w-[200px] sm:min-w-[240px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search model, serial, bus..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 hover:bg-white focus:bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 transition"
            />
          </div>
        </div>

        {/* View Mode 1: Table View (Optimized for screen scaling with guaranteed horizontal scroll container) */}
        {viewMode === 'table' && (
          <div className="w-full bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[860px]">
                <thead>
                  <tr className="bg-slate-50/90 text-slate-500 text-[11px] font-bold uppercase tracking-wider border-b border-slate-200 select-none">
                    <th className="py-3.5 px-4 w-[32%]">Target & Device Model</th>
                    <th className="py-3.5 px-4 w-[20%]">Serial Number</th>
                    <th className="py-3.5 px-4 w-[11%]">Capacity</th>
                    <th className="py-3.5 px-4 w-[12%]">Health & Temp</th>
                    <th className="py-3.5 px-4 w-[11%]">Bus Protocol</th>
                    <th className="py-3.5 px-4 w-[14%] text-right">Access State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredDrives.map((drive) => {
                    const isSelected = localSelectedDrive?.serial === drive.serial;
                    const truncatedSerial = drive.serial.length > 20
                      ? `${drive.serial.slice(0, 10)}...${drive.serial.slice(-8)}`
                      : drive.serial;

                    return (
                      <tr 
                        key={drive.serial}
                        onClick={() => setLocalSelectedDrive(drive)}
                        className={`cursor-pointer transition-colors duration-150 group ${
                          isSelected 
                            ? 'bg-teal-50/60 ring-1 ring-inset ring-teal-500/50' 
                            : 'hover:bg-slate-50/80'
                        }`}
                      >
                        {/* Target Model & Device Path */}
                        <td className="py-3 px-4">
                          <div className="flex items-center space-x-3">
                            <div className={`p-2 rounded-lg border shrink-0 transition-transform group-hover:scale-105 ${
                              isSelected 
                                ? 'bg-white border-teal-300 shadow-2xs' 
                                : 'bg-slate-100 border-slate-200'
                            }`}>
                              {getDeviceIcon(drive)}
                            </div>
                            <div className="min-w-0 pr-2">
                              <div className="font-semibold text-slate-900 text-sm truncate flex items-center space-x-1.5">
                                <span>{drive.model}</span>
                              </div>
                              {drive.devicePath && (
                                <div className="text-[11px] font-mono text-slate-400 truncate max-w-xs" title={drive.devicePath}>
                                  {drive.devicePath}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Serial Number with Copy Action */}
                        <td className="py-3 px-4">
                          <div className="inline-flex items-center space-x-1.5 bg-slate-100/90 border border-slate-200/80 px-2 py-1 rounded text-xs font-mono text-slate-700 max-w-full">
                            <span className="truncate" title={drive.serial}>
                              {truncatedSerial}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => handleCopySerial(drive.serial, e)}
                              title="Copy Serial Number"
                              className="text-slate-400 hover:text-slate-800 p-0.5 rounded transition shrink-0"
                            >
                              {copiedSerial === drive.serial ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </td>

                        {/* Capacity */}
                        <td className="py-3 px-4 font-mono text-xs font-bold text-slate-900 whitespace-nowrap">
                          {drive.capacity}
                        </td>

                        {/* Health & Temp */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex items-center space-x-1.5 text-xs">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${
                              drive.isSystem ? 'bg-amber-400' : 'bg-emerald-500'
                            }`}></span>
                            <span className="font-semibold text-slate-700">{drive.health}</span>
                            <span className="text-slate-300">|</span>
                            <span className="text-slate-500 font-mono text-[11px]">{drive.temp}</span>
                          </div>
                        </td>

                        {/* Bus Type */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 border border-slate-200 text-slate-700">
                            {drive.busType}
                          </span>
                        </td>

                        {/* Access State & Selection Indicator */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end space-x-2">
                            {drive.isSystem ? (
                              <span className="inline-flex items-center space-x-1 px-2.5 py-1 text-[11px] font-bold tracking-wide bg-amber-50 text-amber-800 border border-amber-200 rounded-md">
                                <Lock className="w-3 h-3 text-amber-600 shrink-0" />
                                <span>PROTECTED (OS)</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center space-x-1 px-2.5 py-1 text-[11px] font-bold tracking-wide bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-md">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                                <span>TARGET READY</span>
                              </span>
                            )}

                            {/* Radio selector button */}
                            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition ${
                              isSelected
                                ? 'border-teal-600 bg-teal-600 text-white'
                                : 'border-slate-300 bg-white group-hover:border-slate-400'
                            }`}>
                              {isSelected && <div className="w-2 h-2 rounded-full bg-white"></div>}
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}

                  {filteredDrives.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-12 px-6 text-center text-slate-500">
                        <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2 opacity-70" />
                        <div className="font-semibold text-slate-700">No matching interfaces found</div>
                        <div className="text-xs text-slate-400 mt-1">Try adjusting your search query or filter pills</div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Table Footer Summary */}
            <div className="py-2.5 px-4 bg-slate-50 border-t border-slate-200 text-xs text-slate-500 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <span className="font-mono text-[11px]">
                Bus Polled: {drives.length} physical/virtual endpoints • Last scan: {lastScannedTime}
              </span>
              <span className="text-[11px] text-slate-400">
                Click any row to select as active target
              </span>
            </div>
          </div>
        )}

        {/* View Mode 2: Card Grid View (Alternate layout for high scalability on responsive views) */}
        {viewMode === 'cards' && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredDrives.map((drive) => {
              const isSelected = localSelectedDrive?.serial === drive.serial;
              return (
                <div
                  key={drive.serial}
                  onClick={() => setLocalSelectedDrive(drive)}
                  className={`bg-white border rounded-xl p-5 shadow-sm cursor-pointer transition-all duration-200 relative flex flex-col justify-between ${
                    isSelected
                      ? 'border-teal-500 ring-2 ring-teal-500/30 bg-teal-50/20'
                      : 'border-slate-200 hover:border-slate-300 hover:shadow-md'
                  }`}
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center space-x-3">
                        <div className="p-2.5 rounded-lg bg-slate-100 border border-slate-200">
                          {getDeviceIcon(drive)}
                        </div>
                        <div>
                          <h4 className="font-bold text-slate-900 text-sm tracking-tight leading-snug line-clamp-1" title={drive.model}>
                            {drive.model}
                          </h4>
                          <span className="text-[11px] font-mono text-slate-500 block">
                            {drive.busType} • {drive.interfaceType}
                          </span>
                        </div>
                      </div>

                      {/* State Badge */}
                      {drive.isSystem ? (
                        <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200 rounded whitespace-nowrap">
                          OS PROTECTED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 rounded whitespace-nowrap">
                          READY
                        </span>
                      )}
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-2 text-xs pt-1 font-mono">
                      <div className="bg-slate-50 p-2 rounded border border-slate-100">
                        <span className="text-[10px] text-slate-400 block uppercase font-sans font-semibold">Capacity</span>
                        <span className="font-bold text-slate-800">{drive.capacity}</span>
                      </div>
                      <div className="bg-slate-50 p-2 rounded border border-slate-100">
                        <span className="text-[10px] text-slate-400 block uppercase font-sans font-semibold">Health / Temp</span>
                        <span className="text-slate-700 font-semibold">{drive.health}</span> <span className="text-slate-400">|</span> <span>{drive.temp}</span>
                      </div>
                    </div>

                    {/* Serial snippet with copy button */}
                    <div className="flex items-center justify-between text-[11px] font-mono bg-slate-50 px-2.5 py-1.5 rounded border border-slate-200">
                      <span className="text-slate-500 truncate mr-2" title={drive.serial}>
                        SN: {drive.serial}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleCopySerial(drive.serial, e)}
                        className="text-slate-400 hover:text-slate-700 shrink-0"
                        title="Copy Serial"
                      >
                        {copiedSerial === drive.serial ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* Card Select Button */}
                  <div className="pt-4 mt-2 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400">
                      {isSelected ? "Active target selected" : "Click to select"}
                    </span>
                    <button
                      type="button"
                      onClick={() => setLocalSelectedDrive(drive)}
                      className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${
                        isSelected
                          ? 'bg-teal-600 text-white shadow-2xs'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {isSelected ? 'Selected ✓' : 'Select'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Floating / Sticky Bottom Action Bar for Target Confirmation & Scaling Protection */}
      <div className="fixed bottom-0 right-0 left-0 lg:left-auto lg:w-[calc(100%-5rem)] z-30 bg-white/95 backdrop-blur-md border-t border-slate-200 shadow-lg px-4 sm:px-8 py-3.5 transition-all">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Target Status Info */}
          <div className="flex items-center space-x-3 w-full sm:w-auto">
            <div className="p-2 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 hidden sm:block shrink-0">
              <HardDrive className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider flex items-center space-x-1.5">
                <span>Selected Target:</span>
                {localSelectedDrive?.isSystem && (
                  <span className="text-[10px] text-amber-700 font-bold bg-amber-100 px-1.5 rounded">OS Media</span>
                )}
              </div>
              <div className="text-sm font-bold text-slate-900 truncate">
                {localSelectedDrive ? (
                  <span>
                    {localSelectedDrive.model}{" "}
                    <span className="font-mono text-teal-700 font-normal">({localSelectedDrive.capacity})</span>
                  </span>
                ) : (
                  <span className="text-amber-600 font-medium">Please select a storage drive above</span>
                )}
              </div>
            </div>
          </div>

          {/* Action Trigger */}
          <div className="flex items-center space-x-3 w-full sm:w-auto justify-end">
            <button
              onClick={handleSelectDrive}
              disabled={isNextDisabled}
              className={`w-full sm:w-auto px-6 py-2.5 font-bold rounded-lg transition-all duration-200 shadow-sm flex items-center justify-center space-x-2 text-sm ${
                isNextDisabled
                  ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                  : 'bg-slate-900 text-white hover:bg-slate-800 hover:shadow-md active:scale-95'
              }`}
            >
              <span>Engage Target & Select Mode</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
