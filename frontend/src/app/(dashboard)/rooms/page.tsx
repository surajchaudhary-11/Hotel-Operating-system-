"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import {
  BedDouble, Plus, Filter, RefreshCw, Eye, Sparkles, Wrench,
  CheckCircle, AlertTriangle, Layers, X
} from "lucide-react";

interface Room {
  id: string;
  room_number: string;
  status: string;
  floor_id: string;
  floor_name: string;
  room_type_name: string;
  base_price: number;
  current_guest_name?: string;
}

interface Floor {
  id: string;
  floor_number: number;
  name: string;
}

interface RoomType {
  id: string;
  name: string;
  base_price: number;
}

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; border: string }> = {
  VACANT_CLEAN: { label: "Vacant Clean", bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  VACANT_DIRTY: { label: "Vacant Dirty", bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  OCCUPIED: { label: "Occupied", bg: "bg-azure-50", text: "text-azure-700", border: "border-azure-200" },
  INSPECTION_PENDING: { label: "Inspection Pending", bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  INSPECTION_FAILED: { label: "Inspection Failed", bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  BLOCKED_MAINTENANCE: { label: "Blocked Maintenance", bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
};

export default function RoomsPage() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([]);
  const [selectedFloor, setSelectedFloor] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  // Modal States
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [room360Data, setRoom360Data] = useState<any>(null);
  const [loadingRoom360, setLoadingRoom360] = useState(false);
  const [showNewRoomModal, setShowNewRoomModal] = useState(false);

  // New Room Form
  const [newRoomNumber, setNewRoomNumber] = useState("");
  const [newFloorId, setNewFloorId] = useState("");
  const [newRoomTypeId, setNewRoomTypeId] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [roomsData, floorsData, typesData] = await Promise.all([
        apiFetch<Room[]>("/rooms"),
        apiFetch<Floor[]>("/rooms/floors"),
        apiFetch<RoomType[]>("/rooms/room-types"),
      ]);
      setRooms(roomsData);
      setFloors(floorsData);
      setRoomTypes(typesData);
      if (floorsData.length > 0 && !newFloorId) setNewFloorId(floorsData[0].id);
      if (typesData.length > 0 && !newRoomTypeId) setNewRoomTypeId(typesData[0].id);
    } catch (e: any) {
      console.error("Error loading rooms", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleStatusChange = async (roomId: string, newStatus: string) => {
    try {
      await apiFetch(`/rooms/${roomId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setRooms((prev) =>
        prev.map((r) => (r.id === roomId ? { ...r, status: newStatus } : r))
      );
    } catch (err: any) {
      alert("Failed to update status: " + err.message);
    }
  };

  const handleViewRoom360 = async (roomId: string) => {
    setSelectedRoomId(roomId);
    setLoadingRoom360(true);
    try {
      const data = await apiFetch<any>(`/rooms/${roomId}/details`);
      setRoom360Data(data);
    } catch (err: any) {
      alert("Failed to fetch room details: " + err.message);
    } finally {
      setLoadingRoom360(false);
    }
  };

  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/rooms", {
        method: "POST",
        body: JSON.stringify({
          room_number: newRoomNumber,
          floor_id: newFloorId,
          room_type_id: newRoomTypeId,
        }),
      });
      setShowNewRoomModal(false);
      setNewRoomNumber("");
      fetchData();
    } catch (err: any) {
      alert("Failed to create room: " + err.message);
    }
  };

  const filteredRooms = rooms.filter((r) => {
    if (selectedFloor !== "ALL" && r.floor_id !== selectedFloor) return false;
    if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Room Matrix & Floor Management</h1>
          <p className="text-xs text-slate-500">Live property room states, occupancy & room 360-degree audits</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition shadow-sm"
            title="Refresh rooms"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setShowNewRoomModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Add Room</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
        {/* Floor Filter */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          <button
            onClick={() => setSelectedFloor("ALL")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
              selectedFloor === "ALL" ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            All Floors ({rooms.length})
          </button>
          {floors.map((f) => (
            <button
              key={f.id}
              onClick={() => setSelectedFloor(f.id)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                selectedFloor === f.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f.name}
            </button>
          ))}
        </div>

        {/* Status Dropdown */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1 text-xs border border-slate-300 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-azure-500"
          >
            <option value="ALL">All States</option>
            <option value="VACANT_CLEAN">Vacant Clean</option>
            <option value="VACANT_DIRTY">Vacant Dirty</option>
            <option value="OCCUPIED">Occupied</option>
            <option value="INSPECTION_PENDING">Inspection Pending</option>
            <option value="BLOCKED_MAINTENANCE">Blocked Maintenance</option>
          </select>
        </div>
      </div>

      {/* Room Grid Matrix */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 animate-pulse">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-40 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
      ) : filteredRooms.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-slate-200">
          <p className="text-sm font-semibold text-slate-700">No rooms match the selected filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filteredRooms.map((room) => {
            const cfg = STATUS_CONFIG[room.status] || {
              label: room.status,
              bg: "bg-slate-50",
              text: "text-slate-700",
              border: "border-slate-200",
            };

            return (
              <div
                key={room.id}
                className="bg-white rounded-xl border border-slate-200/90 shadow-sm p-4 flex flex-col justify-between hover:border-slate-300 transition"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-xl font-bold text-slate-900 tracking-tight">
                        Room {room.room_number}
                      </span>
                      <p className="text-[11px] text-slate-500">{room.room_type_name}</p>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.text} ${cfg.border} uppercase`}
                    >
                      {cfg.label}
                    </span>
                  </div>

                  {room.current_guest_name ? (
                    <div className="mt-3 p-2 rounded-lg bg-azure-50/60 border border-azure-100 text-xs">
                      <p className="text-[10px] uppercase font-bold text-azure-600">Active Guest</p>
                      <p className="font-semibold text-slate-800 truncate">{room.current_guest_name}</p>
                    </div>
                  ) : (
                    <div className="mt-3 p-2 rounded-lg bg-slate-50 text-xs text-slate-400">
                      <span>No active in-house guest</span>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700">
                    {formatCurrency(room.base_price)} <span className="text-[10px] text-slate-400 font-normal">/ night</span>
                  </span>

                  <div className="flex items-center gap-1.5">
                    {/* Status Changer Select */}
                    <select
                      value={room.status}
                      onChange={(e) => handleStatusChange(room.id, e.target.value)}
                      className="text-[11px] py-1 px-1.5 rounded border border-slate-200 bg-slate-50 text-slate-700 focus:outline-none"
                    >
                      <option value="VACANT_CLEAN">Clean</option>
                      <option value="VACANT_DIRTY">Dirty</option>
                      <option value="OCCUPIED">Occupied</option>
                      <option value="INSPECTION_PENDING">Inspect</option>
                      <option value="BLOCKED_MAINTENANCE">Block</option>
                    </select>

                    <button
                      onClick={() => handleViewRoom360(room.id)}
                      className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
                      title="View Room 360 Details"
                    >
                      <Eye size={14} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ROOM 360 DETAIL MODAL */}
      {selectedRoomId && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Room {room360Data?.room?.room_number} — 360° Profile
                </h2>
                <p className="text-xs text-slate-500">
                  {room360Data?.room?.floor_name} • {room360Data?.room?.room_type_name}
                </p>
              </div>
              <button
                onClick={() => {
                  setSelectedRoomId(null);
                  setRoom360Data(null);
                }}
                className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700"
              >
                <X size={20} />
              </button>
            </div>

            {loadingRoom360 ? (
              <div className="py-12 text-center text-xs text-slate-500">Loading full room history...</div>
            ) : (
              <div className="space-y-5 pt-4">
                {/* Active Guest Info */}
                {room360Data?.current_stay && (
                  <div className="p-4 rounded-xl bg-azure-50 border border-azure-200">
                    <p className="text-xs font-bold text-azure-800 uppercase mb-1">Active Stay</p>
                    <p className="text-sm font-bold text-slate-900">{room360Data.current_stay.guest_name}</p>
                    <p className="text-xs text-slate-600">Phone: {room360Data.current_stay.phone}</p>
                    <p className="text-xs text-slate-600">
                      Balance Due:{" "}
                      <span className="font-bold text-rose-600">
                        {formatCurrency(room360Data.current_stay.balance_due)}
                      </span>
                    </p>
                  </div>
                )}

                {/* Assigned Physical Assets */}
                <div>
                  <h3 className="text-xs font-bold text-slate-800 uppercase mb-2">
                    Assets Assigned to Room ({room360Data?.assets?.length ?? 0})
                  </h3>
                  {room360Data?.assets?.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No assets registered to this room.</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {room360Data?.assets?.map((a: any) => (
                        <div key={a.id} className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-xs">
                          <p className="font-semibold text-slate-800">{a.name}</p>
                          <p className="text-[10px] text-slate-500">Tag: {a.asset_tag || "N/A"}</p>
                          <p
                            className={`text-[10px] font-bold mt-1 ${
                              a.condition === "DAMAGED" || a.condition === "MISSING"
                                ? "text-rose-600"
                                : "text-emerald-600"
                            }`}
                          >
                            Condition: {a.condition}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Recent Maintenance */}
                <div>
                  <h3 className="text-xs font-bold text-slate-800 uppercase mb-2">Recent Maintenance Tickets</h3>
                  {room360Data?.recent_tickets?.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">No repair tickets recorded.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {room360Data?.recent_tickets?.map((t: any) => (
                        <div
                          key={t.id}
                          className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs"
                        >
                          <span className="font-medium text-slate-800">{t.title}</span>
                          <span className="text-[10px] bg-slate-200 px-2 py-0.5 rounded font-semibold text-slate-700">
                            {t.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* CREATE ROOM MODAL */}
      {showNewRoomModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Add New Room</h2>
            <form onSubmit={handleCreateRoom} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Room Number</label>
                <input
                  type="text"
                  required
                  value={newRoomNumber}
                  onChange={(e) => setNewRoomNumber(e.target.value)}
                  placeholder="e.g. 105"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Floor</label>
                <select
                  value={newFloorId}
                  onChange={(e) => setNewFloorId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {floors.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name} (Floor {f.floor_number})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Room Category / Type</label>
                <select
                  value={newRoomTypeId}
                  onChange={(e) => setNewRoomTypeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {roomTypes.map((rt) => (
                    <option key={rt.id} value={rt.id}>
                      {rt.name} — {formatCurrency(rt.base_price)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowNewRoomModal(false)}
                  className="px-3 py-2 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm"
                >
                  Create Room
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

