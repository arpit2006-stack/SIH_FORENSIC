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
  const bgColor = isErase ? 'bg-danger/20' : 'bg-safe/20';
  const borderColor = isErase ? 'border-danger' : 'border-safe';
  const glowText = isErase ? 'text-glow-danger text-danger' : 'text-glow-safe text-safe';
  const label = isErase ? 'WRITE-ENABLED SESSION - DATA DESTRUCTION ACTIVE' : 'READ-ONLY SESSION - WRITE BLOCKED';
  const glowBox = isErase ? 'glow-danger' : 'glow-safe';

  return (
    <div className={`w-full py-3 px-6 flex items-center justify-center font-black tracking-[0.2em] border-b backdrop-blur-md ${bgColor} ${borderColor} ${glowText} ${glowBox} relative z-20 overflow-hidden`}>
      {/* Animated scanline effect across the banner */}
      <div className="absolute inset-0 w-full h-full bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent)] animate-[pulse_2s_infinite_ease-in-out]"></div>
      <span className="relative z-10 uppercase">{label}</span>
    </div>
  );
}
