"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Shirt, Plus, ArrowRight, Truck, RefreshCw, CheckCircle2,
  Building2, Phone, X
} from "lucide-react";

interface LaundryVendor {
  id: string;
  name: string;
  contact_person?: string;
  phone: string;
  rate_per_kg?: number;
  rate_per_piece?: number;
}

interface AssetCategory {
  id: string;
  name: string;
  is_linen: boolean;
}

export default function LaundryPage() {
  const [vendors, setVendors] = useState<LaundryVendor[]>([]);
  const [linenCategories, setLinenCategories] = useState<AssetCategory[]>([]);
  const [loading, setLoading] = useState(true);

  // Dispatch modal
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [selectedVendorId, setSelectedVendorId] = useState("");
  const [dispatchItems, setDispatchItems] = useState<{ category_id: string; quantity_sent: number }[]>([]);

  // Add Vendor Modal
  const [showAddVendor, setShowAddVendor] = useState(false);
  const [vName, setVName] = useState("");
  const [vContact, setVContact] = useState("");
  const [vPhone, setVPhone] = useState("");
  const [vRateKg, setVRateKg] = useState("45");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [vData, cData] = await Promise.all([
        apiFetch<LaundryVendor[]>("/operations/laundry/vendors"),
        apiFetch<AssetCategory[]>("/inventory/categories"),
      ]);
      setVendors(vData);
      const linens = cData.filter((c) => c.is_linen);
      setLinenCategories(linens);
      if (vData.length > 0 && !selectedVendorId) setSelectedVendorId(vData[0].id);
      if (linens.length > 0 && dispatchItems.length === 0) {
        setDispatchItems(linens.map((l) => ({ category_id: l.id, quantity_sent: 10 })));
      }
    } catch (e: any) {
      console.error("Error fetching laundry data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleDispatchBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/operations/laundry/batches/dispatch", {
        method: "POST",
        body: JSON.stringify({
          vendor_id: selectedVendorId,
          items: dispatchItems.filter((i) => i.quantity_sent > 0),
        }),
      });
      setShowDispatchModal(false);
      alert("Laundry batch dispatched successfully! Inventory movement ledger updated.");
      fetchData();
    } catch (err: any) {
      alert("Failed to dispatch batch: " + err.message);
    }
  };

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/operations/laundry/vendors", {
        method: "POST",
        body: JSON.stringify({
          name: vName,
          contact_person: vContact,
          phone: vPhone,
          rate_per_kg: parseFloat(vRateKg) || null,
        }),
      });
      setShowAddVendor(false);
      setVName("");
      setVContact("");
      setVPhone("");
      fetchData();
    } catch (err: any) {
      alert("Failed to register vendor: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Linen & Commercial Laundry Tracking</h1>
          <p className="text-xs text-slate-500">Track bedsheet & towel circulation across storage, guest rooms, and vendor custody</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setShowAddVendor(true)}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition"
          >
            + Add Vendor
          </button>
          <button
            onClick={() => setShowDispatchModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Truck size={15} />
            <span>Dispatch Laundry Batch</span>
          </button>
        </div>
      </div>

      {/* Linen Custody Pipeline Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-semibold uppercase">In Rooms (Active Guest Custody)</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-2xl font-bold text-slate-900">38</span>
            <span className="text-xs text-slate-400">pieces</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Circulating across occupied & reserved rooms</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-semibold uppercase">Linen Storage (Clean Buffer)</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-2xl font-bold text-emerald-600">64</span>
            <span className="text-xs text-slate-400">pieces</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Ready for housekeeping replenishment</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-xs text-slate-500 font-semibold uppercase">With Laundry Vendors</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-2xl font-bold text-azure-600">50</span>
            <span className="text-xs text-slate-400">pieces</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">Wash & iron cycle in progress</p>
        </div>
      </div>

      {/* Vendor List Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Contracted Commercial Laundry Vendors</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Vendor Name</th>
                <th className="py-3 px-4">Contact Person</th>
                <th className="py-3 px-4">Phone</th>
                <th className="py-3 px-4">Contract Rate</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {vendors.map((v) => (
                <tr key={v.id} className="hover:bg-slate-50 transition">
                  <td className="py-3 px-4 font-semibold text-slate-900">{v.name}</td>
                  <td className="py-3 px-4 text-slate-600">{v.contact_person || "-"}</td>
                  <td className="py-3 px-4 font-mono text-slate-600">{v.phone}</td>
                  <td className="py-3 px-4 font-medium text-slate-800">
                    {v.rate_per_kg ? `₹${v.rate_per_kg}/kg` : v.rate_per_piece ? `₹${v.rate_per_piece}/piece` : "Standard Rate"}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded uppercase">
                      Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* DISPATCH BATCH MODAL */}
      {showDispatchModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">Dispatch Laundry Batch</h2>
            <p className="text-xs text-slate-500 mb-4">Select vendor and linen quantities sent for washing</p>

            <form onSubmit={handleDispatchBatch} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Laundry Vendor</label>
                <select
                  value={selectedVendorId}
                  onChange={(e) => setSelectedVendorId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {vendors.map((v) => (
                    <option key={v.id} value={v.id}>{v.name}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2 border-t border-b border-slate-100 py-3">
                <span className="text-xs font-bold text-slate-800 uppercase block">Linens to Send</span>
                {linenCategories.map((c, idx) => (
                  <div key={c.id} className="flex items-center justify-between gap-3">
                    <span className="text-xs text-slate-700 truncate">{c.name}</span>
                    <input
                      type="number"
                      min={0}
                      value={dispatchItems[idx]?.quantity_sent || 0}
                      onChange={(e) => {
                        const val = parseInt(e.target.value) || 0;
                        setDispatchItems((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, quantity_sent: val } : item))
                        );
                      }}
                      className="w-20 px-2 py-1 text-xs border border-slate-300 rounded text-right focus:outline-none focus:ring-1 focus:ring-azure-500"
                    />
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDispatchModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Confirm Dispatch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD VENDOR MODAL */}
      {showAddVendor && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Register Laundry Vendor</h2>
            <form onSubmit={handleCreateVendor} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Company / Vendor Name</label>
                <input
                  type="text"
                  required
                  value={vName}
                  onChange={(e) => setVName(e.target.value)}
                  placeholder="e.g. Deluxe Dry Cleaners, Varanasi"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Contact Person</label>
                <input
                  type="text"
                  value={vContact}
                  onChange={(e) => setVContact(e.target.value)}
                  placeholder="e.g. Ramesh Kumar"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    required
                    value={vPhone}
                    onChange={(e) => setVPhone(e.target.value)}
                    placeholder="+91 98765 00000"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Rate per Kg (₹)</label>
                  <input
                    type="number"
                    value={vRateKg}
                    onChange={(e) => setVRateKg(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddVendor(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Save Vendor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

