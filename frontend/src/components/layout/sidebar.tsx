"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import {
  LayoutDashboard, CalendarDays, BedDouble, Boxes, Sparkles, Wrench,
  Shirt, Users, TrendingUp, Zap, FileText, Bot, Settings,
  LogOut, ChevronDown, ChevronLeft, ChevronRight, Building2
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { name: "Overview", href: "/overview", icon: LayoutDashboard },
  { name: "Reservations", href: "/reservations", icon: CalendarDays },
  { name: "Rooms & Floors", href: "/rooms", icon: BedDouble },
  { name: "Inventory & Assets", href: "/inventory", icon: Boxes },
  { name: "Housekeeping", href: "/housekeeping", icon: Sparkles },
  { name: "Maintenance", href: "/maintenance", icon: Wrench },
  { name: "Linen & Laundry", href: "/laundry", icon: Shirt },
  { name: "Guests & Stays", href: "/guests", icon: Users },
  { name: "Finance & Profit", href: "/finance", icon: TrendingUp },
  { name: "Energy & Utilities", href: "/utilities", icon: Zap },
  { name: "Daily Reports", href: "/reports", icon: FileText },
  { name: "AI Assistant", href: "/ai", icon: Bot, highlight: true },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, activeHotel, memberships, switchHotel, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [showHotelSwitcher, setShowHotelSwitcher] = useState(false);

  return (
    <aside
      className={cn(
        "h-screen bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 transition-all duration-300 select-none z-30 shrink-0",
        collapsed ? "w-20" : "w-64"
      )}
    >
      {/* Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-slate-800">
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-azure-500 to-tyrian-700 flex items-center justify-center text-white font-extrabold text-lg shadow-md shadow-azure-900/30">
              H
            </div>
            <div>
              <span className="font-bold text-white text-base tracking-tight">HotelOS</span>
              <span className="text-[10px] text-azure-400 block font-semibold tracking-wider uppercase">Varanasi Edition</span>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="w-10 h-10 mx-auto rounded-xl bg-gradient-to-br from-azure-500 to-tyrian-700 flex items-center justify-center text-white font-extrabold text-lg shadow">
            H
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 hidden md:block"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Property Switcher */}
      {!collapsed && (
        <div className="px-3 py-3 border-b border-slate-800/80 relative">
          <button
            onClick={() => setShowHotelSwitcher(!showHotelSwitcher)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-left transition"
          >
            <div className="flex items-center gap-2.5 truncate">
              <Building2 size={16} className="text-azure-400 shrink-0" />
              <div className="truncate">
                <p className="text-xs font-semibold text-white truncate">
                  {activeHotel ? activeHotel.hotel_name : "Select Hotel"}
                </p>
                <p className="text-[11px] text-slate-400">
                  {activeHotel ? `${activeHotel.city} • ${activeHotel.role}` : "No hotel active"}
                </p>
              </div>
            </div>
            <ChevronDown size={14} className="text-slate-400 shrink-0 ml-1" />
          </button>

          {showHotelSwitcher && (
            <div className="absolute top-16 left-3 right-3 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 z-50">
              <p className="text-[10px] uppercase font-bold text-slate-400 px-3 py-1">Your Properties</p>
              {memberships.map((m) => (
                <button
                  key={m.hotel_id}
                  onClick={() => {
                    switchHotel(m.hotel_id);
                    setShowHotelSwitcher(false);
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-700/60 transition",
                    activeHotel?.hotel_id === m.hotel_id ? "text-azure-400 font-semibold bg-slate-700/40" : "text-slate-300"
                  )}
                >
                  <span className="truncate">{m.hotel_name}</span>
                  <span className="text-[10px] bg-slate-900 px-1.5 py-0.5 rounded text-slate-400 uppercase">{m.role}</span>
                </button>
              ))}
              <div className="border-t border-slate-700/80 my-1 pt-1">
                <Link
                  href="/onboard"
                  className="block px-3 py-1.5 text-xs text-azure-400 hover:bg-slate-700/60 transition"
                  onClick={() => setShowHotelSwitcher(false)}
                >
                  + Onboard New Hotel
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Navigation List */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all group",
                isActive
                  ? "bg-azure-600 text-white shadow-sm shadow-azure-900/40 font-semibold"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/70",
                item.highlight && !isActive && "text-azure-400 hover:text-azure-300"
              )}
            >
              <Icon
                size={18}
                className={cn(
                  "shrink-0",
                  isActive ? "text-white" : item.highlight ? "text-azure-400" : "text-slate-400 group-hover:text-white"
                )}
              />
              {!collapsed && (
                <span className="truncate flex-1 flex items-center justify-between">
                  {item.name}
                  {item.highlight && (
                    <span className="text-[9px] font-bold bg-azure-500/20 text-azure-300 border border-azure-500/30 px-1.5 py-0.5 rounded-full">
                      AI
                    </span>
                  )}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User Footer */}
      <div className="p-3 border-t border-slate-800">
        <div className={cn("flex items-center justify-between", collapsed && "flex-col gap-2")}>
          {!collapsed && (
            <div className="truncate pr-2">
              <p className="text-xs font-semibold text-white truncate">{user?.full_name}</p>
              <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
            </div>
          )}
          <button
            onClick={logout}
            title="Log Out"
            className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition shrink-0"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}

