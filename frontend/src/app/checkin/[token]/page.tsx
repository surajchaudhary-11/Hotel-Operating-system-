"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Building2, CheckCircle2, ShieldCheck, UserCheck, ArrowRight } from "lucide-react";

export default function GuestDigitalCheckInPage() {
  const params = useParams();
  const token = params.token as string;

  const [details, setDetails] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [idType, setIdType] = useState("DRIVING_LICENSE");
  const [rawIdNumber, setRawIdNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) return;
    const fetchStay = async () => {
      try {
        const data = await apiFetch<any>(`/guests/digital-checkin/${token}`);
        setDetails(data);
        setFullName(data.guest_name || "");
        setPhone(data.guest_phone || "");
      } catch (err: any) {
        setError(err.message || "Invalid or expired check-in link");
      } finally {
        setLoading(false);
      }
    };
    fetchStay();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch(`/guests/digital-checkin/${token}/submit`, {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          phone,
          email: email || null,
          city: city || null,
          state: state || null,
          id_type: idType,
          id_number_masked: rawIdNumber, // Server enforces last 4 digits masking
        }),
      });
      setSuccess(true);
    } catch (err: any) {
      alert("Submission failed: " + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="text-white text-xs animate-pulse">Loading secure check-in portal...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl p-8 max-w-md w-full text-center shadow-2xl">
          <h1 className="text-base font-bold text-slate-900 mb-2">Check-In Link Expired</h1>
          <p className="text-xs text-slate-500 mb-4">{error}</p>
          <p className="text-[11px] text-slate-400">Please contact the hotel front desk upon arrival for room allocation.</p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl p-8 max-w-md w-full text-center shadow-2xl space-y-4">
          <div className="w-14 h-14 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-200">
            <CheckCircle2 size={32} />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Pre-Registration Complete!</h1>
          <p className="text-xs text-slate-600">
            Thank you, <strong className="text-slate-900">{fullName}</strong>. Your arrival details have been verified for Room{" "}
            <strong>{details?.room_number}</strong>.
          </p>
          <div className="p-3 bg-slate-50 rounded-xl text-xs text-slate-500 border border-slate-200">
            <p>Please present your physical photo ID card at the reception to receive your contactless room key.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 py-10 px-4 flex items-center justify-center">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl p-6 sm:p-8 border border-slate-100">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-azure-50 text-azure-600 flex items-center justify-center border border-azure-200 font-bold text-xl shrink-0">
            H
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Digital Guest Self Check-In</h1>
            <p className="text-xs text-slate-500">
              Allocated Room: <strong className="text-azure-700">Room {details?.room_number}</strong>
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Primary Guest Full Name</label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
              <input
                type="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">City</label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Varanasi"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">State / Province</label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Uttar Pradesh"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
              <ShieldCheck size={15} className="text-emerald-600" />
              <span>Identity Verification (Indian DPDP Act Compliant)</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Government ID Type</label>
                <select
                  value={idType}
                  onChange={(e) => setIdType(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none"
                >
                  <option value="DRIVING_LICENSE">Driving License</option>
                  <option value="PASSPORT">Passport</option>
                  <option value="VOTER_ID">Voter ID Card</option>
                  <option value="AADHAAR_MASKED">Aadhaar (Last 4 Digits)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">ID Document Number</label>
                <input
                  type="text"
                  required
                  value={rawIdNumber}
                  onChange={(e) => setRawIdNumber(e.target.value)}
                  placeholder="e.g. DL-04-2022-XXXX"
                  className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none"
                />
              </div>
            </div>
            <p className="text-[10px] text-slate-400 italic">
              *HotelOS stores masked identity numbers to protect your privacy under India&apos;s Digital Personal Data Protection Act 2023.
            </p>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-4 py-3 rounded-xl bg-azure-600 hover:bg-azure-700 text-white font-semibold text-xs shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <span>{submitting ? "Submitting..." : "Submit Pre-Registration"}</span>
            <ArrowRight size={15} />
          </button>
        </form>
      </div>
    </div>
  );
}

