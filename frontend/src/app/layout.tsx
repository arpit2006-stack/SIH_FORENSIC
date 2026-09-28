import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SessionProvider } from "@/context/SessionContext";
import AppShell from "@/components/AppShell";

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
  title: "Forensic Wipe — Unified Erasure & Evidence Recovery",
  description: "Unified secure erasure & forensic recovery platform complying with IEEE 2883-2022 and Section 63 BSA.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-full overflow-hidden bg-slate-50 text-slate-800 selection:bg-teal-500 selection:text-white`}>
        <SessionProvider>
          <AppShell>
            {children}
          </AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}
