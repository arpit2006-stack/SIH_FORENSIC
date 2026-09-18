"use client";

import React, { createContext, useContext, useState, ReactNode } from 'react';

export type Drive = {
  serial: string;
  model: string;
  capacity: string;
  interfaceType: string;
  health: string;
  temp: string;
  busType: string;
  devicePath?: string;
  isSystem?: boolean;
};

type Mode = 'erase' | 'recovery' | 'neutral';

interface SessionContextType {
  caseId: string;
  setCaseId: (id: string) => void;
  investigatorName: string;
  setInvestigatorName: (name: string) => void;
  targetSource: string;
  setTargetSource: (source: string) => void;
  selectedDrive: Drive | null;
  setSelectedDrive: (drive: Drive | null) => void;
  sessionMode: Mode;
  setSessionMode: (mode: Mode) => void;

  // Active Forensic Operation State
  activeOperationId: string | null;
  setActiveOperationId: (id: string | null) => void;
  activeJobId: string | null;
  setActiveJobId: (id: string | null) => void;
  latestReport: any;
  setLatestReport: (rep: any) => void;
  carvedFiles: any[];
  setCarvedFiles: (files: any[]) => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [caseId, setCaseId] = useState<string>('CAS-2026-904');
  const [investigatorName, setInvestigatorName] = useState<string>('Insp. Rajesh Varma');
  const [targetSource, setTargetSource] = useState<string>('Local Drive');
  const [selectedDrive, setSelectedDrive] = useState<Drive | null>(null);
  const [sessionMode, setSessionMode] = useState<Mode>('neutral');

  const [activeOperationId, setActiveOperationId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [latestReport, setLatestReport] = useState<any>(null);
  const [carvedFiles, setCarvedFiles] = useState<any[]>([]);

  return (
    <SessionContext.Provider value={{
      caseId, setCaseId,
      investigatorName, setInvestigatorName,
      targetSource, setTargetSource,
      selectedDrive, setSelectedDrive,
      sessionMode, setSessionMode,
      activeOperationId, setActiveOperationId,
      activeJobId, setActiveJobId,
      latestReport, setLatestReport,
      carvedFiles, setCarvedFiles,
    }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}
