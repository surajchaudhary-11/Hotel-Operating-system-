"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDate, formatTime } from "@/lib/utils";
import {
  Users, Plus, Share2, LogOut, CheckCircle, RefreshCw,
  Copy, Check, UserCheck, ShieldCheck, X
} from "lucide-react";

interface Stay {
  id: string;
  guest_name: string;
  guest_phone: string;
  room_id: string;
  room_number: string;
  check_in_time: string;
  expected_check_out_time: string;
  actual_check_out_time?: string;
  status: string;
  adult_count: number;
  child_count: number;
  room_rate_per_night: number;
  total_room_charge: number;
  total_paid: number;
  balance_due: number;
  registration_token: string;
}

interface Room {
  id: string;
  room_number: string;
  status: string;
  room_type_name: string;
  base_price: number;
}

export default function GuestsPage() {
  const [stays, setStays] = useState<Stay[]>([]);
  const [availableRooms, setAvailableRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Check-In Modal
  const [showCheckInModal, setShowCheckInModal] = useState(false);
  const [gName, setGName] = useState("");
  const [gPhone, setGPhone] = useState("+91 ");
  const [gEmail, setGEmail] = useState("");
  const [gCity, setGCity] = useState("");
  const [gRoomId, setGRoomId] = useState("");
  const [gAdults, setGAdults] = useState("2");
  const [gCheckOutDate, setGCheckOutDate] = useState("");
  const [gAdvanceAmount, setGAdvanceAmount] = useState("");
  const [gPaymentMode, setGPaymentMode] = useState("UPI_QR");

  // Check-Out Settlement Modal
  const [checkoutStay, setCheckoutStay] = useState<Stay | null>(null);
  const [settlementAmount, setSettlementAmount] = useState("");
  const [settlementMode, setSettlementMode] = useState("UPI_QR");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [staysData, roomsData] = await Promise.all([
        apiFetch<Stay[]>("/guests/stays"),
        apiFetch<Room[]>("/rooms"),
      ]);
      setStays(staysData);
      const vacant = roomsData.filter((r) => r.status === "VACANT_CLEAN" || r.status === "VACANT_DIRTY");
      setAvailableRooms(vacant);
      if (vacant.length > 0 && !gRoomId) setGRoomId(vacant[0].id);

      // Default checkout date 2 days from now
      const d = new Date();
      d.setDate(d.getDate() + 2);
      setGCheckOutDate(d.toISOString().slice(0, 16));
    } catch (e: any) {
      console.error("Error fetching guest stays", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCopyLink = (token: string) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const url = `${origin}/checkin/${token}`;
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 3000);
  };

  const handleCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    const selRoom = availableRooms.find((r) => r.id === gRoomId);
    const rate = selRoom ? selRoom.base_price : 3500;

    try {
      await apiFetch("/guests/check-in", {
        method: "POST",
        body: JSON.stringify({
          guest_info: {
            full_name: gName,
            phone: gPhone,
            email: gEmail || null,
            city: gCity || null,
          },
          room_id: gRoomId,
          expected_check_out_time: new Date(gCheckOutDate).toISOString(),
          adult_count: parseInt(gAdults) || 1,
          room_rate_per_night: rate,
          advance_payment_amount: parseFloat(gAdvanceAmount) || 0,
          advance_payment_mode: gPaymentMode,
        }),
      });
      setShowCheckInModal(false);
      setGName("");
      setGPhone("+91 ");
      setGAdvanceAmount("");
      fetchData();
    } catch (err: any) {
      alert("Check-in failed: " + err.message);
    }
  };

  const handleCheckoutSettle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkoutStay) return;

    try {
      await apiFetch(`/guests/stays/${checkoutStay.id}/checkout`, {
        method: "POST",
        body: JSON.stringify({
          settlement_payment_amount: parseFloat(settlementAmount) || 0,
          settlement_payment_mode: settlementMode,
        }),
      });
      setCheckoutStay(null);
      setSettlementAmount("");
      fetchData();
    } catch (err: any) {
      alert("Checkout failed: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Guest Stays & Digital Check-In</h1>
          <p className="text-xs text-slate-500">Front desk reservations, folio balances, payments & tokenized digital check-in links</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setShowCheckInModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Check-In Guest</span>
          </button>
        </div>
      </div>

      {/* Stays Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Guest Name</th>
                <th className="py-3 px-4">Room</th>
                <th className="py-3 px-4">Contact</th>
                <th className="py-3 px-4">Check-In</th>
                <th className="py-3 px-4">Expected Checkout</th>
                <th className="py-3 px-4">Tariff / Night</th>
                <th className="py-3 px-4">Balance Due</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stays.map((stay) => (
                <tr key={stay.id} className="hover:bg-slate-50 transition">
                  <td className="py-3 px-4 font-bold text-slate-900">{stay.guest_name}</td>
                  <td className="py-3 px-4">
                    <span className="font-bold text-azure-700 bg-azure-50 border border-azure-200 px-2 py-0.5 rounded">
                      Room {stay.room_number}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-600">{stay.guest_phone}</td>
                  <td className="py-3 px-4 text-slate-500 whitespace-nowrap">{formatDate(stay.check_in_time)}</td>
                  <td className="py-3 px-4 text-slate-500 whitespace-nowrap">{formatDate(stay.expected_check_out_time)}</td>
                  <td className="py-3 px-4 font-medium">{formatCurrency(stay.room_rate_per_night)}</td>
                  <td className="py-3 px-4">
                    <span
                      className={`font-bold ${
                        stay.balance_due > 0 ? "text-rose-600" : "text-emerald-600"
                      }`}
                    >
                      {formatCurrency(stay.balance_due)}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                        stay.status === "CHECKED_IN"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {stay.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {/* Copy Digital Check-In Link */}
                      <button
                        onClick={() => handleCopyLink(stay.registration_token)}
                        className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-medium transition"
                        title="Copy Guest Digital Self-Check-in Link"
                      >
                        {copiedToken === stay.registration_token ? (
                          <>
                            <Check size={12} className="text-emerald-600" />
                            <span className="text-emerald-600 font-semibold">Copied!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            <span>Portal Link</span>
                          </>
                        )}
                      </button>

                      {stay.status === "CHECKED_IN" && (
                        <button
                          onClick={() => {
                            setCheckoutStay(stay);
                            setSettlementAmount(stay.balance_due.toString());
                          }}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-white text-[11px] font-semibold transition"
                        >
                          <LogOut size={12} />
                          <span>Check-Out</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* CHECK-IN MODAL */}
      {showCheckInModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">Guest Check-In & Room Allocation</h2>
            <p className="text-xs text-slate-500 mb-4">Record guest folio, allocate available room, and log advance</p>

            <form onSubmit={handleCheckIn} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={gName}
                    onChange={(e) => setGName(e.target.value)}
                    placeholder="e.g. Vikramaditya Singh"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    required
                    value={gPhone}
                    onChange={(e) => setGPhone(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Email (Optional)</label>
                  <input
                    type="email"
                    value={gEmail}
                    onChange={(e) => setGEmail(e.target.value)}
                    placeholder="guest@example.com"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">City / Origin</label>
                  <input
                    type="text"
                    value={gCity}
                    onChange={(e) => setGCity(e.target.value)}
                    placeholder="e.g. New Delhi"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Allocated Room</label>
                  <select
                    value={gRoomId}
                    onChange={(e) => setGRoomId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  >
                    {availableRooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        Room {r.room_number} ({r.room_type_name} - {formatCurrency(r.base_price)})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Adult Count</label>
                  <input
                    type="number"
                    min={1}
                    value={gAdults}
                    onChange={(e) => setGAdults(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Expected Check-Out Date & Time</label>
                <input
                  type="datetime-local"
                  required
                  value={gCheckOutDate}
                  onChange={(e) => setGCheckOutDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Advance Payment (₹)</label>
                  <input
                    type="number"
                    value={gAdvanceAmount}
                    onChange={(e) => setGAdvanceAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Mode</label>
                  <select
                    value={gPaymentMode}
                    onChange={(e) => setGPaymentMode(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  >
                    <option value="UPI_QR">UPI / QR Code</option>
                    <option value="CASH">Cash</option>
                    <option value="CREDIT_DEBIT_CARD">Credit / Debit Card</option>
                    <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS)</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCheckInModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Confirm Check-In
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CHECK-OUT SETTLEMENT MODAL */}
      {checkoutStay && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">Check-Out & Folio Settlement</h2>
            <p className="text-xs text-slate-500 mb-4">
              Guest: <strong className="text-slate-800">{checkoutStay.guest_name}</strong> (Room {checkoutStay.room_number})
            </p>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl mb-4 space-y-1.5 text-xs">
              <div className="flex justify-between text-slate-600">
                <span>Total Tariff & Taxes:</span>
                <span>{formatCurrency(checkoutStay.total_room_charge)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Total Paid Previously:</span>
                <span>{formatCurrency(checkoutStay.total_paid)}</span>
              </div>
              <div className="flex justify-between text-slate-900 font-bold border-t border-slate-200 pt-1.5">
                <span>Outstanding Balance Due:</span>
                <span className="text-rose-600">{formatCurrency(checkoutStay.balance_due)}</span>
              </div>
            </div>

            <form onSubmit={handleCheckoutSettle} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Settlement Payment Amount (₹)</label>
                <input
                  type="number"
                  required
                  value={settlementAmount}
                  onChange={(e) => setSettlementAmount(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Mode</label>
                <select
                  value={settlementMode}
                  onChange={(e) => setSettlementMode(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="UPI_QR">UPI / QR Code</option>
                  <option value="CASH">Cash</option>
                  <option value="CREDIT_DEBIT_CARD">Credit / Debit Card</option>
                </select>
              </div>

              <p className="text-[11px] text-slate-400">
                Room {checkoutStay.room_number} will automatically transition to <strong>VACANT_DIRTY</strong> for housekeeping inspection.
              </p>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCheckoutStay(null)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
                >
                  Complete Settlement & Check-Out
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

