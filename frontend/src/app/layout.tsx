import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SessionProvider } from "@/context/SessionContext";
import ClientHeader from "@/components/ClientHeader";
import ClientBanner from "@/components/ClientBanner";
import SidebarNav from "@/components/SidebarNav";

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
  title: "Forensic Wipe",
  description: "Unified secure erasure & forensic recovery dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-screen flex overflow-hidden bg-slate-50 text-slate-800`}>
        <SessionProvider>
          {/* Persistent Left Sidebar */}
          <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 z-10 relative text-slate-300">
            <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-900">
              <div className="flex items-center space-x-3">
                <div className="w-3 h-3 rounded-full bg-teal-500"></div>
                <h1 className="text-lg font-bold tracking-widest text-white uppercase">Forensic Wipe</h1>
              </div>
            </div>
            <SidebarNav />
            <div className="p-4 border-t border-slate-800 bg-slate-900 text-xs text-slate-500 font-mono text-center">
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
