"use client";

import React, { useEffect, useState } from "react";
import { apiFetch, apiFetchCached, invalidateApiCache } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  FileText, Download, Clock, Send, CheckCircle2,
  AlertCircle, RefreshCw, MessageCircle, Mail
} from "lucide-react";

export default function ReportsPage() {
  const [report, setReport] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Schedule settings form
  const [waNumber, setWaNumber] = useState("");
  const [email, setEmail] = useState("");
  const [repTime, setRepTime] = useState("23:59");
  const [savingSettings, setSavingSettings] = useState(false);

  const fetchData = async (force = false) => {
    if (force) {
      invalidateApiCache("/reports");
      setRefreshing(true);
    } else if (!report) {
      setLoading(true);
    }
    try {
      const [repData, settsData] = await Promise.all([
        apiFetchCached<any>("/reports/daily", {}, 30000),
        apiFetchCached<any>("/reports/settings", {}, 60000),
      ]);
      setReport(repData);
      setSettings(settsData);
      if (settsData?.whatsapp_recipients?.length > 0) {
        setWaNumber(settsData.whatsapp_recipients[0]);
      }
      if (settsData?.email_recipients?.length > 0) {
        setEmail(settsData.email_recipients[0]);
      }
      if (settsData?.reporting_time) {
        setRepTime(settsData.reporting_time);
      }
    } catch (e: any) {
      console.error("Error loading reports", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTriggerAudit = async () => {
    setTriggering(true);
    try {
      const res = await apiFetch<any>("/reports/trigger-audit", { method: "POST" });
      invalidateApiCache("/reports");
      invalidateApiCache("/finance");
      setReport(res.report);
      alert("Night Audit executed successfully!");
    } catch (err: any) {
      alert("Failed to trigger Night Audit: " + err.message);
    } finally {
      setTriggering(false);
    }
  };

  const handleDownloadPDF = async () => {
    setDownloading(true);
    try {
      const blob = await apiFetch<Blob>("/reports/daily/pdf");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `HotelOS_Daily_EOD_Report_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert("Failed to download PDF report: " + err.message);
    } finally {
      setDownloading(false);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      await apiFetch("/reports/settings", {
        method: "PUT",
        body: JSON.stringify({
          reporting_time: repTime,
          timezone: "Asia/Kolkata",
          whatsapp_recipients: [waNumber],
          email_recipients: [email],
          send_pdf_attachment: true,
          is_active: true,
        }),
      });
      alert("Automated Daily Report schedule saved successfully!");
    } catch (err: any) {
      alert("Failed to save schedule: " + err.message);
    } finally {
      setSavingSettings(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Daily End-of-Day (EOD) Audit Reports</h1>
          <p className="text-xs text-slate-500">Night Audit reconciliations, high-res PDF generation & automated WhatsApp delivery</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm disabled:opacity-60"
            title="Refresh reports"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-azure-600" : ""} />
          </button>
          <button
            onClick={handleTriggerAudit}
            disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-white shadow-sm transition disabled:opacity-50"
          >
            <Clock size={14} className={triggering ? "animate-spin text-azure-400" : ""} />
            <span>{triggering ? "Auditing..." : "Execute Night Audit"}</span>
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition disabled:opacity-50"
          >
            <Download size={14} className={downloading ? "animate-bounce" : ""} />
            <span>{downloading ? "Generating..." : "Download PDF Digest"}</span>
          </button>
        </div>
      </div>

      {/* TODAY'S COMPILED REPORT CARD */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <span className="text-[10px] font-bold text-azure-600 bg-azure-50 px-2.5 py-0.5 rounded-full border border-azure-200 uppercase tracking-wider">
              Official Property Digest
            </span>
            <h2 className="text-lg font-bold text-slate-900 mt-1">
              Daily Operations & Financial Performance Summary
            </h2>
            <p className="text-xs text-slate-500">
              Audit Date: <strong className="text-slate-800">{report?.report_date || "Today"}</strong> • Timezone: Asia/Kolkata (IST)
            </p>
          </div>
          <button
            onClick={handleDownloadPDF}
            className="hidden sm:flex items-center gap-1 text-xs text-azure-600 hover:underline font-semibold"
          >
            <Download size={13} />
            <span>Download High-Resolution PDF</span>
          </button>
        </div>

        {/* 1. Financial Breakdown */}
        <div>
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">
            1. Financial Metrics (Accrual vs. Cash Flow)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Earned Revenue (Accrual)</span>
              <p className="text-base font-bold text-slate-900 mt-1">
                {formatCurrency(report?.financials?.today_earned_revenue_accrual ?? 0)}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Billed nightly tariff</p>
            </div>

            <div className="p-3.5 bg-emerald-50/60 border border-emerald-200 rounded-xl">
              <span className="text-[10px] font-bold text-emerald-800 uppercase">Cash Inflows</span>
              <p className="text-base font-bold text-emerald-700 mt-1">
                {formatCurrency(report?.financials?.today_cash_collections ?? 0)}
              </p>
              <p className="text-[10px] text-emerald-600 mt-1">Actual UPI / Cash / Cards</p>
            </div>

            <div className="p-3.5 bg-rose-50/60 border border-rose-200 rounded-xl">
              <span className="text-[10px] font-bold text-rose-800 uppercase">Operating Expenses</span>
              <p className="text-base font-bold text-rose-700 mt-1">
                {formatCurrency(report?.financials?.today_recorded_expenses ?? 0)}
              </p>
              <p className="text-[10px] text-rose-600 mt-1">Direct & shared expenses</p>
            </div>

            <div className="p-3.5 bg-tyrian-50/60 border border-tyrian-200 rounded-xl">
              <span className="text-[10px] font-bold text-tyrian-800 uppercase">Operating Contribution</span>
              <p className="text-base font-bold text-tyrian-700 mt-1">
                {formatCurrency(report?.financials?.today_operating_contribution ?? 0)}
              </p>
              <p className="text-[10px] text-tyrian-600 mt-1">USALI Standard (GOP)</p>
            </div>
          </div>
        </div>

        {/* 2. Room Inventory & Operations */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
            <h3 className="text-xs font-bold text-slate-800 uppercase mb-3">2. Room Status Breakdown</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Total Available Rooms:</span>
                <span className="font-bold text-slate-900">{report?.occupancy?.total_rooms ?? 0}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Occupied In-House:</span>
                <span className="font-bold text-azure-700">
                  {report?.occupancy?.occupied_rooms ?? 0} ({report?.occupancy?.occupancy_rate_percent ?? 0}%)
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Vacant Clean (Ready):</span>
                <span className="font-semibold text-emerald-700">{report?.occupancy?.vacant_clean ?? 0}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Blocked for Maintenance:</span>
                <span className="font-semibold text-rose-700">{report?.occupancy?.blocked_maintenance ?? 0}</span>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
            <h3 className="text-xs font-bold text-slate-800 uppercase mb-3">3. Operational Queues</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Pending Maintenance Tickets:</span>
                <span className="font-bold text-amber-700">{report?.operations?.pending_maintenance_tickets ?? 0}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Pending Housekeeping Tasks:</span>
                <span className="font-bold text-azure-700">{report?.operations?.pending_housekeeping_tasks ?? 0}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Damaged / Missing Assets:</span>
                <span className="font-bold text-rose-700">{report?.operations?.damaged_or_missing_assets ?? 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AUTOMATED REPORTING SCHEDULE CONFIGURATION */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <MessageCircle size={18} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Automated Daily Report Dispatch</h2>
            <p className="text-xs text-slate-500">Deliver daily financial & operational PDF digest directly to Owner WhatsApp and Email</p>
          </div>
        </div>

        <form onSubmit={handleSaveSettings} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">WhatsApp Recipient Number</label>
            <input
              type="tel"
              required
              value={waNumber}
              onChange={(e) => setWaNumber(e.target.value)}
              placeholder="+91 98765 43210"
              className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Email Recipient Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="owner@hotel.com"
              className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Nightly Reporting Time</label>
            <div className="flex items-center gap-2">
              <input
                type="time"
                value={repTime}
                onChange={(e) => setRepTime(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
              <button
                type="submit"
                disabled={savingSettings}
                className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-xl shadow-sm shrink-0 disabled:opacity-50"
              >
                {savingSettings ? "Saving..." : "Save Schedule"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

