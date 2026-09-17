import React from 'react';

type Mode = 'erase' | 'recovery' | 'neutral';

interface ModeBannerProps {
  mode: Mode;
}

export default function ModeBanner({ mode }: ModeBannerProps) {
  if (mode === 'neutral') {
    return null;
  }

  const isErase = mode === 'erase';
  const bgColor = isErase ? 'bg-red-50' : 'bg-teal-50';
  const borderColor = isErase ? 'border-red-200' : 'border-teal-200';
  const textColor = isErase ? 'text-red-700' : 'text-teal-700';
  const label = isErase ? 'WRITE-ENABLED SESSION - DATA DESTRUCTION ACTIVE' : 'READ-ONLY SESSION - WRITE BLOCKED';

  return (
    <div className={`w-full py-3 px-6 flex items-center justify-center font-bold text-sm tracking-widest border-b ${bgColor} ${borderColor} ${textColor} relative z-20 shadow-sm`}>
      <span className="uppercase">{label}</span>
    </div>
  );
}
