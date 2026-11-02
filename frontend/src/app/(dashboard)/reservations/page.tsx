"use client";

import React, { useEffect, useState, useMemo } from "react";
import { apiFetch, invalidateApiCache } from "@/lib/api";
import { formatCurrency, formatDate, formatTime, cn } from "@/lib/utils";
import {
  CalendarDays, Users, BedDouble, Search, Plus, Filter, RefreshCw,
  ChevronLeft, ChevronRight, CheckCircle2, Clock, XCircle, AlertCircle,
  CreditCard, ArrowRightLeft, ShieldCheck, Phone, Mail, Building,
  Tag, FileText, Check, Copy, Loader2, Calendar, UserPlus, Info
} from "lucide-react";

interface Reservation {
  id: string;
  hotel_id: string;
  booking_reference: string;
  booking_source: string;
  external_reference_id?: string;
  group_booking_id?: string;
  guest_id: string;
  guest_name: string;
  guest_phone: string;
  guest_email?: string;
  room_id: string;
  room_number: string;
  room_type_name?: string;
  floor_name?: string;
  check_in_time: string;
  expected_check_out_time: string;
  actual_check_out_time?: string;
  status: "RESERVED" | "CHECKED_IN" | "CHECKED_OUT" | "CANCELLED" | "NO_SHOW";
  adult_count: number;
  child_count: number;
  room_rate_per_night: number;
  total_room_charge: number;
  total_tax_charge: number;
  total_paid: number;
  balance_due: number;
  payment_status: "UNPAID" | "PARTIALLY_PAID" | "PAID" | "REFUNDED";
  special_requests?: string;
  estimated_arrival_time?: string;
  cancellation_reason?: string;
  registration_token: string;
  created_at: string;
}

interface TapeChartBlock {
  reservation_id: string;
  booking_reference: string;
  guest_name: string;
  guest_phone: string;
  room_id: string;
  room_number: string;
  check_in_date: string;
  check_out_date: string;
  status: string;
  booking_source: string;
  payment_status: string;
  total_paid: number;
  balance_due: number;
}

interface TapeChartRoom {
  room_id: string;
  room_number: string;
  room_type: string;
  floor_name: string;
  current_status: string;
  base_price: number;
  blocks: TapeChartBlock[];
}

interface TapeChartResponse {
  start_date: string;
  end_date: string;
  rooms: TapeChartRoom[];
}

interface RoomItem {
  id: string;
  room_number: string;
  room_type_name: string;
  base_price: number;
  status: string;
}

