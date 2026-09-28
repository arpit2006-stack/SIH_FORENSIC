"use client";

import React, { useState, useEffect } from "react";
import { useSession } from "@/context/SessionContext";
import ClientHeader from "@/components/ClientHeader";
import ClientBanner from "@/components/ClientBanner";
import SidebarNav from "@/components/SidebarNav";
import { ChevronLeft, ChevronRight, HardDriveDownload } from "lucide-react";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { sidebarCollapsed, setSidebarCollapsed, toggleSidebar } = useSession();

  // Auto-collapse sidebar on smaller screens (<1024px) for optimal scaling
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarCollapsed(true);
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [setSidebarCollapsed]);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-slate-50 text-slate-800 antialiased">
      {/* Persistent Left Sidebar with smooth collapse / expand */}
      <aside
        className={`bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 z-20 relative text-slate-300 transition-all duration-300 ease-in-out ${
          sidebarCollapsed ? "w-20" : "w-64"
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center px-5 border-b border-slate-800 bg-slate-900 justify-between overflow-hidden">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="w-3.5 h-3.5 rounded-full bg-teal-400 shrink-0 shadow-[0_0_10px_rgba(45,212,191,0.5)]"></div>
            {!sidebarCollapsed && (
              <h1 className="text-base font-bold tracking-widest text-white uppercase whitespace-nowrap overflow-hidden text-ellipsis">
                Forensic Wipe
              </h1>
            )}
          </div>
          
          {!sidebarCollapsed && (
            <button
              onClick={toggleSidebar}
              title="Collapse Sidebar"
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <SidebarNav collapsed={sidebarCollapsed} />

        {/* Footer / Toggle & Version Tag */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/70 text-slate-500 font-mono text-center flex items-center justify-between">
          {!sidebarCollapsed ? (
            <>
              <span className="text-[10px] tracking-wider text-slate-400">NTRO TOOLKIT V2.4</span>
              <button
                onClick={toggleSidebar}
                title="Collapse Sidebar"
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </>
          ) : (
            <button
              onClick={toggleSidebar}
              title="Expand Sidebar"
              className="w-full flex justify-center p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        <ClientHeader />
        <ClientBanner />

        {/* Scrollable Page Content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6 lg:p-8 relative z-0">
          {children}
        </main>
      </div>
    </div>
  );
}
