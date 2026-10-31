"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Zap, Plus, Droplets, RefreshCw, AlertCircle, Building2,
  Calendar, CheckCircle2
} from "lucide-react";

interface UtilityMeter {
  id: string;
  meter_type: string;
  meter_number: string;
  location_name: string;
  room_number?: string;
}

interface UtilityReading {
  id: string;
  meter_type: string;
  meter_number: string;
  location_name: string;
  reading_date: string;
  reading_value: number;
  consumption_units: number;
  cost_incurred: number;
}

export default function UtilitiesPage() {
  const [meters, setMeters] = useState<UtilityMeter[]>([]);
  const [readings, setReadings] = useState<UtilityReading[]>([]);
  const [loading, setLoading] = useState(true);

  // New Reading Modal
  const [showReadingModal, setShowReadingModal] = useState(false);
  const [selectedMeterId, setSelectedMeterId] = useState("");
  const [readingVal, setReadingVal] = useState("");
  const [units, setUnits] = useState("");
  const [cost, setCost] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [mData, rData] = await Promise.all([
        apiFetch<UtilityMeter[]>("/utilities/meters"),
        apiFetch<UtilityReading[]>("/utilities/readings"),
      ]);
      setMeters(mData);
      setReadings(rData);
      if (mData.length > 0 && !selectedMeterId) setSelectedMeterId(mData[0].id);
    } catch (e: any) {
      console.error("Error loading utilities", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRecordReading = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/utilities/readings", {
        method: "POST",
        body: JSON.stringify({
          meter_id: selectedMeterId,
          reading_value: parseFloat(readingVal) || 0,
          consumption_units: parseFloat(units) || 0,
          cost_incurred: parseFloat(cost) || 0,
        }),
      });
      setShowReadingModal(false);
      setReadingVal("");
      setUnits("");
      setCost("");
      fetchData();
    } catch (err: any) {
      alert("Failed to log reading: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Energy & Resource Management</h1>
          <p className="text-xs text-slate-500">Commercial electricity & water meters, consumption history & allocated utility charges</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setShowReadingModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Record Meter Reading</span>
          </button>
        </div>
      </div>

      {/* Meter Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Zap size={18} className="text-amber-500" />
              <h2 className="text-sm font-bold text-slate-900">Commercial Electricity Meter</h2>
            </div>
            <p className="text-xs text-slate-500">Meter #: <strong className="text-slate-800">UPPCL-VAR-COMM-9812</strong></p>
            <p className="text-xs text-slate-500 mt-2">Latest Rate: ~₹8.50 per Commercial Unit (kWh)</p>
          </div>
          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded uppercase">
            Active Master
          </span>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Droplets size={18} className="text-azure-500" />
              <h2 className="text-sm font-bold text-slate-900">Commercial Water Supply & Borewell</h2>
            </div>
            <p className="text-xs text-slate-500">Meter #: <strong className="text-slate-800">JAL-NIGAM-VNS-4421</strong></p>
            <p className="text-xs text-slate-500 mt-2">Monitors facility rooftop tank pump cycles</p>
          </div>
          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded uppercase">
            Active Master
          </span>
        </div>
      </div>

      {/* Readings Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Meter Log & Consumption History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Reading Date</th>
                <th className="py-3 px-4">Utility Type</th>
                <th className="py-3 px-4">Location / Meter</th>
                <th className="py-3 px-4">Meter Reading Value</th>
                <th className="py-3 px-4">Units Consumed</th>
                <th className="py-3 px-4">Billed Cost (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {readings.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No utility readings logged yet. Record your first meter reading above.
                  </td>
                </tr>
              ) : (
                readings.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-medium text-slate-800">{formatDate(r.reading_date)}</td>
                    <td className="py-3 px-4">
                      <span className="font-semibold text-slate-900">{r.meter_type}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-600">{r.location_name}</td>
                    <td className="py-3 px-4 font-mono">{r.reading_value}</td>
                    <td className="py-3 px-4 font-bold text-azure-700">{r.consumption_units} units</td>
                    <td className="py-3 px-4 font-bold text-slate-900">{formatCurrency(r.cost_incurred)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RECORD READING MODAL */}
      {showReadingModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Record Utility Reading</h2>
            <form onSubmit={handleRecordReading} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Utility Meter</label>
                <select
                  value={selectedMeterId}
                  onChange={(e) => setSelectedMeterId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {meters.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.meter_type} — {m.location_name} ({m.meter_number})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Meter Dial Reading Value</label>
                <input
                  type="number"
                  required
                  value={readingVal}
                  onChange={(e) => setReadingVal(e.target.value)}
                  placeholder="e.g. 14280.5"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Units Consumed (kWh / L)</label>
                  <input
                    type="number"
                    required
                    value={units}
                    onChange={(e) => setUnits(e.target.value)}
                    placeholder="e.g. 350"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Cost Incurred (₹)</label>
                  <input
                    type="number"
                    required
                    value={cost}
                    onChange={(e) => setCost(e.target.value)}
                    placeholder="e.g. 2975"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowReadingModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Save Reading
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