const BOOKING_SOURCES = [
  { value: "DIRECT", label: "Direct Walk-in / Counter", badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  { value: "PHONE", label: "Phone Reservation", badgeColor: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
  { value: "WEBSITE", label: "Hotel Website", badgeColor: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20" },
  { value: "MAKEMYTRIP", label: "MakeMyTrip (MMT)", badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  { value: "BOOKING_COM", label: "Booking.com", badgeColor: "bg-sky-500/10 text-sky-400 border-sky-500/20" },
  { value: "GOIBIBO", label: "Goibibo", badgeColor: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
  { value: "AGODA", label: "Agoda", badgeColor: "bg-teal-500/10 text-teal-400 border-teal-500/20" },
  { value: "CORPORATE", label: "Corporate Account", badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/20" },
  { value: "TRAVEL_AGENT", label: "Travel Agent", badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/20" },
];

export default function ReservationsPage() {
  const [activeTab, setActiveTab] = useState<"calendar" | "list">("calendar");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Calendar State
  const [calendarStartDate, setCalendarStartDate] = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [calendarDays, setCalendarDays] = useState<14 | 30>(14);
  const [tapeChartData, setTapeChartData] = useState<TapeChartResponse | null>(null);

  // Reservations List State
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");

  // Rooms list for modals
  const [allRooms, setAllRooms] = useState<RoomItem[]>([]);

  // Selected reservation for details modal
  const [selectedRes, setSelectedRes] = useState<Reservation | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  // New Reservation Modal
  const [showNewModal, setShowNewModal] = useState(false);
  const [newMode, setNewMode] = useState<"single" | "group">("single");
  const [newRoomId, setNewRoomId] = useState("");
  const [newCheckIn, setNewCheckIn] = useState("");
  const [newCheckOut, setNewCheckOut] = useState("");
  const [newRate, setNewRate] = useState<string>("3000");
  const [newAdults, setNewAdults] = useState("2");
  const [newChildren, setNewChildren] = useState("0");
  const [newSource, setNewSource] = useState("DIRECT");
  const [newExternalRef, setNewExternalRef] = useState("");
  const [newSpecialRequests, setNewSpecialRequests] = useState("");
  const [newArrivalTime, setNewArrivalTime] = useState("14:00");
  const [newAdvanceAmount, setNewAdvanceAmount] = useState("0");
  const [newAdvanceMode, setNewAdvanceMode] = useState("UPI_QR");

  // Guest details for new modal
  const [gName, setGName] = useState("");
  const [gPhone, setGPhone] = useState("+91 ");
  const [gEmail, setGEmail] = useState("");
  const [gCity, setGCity] = useState("");
  const [gState, setGState] = useState("");
  const [gIdType, setGIdType] = useState("AADHAAR_MASKED");
  const [gIdNumber, setGIdNumber] = useState("");

  // Action Modals State
  const [actionLoading, setActionLoading] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [payAmount, setPayAmount] = useState("");
  const [payMode, setPayMode] = useState("UPI_QR");
  const [payRef, setPayRef] = useState("");

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("0");

  const [showReassignModal, setShowReassignModal] = useState(false);
  const [reassignRoomId, setReassignRoomId] = useState("");
  const [reassignReason, setReassignReason] = useState("");

  // Initialize dates
  useEffect(() => {
    const today = new Date();
    const tomorrow = new Date();
    tomorrow.setDate(today.getDate() + 2);
    setNewCheckIn(today.toISOString().slice(0, 10));
    setNewCheckOut(tomorrow.toISOString().slice(0, 10));
  }, []);

  const fetchRooms = async () => {
    try {
      const data = await apiFetch<RoomItem[]>("/rooms");
      setAllRooms(data);
      if (data.length > 0 && !newRoomId) {
        setNewRoomId(data[0].id);
        setNewRate(data[0].base_price?.toString() || "3000");
      }
    } catch (e: any) {
      console.error("Failed to load rooms", e);
    }
  };

  const fetchCalendar = async () => {
    const startStr = calendarStartDate.toISOString().slice(0, 10);
    try {
      const data = await apiFetch<TapeChartResponse>(
        `/reservations/calendar?start_date=${startStr}&days=${calendarDays}`
      );
      setTapeChartData(data);
    } catch (e: any) {
      console.error("Failed to load tape chart", e);
      setErrorMsg("Failed to load tape chart calendar.");
    }
  };

  const fetchReservations = async () => {
    try {
      let query = "/reservations?limit=150";
      if (statusFilter !== "ALL") query += `&status=${statusFilter}`;
      if (sourceFilter !== "ALL") query += `&booking_source=${sourceFilter}`;
      if (searchQuery.trim()) query += `&search=${encodeURIComponent(searchQuery.trim())}`;
      const data = await apiFetch<Reservation[]>(query);
      setReservations(data);
    } catch (e: any) {
      console.error("Failed to load reservations list", e);
      setErrorMsg("Failed to load reservations.");
    }
  };

  const loadData = async (force = false) => {
    if (force) {
      invalidateApiCache("/reservations");
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorMsg(null);
    try {
      await Promise.all([fetchRooms(), fetchCalendar(), fetchReservations()]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [calendarStartDate, calendarDays, statusFilter, sourceFilter]);

  // Handle Search Debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchReservations();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Date list for Calendar headers
  const calendarDates = useMemo(() => {
    const list: Date[] = [];
    for (let i = 0; i < calendarDays; i++) {
      const d = new Date(calendarStartDate);
      d.setDate(d.getDate() + i);
      list.push(d);
    }
    return list;
  }, [calendarStartDate, calendarDays]);

  const handlePrevDates = () => {
    setCalendarStartDate((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() - calendarDays);
      return d;
    });
  };

  const handleNextDates = () => {
    setCalendarStartDate((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() + calendarDays);
      return d;
    });
  };

  const handleToday = () => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    setCalendarStartDate(d);
  };

  // Open single booking modal preselected
  const handleCellClick = (roomId: string, date: Date) => {
    setNewRoomId(roomId);
    const inStr = date.toISOString().slice(0, 10);
    const outD = new Date(date);
    outD.setDate(outD.getDate() + 2);
    const outStr = outD.toISOString().slice(0, 10);
    setNewCheckIn(inStr);
    setNewCheckOut(outStr);
    const r = allRooms.find((rm) => rm.id === roomId);
    if (r) setNewRate(r.base_price?.toString() || "3000");
    setShowNewModal(true);
  };

  // Create Reservation Submit
  const handleCreateReservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gName.trim() || !gPhone.trim()) {
      alert("Guest Name and Phone are required.");
      return;
    }
    setActionLoading(true);
    try {
      const checkInDt = new Date(`${newCheckIn}T12:00:00Z`).toISOString();
      const checkOutDt = new Date(`${newCheckOut}T11:00:00Z`).toISOString();

      const payload = {
        room_id: newRoomId,
        check_in_time: checkInDt,
        expected_check_out_time: checkOutDt,
        adult_count: parseInt(newAdults) || 2,
        child_count: parseInt(newChildren) || 0,
        room_rate_per_night: parseFloat(newRate) || 3000,
        booking_source: newSource,
        external_reference_id: newExternalRef.trim() || undefined,
        special_requests: newSpecialRequests.trim() || undefined,
        estimated_arrival_time: newArrivalTime.trim() || "14:00",
        advance_payment_amount: parseFloat(newAdvanceAmount) || 0,
        advance_payment_mode: newAdvanceMode,
        guest_info: {
          full_name: gName.trim(),
          phone: gPhone.trim(),
          email: gEmail.trim() || undefined,
          city: gCity.trim() || undefined,
          state: gState.trim() || undefined,
          id_type: gIdType,
          id_number_masked: gIdNumber.trim() || undefined,
          nationality: "Indian"
        }
      };

      const res = await apiFetch<Reservation>("/reservations", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      setShowNewModal(false);
      // Reset form
      setGName("");
      setGPhone("+91 ");
      setGEmail("");
      setGIdNumber("");
      setNewAdvanceAmount("0");
      setNewExternalRef("");
      setNewSpecialRequests("");
      loadData(true);
      setSelectedRes(res);
    } catch (err: any) {
      alert(err.message || "Failed to create reservation");
    } finally {
      setActionLoading(false);
    }
  };

  // Check In from Details
  const handleCheckIn = async (resId: string) => {
    if (!confirm("Confirm check-in for this guest? Room status will update to OCCUPIED.")) return;
    setActionLoading(true);
    try {
      const updated = await apiFetch<Reservation>(`/reservations/${resId}/checkin`, {
        method: "POST"
      });
      setSelectedRes(updated);
      loadData(true);
    } catch (e: any) {
      alert(e.message || "Failed to check in");
    } finally {
      setActionLoading(false);
    }
  };

  // Record Payment
  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRes) return;
    const amount = parseFloat(payAmount);
    if (!amount || amount <= 0) {
      alert("Enter a valid amount greater than 0");
      return;
    }
    setActionLoading(true);
    try {
      const updated = await apiFetch<Reservation>(`/reservations/${selectedRes.id}/payments`, {
        method: "POST",
        body: JSON.stringify({
          amount: amount,
          payment_mode: payMode,
          transaction_reference: payRef.trim() || undefined
        })
      });
      setSelectedRes(updated);
      setShowPaymentModal(false);
      setPayAmount("");
      setPayRef("");
      loadData(true);
    } catch (e: any) {
      alert(e.message || "Failed to record payment");
    } finally {
      setActionLoading(false);
    }
  };

  // Reassign Room
  const handleReassignRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRes || !reassignRoomId) return;
    setActionLoading(true);
    try {
      const updated = await apiFetch<Reservation>(`/reservations/${selectedRes.id}/reassign`, {
        method: "POST",
        body: JSON.stringify({
          new_room_id: reassignRoomId,
          reason: reassignReason.trim() || undefined
        })
      });
      setSelectedRes(updated);
      setShowReassignModal(false);
      setReassignReason("");
      loadData(true);
    } catch (e: any) {
      alert(e.message || "Failed to reassign room. Check for overlap.");
    } finally {
      setActionLoading(false);
    }
  };

  // Cancel Reservation
  const handleCancelReservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRes) return;
    if (!cancelReason.trim()) {
      alert("Cancellation reason is mandatory.");
      return;
    }
    setActionLoading(true);
    try {
      const updated = await apiFetch<Reservation>(`/reservations/${selectedRes.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({
          cancellation_reason: cancelReason.trim(),
          refund_amount: parseFloat(refundAmount) || 0
        })
      });
      setSelectedRes(updated);
      setShowCancelModal(false);
      setCancelReason("");
      setRefundAmount("0");
      loadData(true);
    } catch (e: any) {
      alert(e.message || "Failed to cancel reservation");
    } finally {
      setActionLoading(false);
    }
  };

  const getSourceBadge = (source: string) => {
    const match = BOOKING_SOURCES.find((s) => s.value === source);
    return match ? (
      <span className={cn("px-2 py-0.5 text-[10px] font-bold rounded border uppercase tracking-wider", match.badgeColor)}>
        {match.label.split(" ")[0]}
      </span>
    ) : (
      <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-800 text-slate-300 border border-slate-700 uppercase">
        {source}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "RESERVED":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30">Reserved</span>;
      case "CHECKED_IN":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">In-House</span>;
      case "CHECKED_OUT":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-slate-700/50 text-slate-300 border border-slate-600">Checked Out</span>;
      case "CANCELLED":
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30">Cancelled</span>;
      default:
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-slate-800 text-slate-400">{status}</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto p-4 md:p-6 text-slate-200">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-azure-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-azure-900/20">
              <CalendarDays size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                Reservations & Tape Chart
              </h1>
              <p className="text-xs text-slate-400">
                Visual room availability timeline, advance bookings, OTA channels & group management
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          {/* Tab Switcher */}
          <div className="flex bg-slate-800/80 p-1 rounded-xl border border-slate-700/60">
            <button
              onClick={() => setActiveTab("calendar")}
              className={cn(
                "px-3.5 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition",
                activeTab === "calendar"
                  ? "bg-azure-600 text-white shadow-md shadow-azure-600/30"
                  : "text-slate-400 hover:text-white"
              )}
            >
              <CalendarDays size={14} />
              Tape Chart
            </button>
            <button
              onClick={() => setActiveTab("list")}
              className={cn(
                "px-3.5 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition",
                activeTab === "list"
                  ? "bg-azure-600 text-white shadow-md shadow-azure-600/30"
                  : "text-slate-400 hover:text-white"
              )}
            >
              <FileText size={14} />
              Reservations List
            </button>
          </div>

          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="p-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white rounded-xl transition"
            title="Refresh Data"
          >
            <RefreshCw size={16} className={cn(refreshing && "animate-spin text-azure-400")} />
          </button>

          <button
            onClick={() => {
              setNewMode("single");
              setShowNewModal(true);
            }}
            className="px-4 py-2 bg-gradient-to-r from-azure-500 to-indigo-600 hover:from-azure-600 hover:to-indigo-700 text-white rounded-xl text-xs font-bold shadow-lg shadow-azure-900/30 flex items-center gap-2 transition"
          >
            <Plus size={16} />
            New Reservation
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 px-4 py-3 rounded-xl text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-rose-400" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-slate-400 hover:text-white">
            <XCircle size={14} />
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* VIEW A: TAPE CHART / CALENDAR */}
      {/* ------------------------------------------------------------- */}
      {activeTab === "calendar" && (
        <div className="space-y-4">
          {/* Calendar Controls Bar */}
          <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-2xl flex flex-wrap items-center justify-between gap-4">
            {/* Date Navigation */}
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrevDates}
                className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 hover:text-white transition"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={handleToday}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs font-semibold text-white transition"
              >
                Today
              </button>
              <button
                onClick={handleNextDates}
                className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 hover:text-white transition"
              >
                <ChevronRight size={16} />
              </button>

              <span className="text-xs font-semibold text-slate-300 ml-2">
                {calendarDates[0]?.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                {" — "}
                {calendarDates[calendarDates.length - 1]?.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
              </span>
            </div>

            {/* Days Window Toggle & Legend */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"></span>
                  Reserved
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block"></span>
                  In-House
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-400 inline-block"></span>
                  Checked Out
                </span>
              </div>

              <div className="flex bg-slate-800/80 p-0.5 rounded-lg border border-slate-700/60">
                <button
                  onClick={() => setCalendarDays(14)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-semibold rounded-md transition",
                    calendarDays === 14 ? "bg-azure-600 text-white" : "text-slate-400 hover:text-white"
                  )}
                >
                  14 Days
                </button>
                <button
                  onClick={() => setCalendarDays(30)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-semibold rounded-md transition",
                    calendarDays === 30 ? "bg-azure-600 text-white" : "text-slate-400 hover:text-white"
                  )}
                >
                  30 Days
                </button>
              </div>
            </div>
          </div>

          {/* Tape Chart Grid Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl relative">
            {loading ? (
              <div className="py-24 flex flex-col items-center justify-center gap-3 text-slate-400">
                <Loader2 size={32} className="animate-spin text-azure-400" />
                <p className="text-xs font-semibold">Loading tape chart timeline...</p>
              </div>
            ) : tapeChartData && tapeChartData.rooms.length > 0 ? (
              <div className="overflow-x-auto select-none">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-slate-950 border-b border-slate-800">
                      {/* Fixed Room Header */}
                      <th className="sticky left-0 z-20 bg-slate-950 px-4 py-3 text-left text-xs font-bold text-slate-300 w-48 min-w-[190px] border-r border-slate-800 shadow-md">
                        Room & Type
                      </th>
                      {/* Date Columns */}
                      {calendarDates.map((dateObj) => {
                        const isToday = dateObj.toDateString() === new Date().toDateString();
                        const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
                        return (
                          <th
                            key={dateObj.toISOString()}
                            className={cn(
                              "text-center py-2 px-1 text-[11px] font-semibold border-r border-slate-800/80 min-w-[56px]",
                              isToday ? "bg-azure-500/10 text-azure-300 font-bold" : "text-slate-400",
                              isWeekend && !isToday && "bg-slate-900/40 text-slate-400"
                            )}
                          >
                            <span className="block text-[9px] uppercase tracking-wider text-slate-400">
                              {dateObj.toLocaleDateString("en-IN", { weekday: "narrow" })}
                            </span>
                            <span className={cn("text-xs", isToday && "text-azure-400 font-extrabold")}>
                              {dateObj.getDate()}
                            </span>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {tapeChartData.rooms.map((room) => {
                      return (
                        <tr
                          key={room.room_id}
                          className="border-b border-slate-800/60 hover:bg-slate-850/40 transition group"
                        >
                          {/* Left Room Column */}
                          <td className="sticky left-0 z-10 bg-slate-900 group-hover:bg-slate-850 px-4 py-3 border-r border-slate-800 shadow-md">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-sm text-white">
                                Room {room.room_number}
                              </span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                                {room.room_type}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-0.5">
                              <span>{room.floor_name}</span>
                              <span className="text-azure-400 font-semibold">{formatCurrency(room.base_price)}</span>
                            </div>
                          </td>

                          {/* Date Cells */}
                          {calendarDates.map((d) => {
                            const dateStr = d.toISOString().slice(0, 10);
                            const isToday = d.toDateString() === new Date().toDateString();

                            // Check if a block covers this date
                            // Notice: Check-in date inclusive, check-out date exclusive
                            const activeBlock = room.blocks.find((b) => {
                              return dateStr >= b.check_in_date && dateStr < b.check_out_date;
                            });

                            const isBlockStart = activeBlock && activeBlock.check_in_date === dateStr;

                            return (
                              <td
                                key={dateStr}
                                onClick={() => {
                                  if (activeBlock) {
                                    // Fetch and open reservation details
                                    apiFetch<Reservation>(`/reservations/${activeBlock.reservation_id}`).then((r) => {
                                      setSelectedRes(r);
                                    });
                                  } else {
                                    handleCellClick(room.room_id, d);
                                  }
                                }}
                                className={cn(
                                  "p-1 text-center border-r border-slate-800/80 min-w-[56px] h-14 relative cursor-pointer transition",
                                  isToday && "bg-azure-500/5",
                                  !activeBlock && "hover:bg-azure-500/10"
                                )}
                              >
                                {activeBlock ? (
                                  <div
                                    title={`${activeBlock.guest_name} (${activeBlock.booking_reference}) • ${activeBlock.status}`}
                                    className={cn(
                                      "h-10 rounded-lg p-1.5 flex flex-col justify-center text-left text-xs transition shadow-sm overflow-hidden",
                                      activeBlock.status === "RESERVED" && "bg-gradient-to-r from-amber-500/20 to-amber-600/30 border border-amber-500/40 text-amber-200 hover:border-amber-400",
                                      activeBlock.status === "CHECKED_IN" && "bg-gradient-to-r from-emerald-500/20 to-teal-600/30 border border-emerald-500/40 text-emerald-200 hover:border-emerald-400",
                                      activeBlock.status === "CHECKED_OUT" && "bg-slate-800/70 border border-slate-700 text-slate-300"
                                    )}
                                  >
                                    <span className="font-bold text-[10px] truncate leading-tight">
                                      {activeBlock.guest_name.split(" ")[0]}
                                    </span>
                                    <span className="text-[9px] text-slate-400 truncate leading-tight">
                                      {activeBlock.booking_reference.replace("BK-", "")}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-[10px] text-transparent group-hover:text-slate-600 flex items-center justify-center">
                                    +
                                  </span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-20 text-center text-slate-400 text-xs">
                No rooms available or configured in this property.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* VIEW B: RESERVATIONS LIST TABLE */}
      {/* ------------------------------------------------------------- */}
      {activeTab === "list" && (
        <div className="space-y-4">
          {/* Search & Filter Toolbar */}
          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-2xl flex flex-col lg:flex-row items-center justify-between gap-4">
            {/* Search Input */}
            <div className="relative w-full lg:w-96">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search guest, phone, ref, voucher..."
                className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-azure-500 transition"
              />
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-azure-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="RESERVED">Reserved</option>
                <option value="CHECKED_IN">In-House</option>
                <option value="CHECKED_OUT">Checked Out</option>
                <option value="CANCELLED">Cancelled</option>
              </select>

              {/* Source Filter */}
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="bg-slate-800/80 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-azure-500"
              >
                <option value="ALL">All Channels</option>
                {BOOKING_SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-slate-400 font-bold uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="px-5 py-3.5">Booking Ref</th>
                    <th className="px-5 py-3.5">Guest Info</th>
                    <th className="px-5 py-3.5">Room</th>
                    <th className="px-5 py-3.5">Stay Period</th>
                    <th className="px-5 py-3.5">Folio / Financials</th>
                    <th className="px-5 py-3.5">Status</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="text-center py-16 text-slate-400">
                        <Loader2 size={24} className="animate-spin text-azure-400 mx-auto mb-2" />
                        Loading reservations...
                      </td>
                    </tr>
                  ) : reservations.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-16 text-slate-500">
                        No reservations found matching current filters.
                      </td>
                    </tr>
                  ) : (
                    reservations.map((res) => (
                      <tr key={res.id} className="hover:bg-slate-800/30 transition">
                        {/* Booking Ref & Channel */}
                        <td className="px-5 py-4 font-mono font-bold text-white whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span>{res.booking_reference}</span>
                          </div>
                          <div className="mt-1 flex items-center gap-1.5">
                            {getSourceBadge(res.booking_source)}
                            {res.external_reference_id && (
                              <span className="text-[10px] text-slate-400">
                                {res.external_reference_id}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Guest */}
                        <td className="px-5 py-4">
                          <p className="font-semibold text-white">{res.guest_name}</p>
                          <p className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                            <Phone size={11} className="text-slate-500" />
                            {res.guest_phone}
                          </p>
                        </td>

                        {/* Room */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          <p className="font-bold text-white">Room {res.room_number}</p>
                          <p className="text-[11px] text-slate-400">{res.room_type_name || "Standard"}</p>
                        </td>

                        {/* Stay Period */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          <p className="text-white font-medium">
                            {formatDate(res.check_in_time)} → {formatDate(res.expected_check_out_time)}
                          </p>
                          <p className="text-[11px] text-slate-400">
                            {Math.max(1, Math.round((new Date(res.expected_check_out_time).getTime() - new Date(res.check_in_time).getTime()) / (1000 * 60 * 60 * 24)))} Nights • {res.adult_count} Adults
                          </p>
                        </td>

                        {/* Financials */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          <p className="font-bold text-white">{formatCurrency(res.total_room_charge + res.total_tax_charge)}</p>
                          <p className="text-[11px] text-slate-400">
                            Paid: <span className="text-emerald-400 font-semibold">{formatCurrency(res.total_paid)}</span>
                            {res.balance_due > 0 && (
                              <span className="text-rose-400 font-semibold ml-1.5">
                                (Due: {formatCurrency(res.balance_due)})
                              </span>
                            )}
                          </p>
                        </td>

                        {/* Status */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          {getStatusBadge(res.status)}
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-2">
                            {res.status === "RESERVED" && (
                              <button
                                onClick={() => handleCheckIn(res.id)}
                                className="px-2.5 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-bold transition flex items-center gap-1"
                              >
                                <Check size={12} />
                                Check-In
                              </button>
                            )}

                            <button
                              onClick={() => setSelectedRes(res)}
                              className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-xs font-semibold transition"
                            >
                              Details
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 1: NEW RESERVATION MODAL */}
      {/* ------------------------------------------------------------- */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
            <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-base text-white">Create New Hotel Reservation</h3>
                <p className="text-xs text-slate-400">Advance bookings, walk-ins, and OTA channel vouchers</p>
              </div>
              <button
                onClick={() => setShowNewModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <XCircle size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateReservation} className="p-6 space-y-5">
              {/* Stay Period & Room */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Check-in Date *</label>
                  <input
                    type="date"
                    required
                    value={newCheckIn}
                    onChange={(e) => setNewCheckIn(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Expected Check-out Date *</label>
                  <input
                    type="date"
                    required
                    value={newCheckOut}
                    onChange={(e) => setNewCheckOut(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Assign Room *</label>
                  <select
                    required
                    value={newRoomId}
                    onChange={(e) => {
                      setNewRoomId(e.target.value);
                      const r = allRooms.find((rm) => rm.id === e.target.value);
                      if (r) setNewRate(r.base_price?.toString() || "3000");
                    }}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                  >
                    {allRooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        Room {r.room_number} — {r.room_type_name} ({formatCurrency(r.base_price)}/night)
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Room Rate / Night (INR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={newRate}
                    onChange={(e) => setNewRate(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                  />
                </div>
              </div>

              {/* Guest Profile */}
              <div className="pt-2 border-t border-slate-800">
                <h4 className="text-xs font-bold uppercase text-azure-400 tracking-wider mb-3">Guest Information</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Full Name *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Rahul Sharma"
                      value={gName}
                      onChange={(e) => setGName(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Phone Number *</label>
                    <input
                      type="text"
                      required
                      placeholder="+91 9876543210"
                      value={gPhone}
                      onChange={(e) => setGPhone(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Email Address</label>
                    <input
                      type="email"
                      placeholder="guest@example.com"
                      value={gEmail}
                      onChange={(e) => setGEmail(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">City & State</label>
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="City"
                        value={gCity}
                        onChange={(e) => setGCity(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                      />
                      <input
                        type="text"
                        placeholder="State"
                        value={gState}
                        onChange={(e) => setGState(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Channel & Financials */}
              <div className="pt-2 border-t border-slate-800">
                <h4 className="text-xs font-bold uppercase text-azure-400 tracking-wider mb-3">Channel & Payment</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Booking Source *</label>
                    <select
                      value={newSource}
                      onChange={(e) => setNewSource(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    >
                      {BOOKING_SOURCES.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">External OTA Reference ID</label>
                    <input
                      type="text"
                      placeholder="e.g. MMT-8912384 or BKNG-7781"
                      value={newExternalRef}
                      onChange={(e) => setNewExternalRef(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Advance Deposit (INR)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={newAdvanceAmount}
                      onChange={(e) => setNewAdvanceAmount(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Payment Mode</label>
                    <select
                      value={newAdvanceMode}
                      onChange={(e) => setNewAdvanceMode(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                    >
                      <option value="UPI_QR">UPI QR Code</option>
                      <option value="CASH">Cash</option>
                      <option value="CREDIT_DEBIT_CARD">Credit / Debit Card</option>
                      <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Special Requests */}
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Special Requests / Preferences</label>
                <textarea
                  rows={2}
                  placeholder="e.g. High floor, extra pillows, early check-in requested"
                  value={newSpecialRequests}
                  onChange={(e) => setNewSpecialRequests(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 bg-gradient-to-r from-azure-500 to-indigo-600 hover:from-azure-600 hover:to-indigo-700 text-white rounded-xl text-xs font-bold shadow-lg shadow-azure-900/30 flex items-center gap-2 transition"
                >
                  {actionLoading && <Loader2 size={14} className="animate-spin" />}
                  Confirm Reservation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 2: RESERVATION DETAILS & FOLIO */}
      {/* ------------------------------------------------------------- */}
      {selectedRes && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
            {/* Header */}
            <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-azure-500/20 text-azure-400 flex items-center justify-center font-bold">
                  {selectedRes.room_number}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-white">{selectedRes.booking_reference}</h3>
                    {getStatusBadge(selectedRes.status)}
                  </div>
                  <p className="text-xs text-slate-400">
                    {getSourceBadge(selectedRes.booking_source)}
                    {selectedRes.external_reference_id && ` • ${selectedRes.external_reference_id}`}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedRes(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <XCircle size={18} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Guest & Room Details Grid */}
              <div className="grid grid-cols-2 gap-4 bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80">
                <div>
                  <p className="text-[11px] uppercase font-bold text-slate-400">Guest Name</p>
                  <p className="text-sm font-bold text-white mt-0.5">{selectedRes.guest_name}</p>
                  <p className="text-xs text-slate-400 flex items-center gap-1 mt-1">
                    <Phone size={12} className="text-slate-500" />
                    {selectedRes.guest_phone}
                  </p>
                  {selectedRes.guest_email && (
                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                      <Mail size={12} className="text-slate-500" />
                      {selectedRes.guest_email}
                    </p>
                  )}
                </div>

                <div>
                  <p className="text-[11px] uppercase font-bold text-slate-400">Room Details</p>
                  <p className="text-sm font-bold text-white mt-0.5">
                    Room {selectedRes.room_number} ({selectedRes.room_type_name || "Standard"})
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {formatDate(selectedRes.check_in_time)} → {formatDate(selectedRes.expected_check_out_time)}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Rate: <span className="text-azure-400 font-semibold">{formatCurrency(selectedRes.room_rate_per_night)}/night</span>
                  </p>
                </div>
              </div>

              {/* Folio Financials Breakdown */}
              <div className="bg-slate-800/40 p-4 rounded-2xl border border-slate-700/60 space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Room Charges:</span>
                  <span className="font-semibold text-white">{formatCurrency(selectedRes.total_room_charge)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">GST (12%):</span>
                  <span className="font-semibold text-white">{formatCurrency(selectedRes.total_tax_charge)}</span>
                </div>
                <div className="flex items-center justify-between text-xs font-bold pt-2 border-t border-slate-700/60">
                  <span className="text-slate-300">Total Folio Charge:</span>
                  <span className="text-azure-400 text-sm">
                    {formatCurrency(selectedRes.total_room_charge + selectedRes.total_tax_charge)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs pt-1">
                  <span className="text-slate-400">Advance Paid / Deposits:</span>
                  <span className="font-semibold text-emerald-400">{formatCurrency(selectedRes.total_paid)}</span>
                </div>
                <div className="flex items-center justify-between text-xs font-bold pt-1">
                  <span className="text-slate-300">Balance Due:</span>
                  <span className={cn("text-sm", selectedRes.balance_due > 0 ? "text-rose-400" : "text-emerald-400")}>
                    {formatCurrency(selectedRes.balance_due)}
                  </span>
                </div>
              </div>

              {/* Special Requests or Cancellation Reason */}
              {selectedRes.special_requests && (
                <div className="bg-slate-800/30 p-3 rounded-xl border border-slate-800 text-xs">
                  <span className="font-bold text-azure-400 block mb-0.5">Special Requests:</span>
                  <p className="text-slate-300">{selectedRes.special_requests}</p>
                </div>
              )}

              {selectedRes.cancellation_reason && (
                <div className="bg-rose-500/10 p-3 rounded-xl border border-rose-500/20 text-xs text-rose-300">
                  <span className="font-bold block mb-0.5">Cancellation Reason:</span>
                  <p>{selectedRes.cancellation_reason}</p>
                </div>
              )}

              {/* Digital Check-In Share Link */}
              <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                <div className="flex items-center gap-2 text-xs text-slate-400 truncate">
                  <ShieldCheck size={16} className="text-azure-400 shrink-0" />
                  <span className="truncate">Digital Check-in Token: {selectedRes.registration_token}</span>
                </div>
                <button
                  onClick={() => {
                    const url = `${window.location.origin}/checkin/${selectedRes.registration_token}`;
                    navigator.clipboard.writeText(url);
                    setCopiedLink(true);
                    setTimeout(() => setCopiedLink(false), 2000);
                  }}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center gap-1 shrink-0 ml-2"
                >
                  {copiedLink ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  {copiedLink ? "Copied!" : "Copy Link"}
                </button>
              </div>

              {/* Actions Footer */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
                <div className="flex items-center gap-2">
                  {selectedRes.status === "RESERVED" && (
                    <button
                      onClick={() => setShowCancelModal(true)}
                      className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-xl text-xs font-semibold transition"
                    >
                      Cancel Reservation
                    </button>
                  )}
                  {["RESERVED", "CHECKED_IN"].includes(selectedRes.status) && (
                    <button
                      onClick={() => {
                        setReassignRoomId(selectedRes.room_id);
                        setShowReassignModal(true);
                      }}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-xl text-xs font-semibold transition flex items-center gap-1.5"
                    >
                      <ArrowRightLeft size={13} />
                      Reassign Room
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {selectedRes.status !== "CANCELLED" && (
                    <button
                      onClick={() => {
                        setPayAmount(selectedRes.balance_due.toString());
                        setShowPaymentModal(true);
                      }}
                      className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition flex items-center gap-1.5"
                    >
                      <CreditCard size={13} />
                      Record Payment
                    </button>
                  )}

                  {selectedRes.status === "RESERVED" && (
                    <button
                      onClick={() => handleCheckIn(selectedRes.id)}
                      disabled={actionLoading}
                      className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-emerald-900/30"
                    >
                      {actionLoading ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                      Check-In Guest
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 3: RECORD PAYMENT / DEPOSIT */}
      {/* ------------------------------------------------------------- */}
      {showPaymentModal && selectedRes && (
        <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md overflow-hidden shadow-2xl p-6">
            <h3 className="font-bold text-base text-white mb-1">Record Advance Deposit / Folio Payment</h3>
            <p className="text-xs text-slate-400 mb-4">
              Booking {selectedRes.booking_reference} • Current Balance Due: {formatCurrency(selectedRes.balance_due)}
            </p>

            <form onSubmit={handleRecordPayment} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Payment Amount (INR) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Payment Method *</label>
                <select
                  value={payMode}
                  onChange={(e) => setPayMode(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                >
                  <option value="UPI_QR">UPI QR Code</option>
                  <option value="CASH">Cash</option>
                  <option value="CREDIT_DEBIT_CARD">Credit / Debit Card</option>
                  <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Transaction Reference</label>
                <input
                  type="text"
                  placeholder="e.g. UTR / Transaction ID"
                  value={payRef}
                  onChange={(e) => setPayRef(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowPaymentModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 size={13} className="animate-spin" />}
                  Submit Payment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 4: CANCEL RESERVATION */}
      {/* ------------------------------------------------------------- */}
      {showCancelModal && selectedRes && (
        <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md overflow-hidden shadow-2xl p-6">
            <h3 className="font-bold text-base text-white mb-1">Cancel Reservation</h3>
            <p className="text-xs text-slate-400 mb-4">
              Booking {selectedRes.booking_reference} for {selectedRes.guest_name}
            </p>

            <form onSubmit={handleCancelReservation} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Cancellation Reason *</label>
                <textarea
                  required
                  rows={2}
                  placeholder="e.g. Guest requested cancellation due to travel delay"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Refund Amount (Max {formatCurrency(selectedRes.total_paid)})
                </label>
                <input
                  type="number"
                  step="0.01"
                  max={selectedRes.total_paid}
                  value={refundAmount}
                  onChange={(e) => setRefundAmount(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 size={13} className="animate-spin" />}
                  Confirm Cancellation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 5: REASSIGN ROOM */}
      {/* ------------------------------------------------------------- */}
      {showReassignModal && selectedRes && (
        <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md overflow-hidden shadow-2xl p-6">
            <h3 className="font-bold text-base text-white mb-1">Reassign Room</h3>
            <p className="text-xs text-slate-400 mb-4">
              Move {selectedRes.guest_name} from Room {selectedRes.room_number} to a different room
            </p>

            <form onSubmit={handleReassignRoom} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Select New Room *</label>
                <select
                  required
                  value={reassignRoomId}
                  onChange={(e) => setReassignRoomId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                >
                  {allRooms
                    .filter((r) => r.id !== selectedRes.room_id)
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        Room {r.room_number} — {r.room_type_name}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Reason for Reassignment</label>
                <input
                  type="text"
                  placeholder="e.g. Higher floor requested, AC repair in original room"
                  value={reassignReason}
                  onChange={(e) => setReassignReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-azure-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowReassignModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2 bg-azure-600 hover:bg-azure-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 size={13} className="animate-spin" />}
                  Confirm Reassignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
