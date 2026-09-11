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
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [caseId, setCaseId] = useState<string>('');
  const [investigatorName, setInvestigatorName] = useState<string>('');
  const [targetSource, setTargetSource] = useState<string>('Local Drive');
  const [selectedDrive, setSelectedDrive] = useState<Drive | null>(null);
  const [sessionMode, setSessionMode] = useState<Mode>('neutral');

  return (
    <SessionContext.Provider value={{
      caseId, setCaseId,
      investigatorName, setInvestigatorName,
      targetSource, setTargetSource,
      selectedDrive, setSelectedDrive,
      sessionMode, setSessionMode
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
