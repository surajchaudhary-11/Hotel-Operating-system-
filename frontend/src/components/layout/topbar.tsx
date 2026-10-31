"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { Plus, Bell, Clock, Calendar, CheckCircle, ShieldAlert } from "lucide-react";
import { apiFetch } from "@/lib/api";

export function Topbar() {
  const { user, activeHotel } = useAuth();
  const [auditRunning, setAuditRunning] = useState(false);
  const [auditMessage, setAuditMessage] = useState<string | null>(null);

  const handleRunNightAudit = async () => {
    if (!confirm("Execute Night Audit now? This will post accrual room charges and generate today's performance report.")) return;
    try {
      setAuditRunning(true);
      await apiFetch("/reports/trigger-audit", { method: "POST" });
      setAuditMessage("Night Audit executed successfully! Report compiled.");
      setTimeout(() => setAuditMessage(null), 4000);
    } catch (err: any) {
      alert("Night Audit failed: " + err.message);
    } finally {
      setAuditRunning(false);
    }
  };

  const todayStr = new Date().toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric"
  });

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between z-20 shrink-0">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <span>{activeHotel?.hotel_name || "HotelOS Management"}</span>
            <span className="text-[10px] font-semibold bg-azure-50 text-azure-700 border border-azure-200 px-2 py-0.5 rounded-full uppercase tracking-wider">
              {activeHotel?.role || "Staff"}
            </span>
          </h1>
          <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
            <span className="flex items-center gap-1">
              <Calendar size={12} className="text-slate-400" />
              {todayStr}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Clock size={12} className="text-slate-400" />
              Asia/Kolkata (IST)
            </span>
          </p>
        </div>

        {auditMessage && (
          <div className="hidden lg:flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-lg animate-fade-in">
            <CheckCircle size={14} />
            <span>{auditMessage}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Night Audit One-Click Button */}
        {activeHotel?.role === "OWNER" || activeHotel?.role === "MANAGER" ? (
          <button
            onClick={handleRunNightAudit}
            disabled={auditRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition disabled:opacity-50"
            title="Execute daily revenue accruals and audit report"
          >
            <Clock size={14} className={auditRunning ? "animate-spin text-azure-600" : "text-slate-500"} />
            <span>{auditRunning ? "Auditing..." : "Night Audit"}</span>
          </button>
        ) : null}

        {/* Quick Check-in Button */}
        <Link
          href="/guests"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm shadow-azure-600/30 transition"
        >
          <Plus size={15} />
          <span>Quick Check-In</span>
        </Link>
      </div>
    </header>
  );
}

