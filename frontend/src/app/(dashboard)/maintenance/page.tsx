"use client";

import React, { useEffect, useState } from "react";
import { apiFetch, apiFetchCached, invalidateApiCache } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Wrench, Plus, CheckCircle, Clock, AlertTriangle,
  RefreshCw, MessageSquare, DollarSign, X, Loader2
} from "lucide-react";

interface Ticket {
  id: string;
  room_id?: string;
  room_number?: string;
  asset_id?: string;
  asset_name?: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  reported_by_name: string;
  estimated_cost: number;
  actual_cost: number;
  created_at: string;
  updates: { id: string; message: string; status_change?: string; cost: number; created_at: string }[];
}

interface Room {
  id: string;
  room_number: string;
}

interface Asset {
  id: string;
  name: string;
}

export default function MaintenancePage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New Ticket Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority, setNewPriority] = useState("MEDIUM");
  const [newRoomId, setNewRoomId] = useState("");
  const [newAssetId, setNewAssetId] = useState("");
  const [newEstCost, setNewEstCost] = useState("");

  // Update Ticket Modal
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [updateMsg, setUpdateMsg] = useState("");
  const [updateStatus, setUpdateStatus] = useState("IN_PROGRESS");
  const [updateCost, setUpdateCost] = useState("");

  const fetchData = async (force = false) => {
    if (force) {
      invalidateApiCache("/operations/maintenance/tickets");
      setRefreshing(true);
    } else if (tickets.length === 0) {
      setLoading(true);
    }
    try {
      const [ticketsData, roomsData, assetsData] = await Promise.all([
        apiFetchCached<Ticket[]>("/operations/maintenance/tickets", {}, 20000),
        apiFetchCached<Room[]>("/rooms", {}, 60000),
        apiFetchCached<Asset[]>("/inventory/assets", {}, 60000),
      ]);
      setTickets(ticketsData);
      setRooms(roomsData);
      setAssets(assetsData);
    } catch (e: any) {
      console.error("Error fetching maintenance data", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await apiFetch("/operations/maintenance/tickets", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle,
          description: newDesc,
          priority: newPriority,
          room_id: newRoomId || null,
          asset_id: newAssetId || null,
          estimated_cost: parseFloat(newEstCost) || 0,
        }),
      });
      setShowCreateModal(false);
      setNewTitle("");
      setNewDesc("");
      setNewEstCost("");
      fetchData(true);
    } catch (err: any) {
      alert("Failed to create ticket: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || isSubmitting) return;
    setIsSubmitting(true);

    try {
      await apiFetch(`/operations/maintenance/tickets/${selectedTicket.id}/updates`, {
        method: "POST",
        body: JSON.stringify({
          message: updateMsg,
          status_change: updateStatus,
          additional_cost: parseFloat(updateCost) || 0,
        }),
      });
      setSelectedTicket(null);
      setUpdateMsg("");
      setUpdateCost("");
      fetchData(true);
    } catch (err: any) {
      alert("Failed to log update: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Maintenance & Equipment Repairs</h1>
          <p className="text-xs text-slate-500">Track appliance tickets, technician updates, parts costs & room unblocking</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm disabled:opacity-60"
            title="Refresh tickets"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-azure-600" : ""} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Report Breakdown</span>
          </button>
        </div>
      </div>

      {/* Ticket List */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-28 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
      ) : tickets.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-slate-200">
          <Wrench size={32} className="mx-auto text-azure-500 mb-2" />
          <p className="text-sm font-semibold text-slate-700">All appliances and rooms are fully operational.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <div
              key={t.id}
              className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-slate-300 transition"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-slate-900">{t.title}</span>
                  <span
                    className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${
                      t.priority === "CRITICAL" || t.priority === "HIGH"
                        ? "bg-rose-50 text-rose-700 border border-rose-200"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {t.priority}
                  </span>
                  <span
                    className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${
                      t.status === "RESOLVED"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>

                <p className="text-xs text-slate-600 max-w-xl">{t.description}</p>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-1">
                  {t.room_number && (
                    <span className="font-semibold text-azure-700 bg-azure-50 px-1.5 py-0.5 rounded border border-azure-200">
                      Room {t.room_number}
                    </span>
                  )}
                  {t.asset_name && <span>Asset: {t.asset_name}</span>}
                  <span>Reported by: {t.reported_by_name}</span>
                  <span>Actual Cost: <strong className="text-slate-800">{formatCurrency(t.actual_cost)}</strong></span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => {
                    setSelectedTicket(t);
                    setUpdateStatus(t.status === "RESOLVED" ? "RESOLVED" : "IN_PROGRESS");
                  }}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-white shadow-sm flex items-center gap-1.5"
                >
                  <MessageSquare size={13} />
                  <span>Update & Cost</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* UPDATE MODAL */}
      {selectedTicket && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">Log Repair Update</h2>
            <p className="text-xs text-slate-500 mb-4">{selectedTicket.title}</p>

            <form onSubmit={handleAddUpdate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Status</label>
                <select
                  value={updateStatus}
                  onChange={(e) => setUpdateStatus(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="WAITING_PARTS">Waiting for Parts</option>
                  <option value="RESOLVED">Resolved (Unblock Room)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Repair Note / Work Done</label>
                <textarea
                  required
                  value={updateMsg}
                  onChange={(e) => setUpdateMsg(e.target.value)}
                  placeholder="e.g. Replaced faulty HDMI connector board, tested with cable box"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  rows={2}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Additional Cost Incurred (₹)</label>
                <input
                  type="number"
                  value={updateCost}
                  onChange={(e) => setUpdateCost(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedTicket(null)}
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
                  <span>{isSubmitting ? "Saving..." : "Save Update"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE TICKET MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Report Issue or Breakdown</h2>
            <form onSubmit={handleCreateTicket} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Issue Title</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. AC Water Leakage in Room 201"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  required
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Describe the issue, error codes, or broken parts"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Affected Room (Optional)</label>
                  <select
                    value={newRoomId}
                    onChange={(e) => setNewRoomId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  >
                    <option value="">No Room (Property-wide)</option>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>Room {r.room_number}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Priority</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical (Blocks Room)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Estimated Repair Cost (₹)</label>
                <input
                  type="number"
                  value={newEstCost}
                  onChange={(e) => setNewEstCost(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
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
                  <span>{isSubmitting ? "Submitting..." : "Submit Ticket"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

