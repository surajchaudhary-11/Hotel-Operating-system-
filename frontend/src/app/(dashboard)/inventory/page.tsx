"use client";

import React, { useEffect, useState } from "react";
import { apiFetch, apiFetchCached, invalidateApiCache } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Boxes, Plus, QrCode, ArrowRightLeft, AlertTriangle,
  RefreshCw, CheckCircle2, History, X, ShieldAlert, Loader2
} from "lucide-react";

interface Asset {
  id: string;
  category_id: string;
  category_name: string;
  name: string;
  asset_tag: string;
  qr_code_identifier: string;
  current_location_type: string;
  current_room_number?: string;
  condition: string;
  purchase_price: number;
}

interface AssetCategory {
  id: string;
  name: string;
  is_linen: boolean;
  low_stock_threshold: number;
  total_assets_count: number;
}

interface Transaction {
  id: string;
  asset_name?: string;
  category_name: string;
  transaction_type: string;
  quantity: number;
  from_location: string;
  to_location: string;
  performed_by_name: string;
  notes?: string;
  created_at: string;
}

export default function InventoryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [activeTab, setActiveTab] = useState<"ASSETS" | "LEDGER">("ASSETS");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // QR Modal
  const [selectedQR, setSelectedQR] = useState<{ code: string; name: string } | null>(null);

  // Transfer Modal
  const [transferAsset, setTransferAsset] = useState<Asset | null>(null);
  const [transferType, setTransferType] = useState<string>("ASSIGN_ROOM");
  const [transferToLocation, setTransferToLocation] = useState<string>("");
  const [transferNotes, setTransferNotes] = useState<string>("");

  // Add Asset Modal
  const [showAddAsset, setShowAddAsset] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCategoryId, setNewCategoryId] = useState("");
  const [newTag, setNewTag] = useState("");
  const [newPrice, setNewPrice] = useState("");

  const fetchData = async (force = false) => {
    if (force) {
      invalidateApiCache("/inventory");
      setRefreshing(true);
    } else if (assets.length === 0) {
      setLoading(true);
    }
    try {
      const [assetsData, catsData, txsData] = await Promise.all([
        apiFetchCached<Asset[]>("/inventory/assets", {}, 20000),
        apiFetchCached<AssetCategory[]>("/inventory/categories", {}, 60000),
        apiFetchCached<Transaction[]>("/inventory/transactions", {}, 20000),
      ]);
      setAssets(assetsData);
      setCategories(catsData);
      setTransactions(txsData);
      if (catsData.length > 0 && !newCategoryId) setNewCategoryId(catsData[0].id);
    } catch (e: any) {
      console.error("Error loading inventory", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRecordMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferAsset || isSubmitting) return;
    setIsSubmitting(true);

    try {
      await apiFetch("/inventory/transactions", {
        method: "POST",
        body: JSON.stringify({
          asset_id: transferAsset.id,
          category_id: transferAsset.category_id,
          transaction_type: transferType,
          quantity: 1,
          from_location: transferAsset.current_location_type,
          to_location: transferToLocation || "STORAGE",
          notes: transferNotes,
        }),
      });
      setTransferAsset(null);
      setTransferNotes("");
      fetchData(true);
    } catch (err: any) {
      alert("Failed to record movement: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await apiFetch("/inventory/assets", {
        method: "POST",
        body: JSON.stringify({
          category_id: newCategoryId,
          name: newName,
          asset_tag: newTag,
          purchase_price: parseFloat(newPrice) || 0,
          current_location_type: "STORAGE",
          condition: "GOOD",
        }),
      });
      setShowAddAsset(false);
      setNewName("");
      setNewTag("");
      setNewPrice("");
      fetchData(true);
    } catch (err: any) {
      alert("Failed to register asset: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Inventory & Asset Tracking</h1>
          <p className="text-xs text-slate-500">Transaction-based immutable stock ledger & room asset QR audits</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition shadow-sm disabled:opacity-60"
            title="Refresh inventory"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-azure-600" : ""} />
          </button>
          <button
            onClick={() => setShowAddAsset(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Register Asset</span>
          </button>
        </div>
      </div>

      {/* Categories Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {categories.map((c) => (
          <div key={c.id} className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-[11px] text-slate-500 font-medium block truncate">{c.name}</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-lg font-bold text-slate-900">{c.total_assets_count}</span>
              <span className="text-[10px] text-slate-400">units</span>
            </div>
            {c.is_linen && (
              <span className="mt-2 inline-block text-[9px] font-bold text-azure-700 bg-azure-50 px-1.5 py-0.5 rounded border border-azure-200">
                Linen Pool
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab("ASSETS")}
          className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
            activeTab === "ASSETS" ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          <Boxes size={14} />
          <span>Active Asset Master ({assets.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("LEDGER")}
          className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
            activeTab === "LEDGER" ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          <History size={14} />
          <span>Immutable Ledger ({transactions.length})</span>
        </button>
      </div>

      {/* ASSET MASTER TABLE */}
      {activeTab === "ASSETS" ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Asset Name</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Tag / QR</th>
                  <th className="py-3 px-4">Location</th>
                  <th className="py-3 px-4">Condition</th>
                  <th className="py-3 px-4">Price</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {assets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3 px-4 font-semibold text-slate-900">{asset.name}</td>
                    <td className="py-3 px-4 text-slate-500">{asset.category_name}</td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[11px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                        {asset.asset_tag || "N/A"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {asset.current_room_number ? (
                        <span className="font-semibold text-azure-700 bg-azure-50 border border-azure-200 px-2 py-0.5 rounded">
                          Room {asset.current_room_number}
                        </span>
                      ) : (
                        <span className="text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {asset.current_location_type}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`font-semibold px-2 py-0.5 rounded text-[10px] uppercase ${
                          asset.condition === "GOOD" || asset.condition === "EXCELLENT"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {asset.condition}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-medium">{formatCurrency(asset.purchase_price)}</td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setSelectedQR({ code: asset.qr_code_identifier, name: asset.name })}
                          className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-900 transition"
                          title="View QR Code"
                        >
                          <QrCode size={15} />
                        </button>
                        <button
                          onClick={() => setTransferAsset(asset)}
                          className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-semibold transition"
                          title="Record Movement"
                        >
                          <ArrowRightLeft size={12} />
                          <span>Move</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* IMMUTABLE LEDGER TABLE */
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Asset / Category</th>
                  <th className="py-3 px-4">Transaction Type</th>
                  <th className="py-3 px-4">Movement</th>
                  <th className="py-3 px-4">Logged By</th>
                  <th className="py-3 px-4">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3 px-4 text-slate-500 whitespace-nowrap">{formatDate(tx.created_at)}</td>
                    <td className="py-3 px-4 font-medium text-slate-800">
                      {tx.asset_name || tx.category_name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[10px] font-bold bg-slate-100 px-2 py-0.5 rounded text-slate-700">
                        {tx.transaction_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-slate-500">{tx.from_location}</span>
                      <span className="mx-1 text-slate-400">→</span>
                      <span className="font-semibold text-slate-800">{tx.to_location}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-600">{tx.performed_by_name}</td>
                    <td className="py-3 px-4 text-slate-500 italic max-w-xs truncate">{tx.notes || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* QR MODAL */}
      {selectedQR && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 text-center">
            <h2 className="text-sm font-bold text-slate-900 mb-1">{selectedQR.name}</h2>
            <p className="text-[11px] text-slate-500 mb-4 font-mono truncate">{selectedQR.code}</p>

            <div className="w-48 h-48 mx-auto bg-slate-50 border border-slate-200 rounded-xl p-2 flex items-center justify-center shadow-inner">
              <img
                src={`/api/v1/inventory/qr/generate?code=${encodeURIComponent(selectedQR.code)}`}
                alt="QR Code"
                className="w-full h-full object-contain"
              />
            </div>

            <p className="text-[11px] text-slate-400 mt-3">Scan during room housekeeping audits to verify custody</p>

            <button
              onClick={() => setSelectedQR(null)}
              className="mt-5 w-full py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* RECORD MOVEMENT MODAL */}
      {transferAsset && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">Record Asset Movement</h2>
            <p className="text-xs text-slate-500 mb-4">
              Moving: <span className="font-bold text-slate-800">{transferAsset.name}</span>
            </p>

            <form onSubmit={handleRecordMovement} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Movement Type</label>
                <select
                  value={transferType}
                  onChange={(e) => setTransferType(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="ASSIGN_ROOM">Assign to Room</option>
                  <option value="RETURN_STORAGE">Return to Storage</option>
                  <option value="DISPATCH_LAUNDRY">Dispatch to Laundry</option>
                  <option value="MARK_DAMAGED">Mark as Damaged</option>
                  <option value="MARK_MISSING">Mark as Missing</option>
                  <option value="DISCARD">Scrap / Discard</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">To Location (e.g. Room 101 / Linen Storage)</label>
                <input
                  type="text"
                  required
                  value={transferToLocation}
                  onChange={(e) => setTransferToLocation(e.target.value)}
                  placeholder="e.g. Room 101"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Audit Notes / Reason</label>
                <textarea
                  value={transferNotes}
                  onChange={(e) => setTransferNotes(e.target.value)}
                  placeholder="e.g. Moved for replacement during housekeeping"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  rows={2}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setTransferAsset(null)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm flex items-center gap-1.5 disabled:opacity-60"
                >
                  {isSubmitting && <Loader2 size={13} className="animate-spin" />}
                  <span>{isSubmitting ? "Logging..." : "Log Transaction"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD ASSET MODAL */}
      {showAddAsset && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Register New Asset</h2>
            <form onSubmit={handleCreateAsset} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Asset Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. LG Split AC 1.5 Ton"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Category</label>
                <select
                  value={newCategoryId}
                  onChange={(e) => setNewCategoryId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Asset Tag</label>
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    placeholder="e.g. AC-105"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Purchase Price (₹)</label>
                  <input
                    type="number"
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="35000"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddAsset(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm flex items-center gap-1.5 disabled:opacity-60"
                >
                  {isSubmitting && <Loader2 size={13} className="animate-spin" />}
                  <span>{isSubmitting ? "Registering..." : "Register"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

