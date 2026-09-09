import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SessionProvider } from "@/context/SessionContext";
import ClientHeader from "@/components/ClientHeader";
import ClientBanner from "@/components/ClientBanner";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Nuance-Forensic Dashboard",
  description: "Unified secure erasure & forensic recovery dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-screen flex overflow-hidden bg-primary text-textPrimary`}>
        <SessionProvider>
          {/* Persistent Left Sidebar - Glassmorphism applied */}
          <aside className="w-64 glass-panel border-r-white/10 flex flex-col shrink-0 z-10 relative">
            <div className="h-16 flex items-center px-6 border-b border-white/10 bg-black/20">
              <div className="flex items-center space-x-3">
                <div className="w-3 h-3 rounded-full bg-safe animate-pulse-slow glow-safe"></div>
                <h1 className="text-lg font-bold tracking-widest text-primary uppercase">Nuance</h1>
              </div>
            </div>
            <nav className="flex-1 p-4 space-y-2">
              <div className="px-4 py-3 rounded-lg bg-safe/10 text-safe cursor-pointer transition-all border border-safe/30 glow-safe shadow-inner shadow-safe/20 font-medium tracking-wide">
                Dashboard
              </div>
            </nav>
            <div className="p-4 border-t border-white/10 bg-black/20 text-xs text-secondary/50 font-mono text-center">
              NTRO FORENSIC TOOLKIT V2.4
            </div>
          </aside>

          {/* Main Content Area */}
          <div className="flex-1 flex flex-col h-full overflow-hidden relative">
            <ClientHeader />
            <ClientBanner />

            {/* Page Content */}
            <main className="flex-1 overflow-auto p-8 relative z-0">
              {children}
            </main>
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}
