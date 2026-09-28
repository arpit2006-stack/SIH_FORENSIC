"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  Archive,
  Database,
  ShieldCheck,
  Eraser,
  FileText,
} from "lucide-react";
import { useSession } from "@/context/SessionContext";

const NAV_ITEMS = [
  {
    section: null,
    items: [
      { label: "Dashboard", href: "/", icon: LayoutDashboard, accent: "text-teal-400" },
    ],
  },
  {
    section: "Operations",
    items: [
      { label: "Drive Eraser", href: "/mode-select", icon: Eraser, accent: "text-red-400" },
      { label: "File Eraser", href: "/file-eraser", icon: FileText, accent: "text-amber-400" },
      { label: "Data Recovery", href: "/recovery/scan", icon: Database, accent: "text-teal-400" },
    ],
  },
  {
    section: "Cases & Evidence",
    items: [
      { label: "Active Cases", href: "/audit?tab=cases", icon: FolderOpen, accent: "text-blue-400" },
      { label: "Recovered Artifacts", href: "/audit?tab=artifacts", icon: Archive, accent: "text-purple-400" },
    ],
  },
  {
    section: "Toolkit & Compliance",
    items: [
      { label: "Hash Verification", href: "/audit?tab=ledger", icon: ShieldCheck, accent: "text-emerald-400" },
      { label: "Section 63 Certificate", href: "/certify/draft", icon: FileText, accent: "text-emerald-400" },
    ],
  },
];

interface SidebarNavProps {
  collapsed?: boolean;
}

export default function SidebarNav({ collapsed = false }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav className="flex-1 p-3 space-y-4 overflow-y-auto overflow-x-hidden">
      {NAV_ITEMS.map((group, gi) => (
        <div key={gi} className="space-y-1">
          {group.section && !collapsed && (
            <h3 className="px-3 text-[11px] font-semibold text-slate-500 tracking-wider uppercase mb-1">
              {group.section}
            </h3>
          )}
          {group.section && collapsed && (
            <div className="my-2 border-t border-slate-800/80 mx-2" />
          )}
          <div className="space-y-1">
            {group.items.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));
              const Icon = item.icon;

              return (
                <Link
                  key={item.href + item.label}
                  href={item.href}
                  title={collapsed ? item.label : undefined}
                  className={`flex items-center rounded-lg font-medium transition-all group relative ${
                    collapsed
                      ? "justify-center p-2.5"
                      : "px-3 py-2 text-sm"
                  } ${
                    isActive
                      ? "bg-slate-800 text-white shadow-sm ring-1 ring-slate-700/60"
                      : "text-slate-300 hover:bg-slate-800/70 hover:text-white"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 transition-transform group-hover:scale-110 ${
                      isActive ? item.accent : "text-slate-400 group-hover:text-slate-200"
                    } ${!collapsed ? "mr-3" : ""}`}
                  />
                  {!collapsed && (
                    <span className="truncate whitespace-nowrap">{item.label}</span>
                  )}
                  {isActive && !collapsed && (
                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-400"></div>
                  )}

                  {/* Tooltip for collapsed mode */}
                  {collapsed && (
                    <div className="fixed left-20 ml-2 hidden group-hover:block z-50 px-2.5 py-1 text-xs font-semibold text-white bg-slate-900 border border-slate-700 rounded-md shadow-xl whitespace-nowrap pointer-events-none">
                      {item.label}
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
