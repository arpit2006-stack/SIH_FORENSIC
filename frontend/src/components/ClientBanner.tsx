"use client";

import React from 'react';
import { useSession } from '@/context/SessionContext';
import ModeBanner from './ModeBanner';

export default function ClientBanner() {
  const { sessionMode } = useSession();
  return <ModeBanner mode={sessionMode} />;
}
