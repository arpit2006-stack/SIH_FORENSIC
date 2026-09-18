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
    section: "Cases",
    items: [
      { label: "Active Cases", href: "/erase/confirm", icon: FolderOpen, accent: "text-slate-400" },
      { label: "Archived", href: "/certify/draft", icon: Archive, accent: "text-slate-400" },
    ],
  },
  {
    section: "Toolkit",
    items: [
      { label: "Hash Verification", href: "/certify/draft", icon: ShieldCheck, accent: "text-emerald-400" },
    ],
  },
];

export default function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="flex-1 p-4 space-y-6 overflow-y-auto">
      {NAV_ITEMS.map((group, gi) => (
        <div key={gi} className="space-y-2">
          {group.section && (
            <h3 className="px-4 text-xs font-semibold text-slate-500 tracking-wider uppercase">
              {group.section}
            </h3>
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
                  className={`flex items-center px-4 py-2.5 rounded-md font-medium transition-colors ${
                    isActive
                      ? "bg-slate-800 text-white shadow-sm"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 mr-3 ${isActive ? item.accent : "text-slate-400"}`}
                  />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
