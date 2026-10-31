"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { apiFetch } from "@/lib/api";
import {
  Settings, Building2, Users, ShieldCheck, Clock,
  Save, Plus, RefreshCw, CheckCircle2, UserCheck
} from "lucide-react";

interface Member {
  membership_id: string;
  user_id: string;
  full_name: string;
  email: string;
  phone_number?: string;
  role: string;
  joined_at: string;
}

export default function SettingsPage() {
  const { activeHotel, refreshUserData } = useAuth();
  const [hotel, setHotel] = useState<any>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);

  // Profile Form
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [checkInTime, setCheckInTime] = useState("12:00");
  const [checkOutTime, setCheckOutTime] = useState("11:00");
  const [savingProfile, setSavingProfile] = useState(false);

  // Add Member Modal
  const [showAddMember, setShowAddMember] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("RECEPTIONIST");

  const fetchData = async () => {
    if (!activeHotel) return;
    setLoading(true);
    try {
      const [hData, mData] = await Promise.all([
        apiFetch<any>(`/hotels/${activeHotel.hotel_id}`),
        apiFetch<Member[]>(`/hotels/${activeHotel.hotel_id}/members`),
      ]);
      setHotel(hData);
      setMembers(mData);
      setName(hData.name);
      setPhone(hData.phone);
      setEmail(hData.email);
      setCheckInTime(hData.check_in_time);
      setCheckOutTime(hData.check_out_time);
    } catch (e: any) {
      console.error("Error loading settings", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeHotel]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeHotel) return;
    setSavingProfile(true);
    try {
      await apiFetch(`/hotels/${activeHotel.hotel_id}`, {
        method: "PUT",
        body: JSON.stringify({
          name,
          phone,
          email,
          check_in_time: checkInTime,
          check_out_time: checkOutTime,
        }),
      });
      await refreshUserData();
      alert("Property settings saved successfully!");
    } catch (err: any) {
      alert("Failed to save profile: " + err.message);
    } finally {
      setSavingProfile(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeHotel) return;
    try {
      await apiFetch(`/hotels/${activeHotel.hotel_id}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_email: inviteEmail,
          role: inviteRole,
        }),
      });
      setShowAddMember(false);
      setInviteEmail("");
      fetchData();
      alert(`User granted ${inviteRole} role in this property!`);
    } catch (err: any) {
      alert("Failed to add member: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Property Settings & Team Permissions</h1>
        <p className="text-xs text-slate-500">Hotel operational policies, check-in timings, staff accounts & access control</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Building2 size={18} className="text-azure-600" />
            <h2 className="text-sm font-bold text-slate-900">Hotel Profile & Operating Policies</h2>
          </div>

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Hotel Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Official Contact Phone</label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Official Hotel Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Standard Check-In Time</label>
                <input
                  type="time"
                  value={checkInTime}
                  onChange={(e) => setCheckInTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Standard Check-Out Time</label>
                <input
                  type="time"
                  value={checkOutTime}
                  onChange={(e) => setCheckOutTime(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-1 text-xs text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-200">
              <div>
                <span className="font-semibold text-slate-700 block">Timezone:</span>
                <span>Asia/Kolkata (IST, UTC+5:30)</span>
              </div>
              <div>
                <span className="font-semibold text-slate-700 block">Operating Currency:</span>
                <span>Indian Rupee (INR, ₹)</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="px-4 py-2.5 text-xs font-semibold rounded-xl bg-azure-600 hover:bg-azure-700 text-white shadow-sm flex items-center gap-1.5 transition disabled:opacity-50"
            >
              <Save size={14} />
              <span>{savingProfile ? "Saving Changes..." : "Save Property Settings"}</span>
            </button>
          </form>
        </div>

        {/* Security & Indian DPDP Act Badge (1 col) */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck size={20} className="text-emerald-600" />
              <h2 className="text-sm font-bold text-slate-900">Security & DPDP Compliance</h2>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              HotelOS is architected for strict multi-tenant boundary isolation and adherence to India&apos;s{" "}
              <strong>Digital Personal Data Protection Act 2023</strong>.
            </p>

            <ul className="mt-4 space-y-2 text-xs text-slate-600">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                <span>Zero raw Aadhaar storage — strictly masked last 4 digits</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                <span>Tenant isolation on database sessions & API dependencies</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                <span>Zero arbitrary SQL AI queries — verified backend tools only</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                <span>Automatic 30-day purge for temporary guest identity documents</span>
              </li>
            </ul>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-100 text-[11px] text-slate-400">
            HotelOS Core Engine • Version 1.0.0 Production Release
          </div>
        </div>
      </div>

      {/* TEAM MEMBERS & ROLE-BASED ACCESS */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Hotel Staff & Memberships</h2>
            <p className="text-xs text-slate-500">Assigned employee roles across Front Desk, Housekeeping, Maintenance & Finance</p>
          </div>
          <button
            onClick={() => setShowAddMember(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={14} />
            <span>Add Member</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Staff Member</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Contact</th>
                <th className="py-3 px-4">Assigned Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {members.map((m) => (
                <tr key={m.membership_id} className="hover:bg-slate-50 transition">
                  <td className="py-3 px-4 font-bold text-slate-900">{m.full_name}</td>
                  <td className="py-3 px-4 text-slate-600">{m.email}</td>
                  <td className="py-3 px-4 font-mono text-slate-500">{m.phone_number || "-"}</td>
                  <td className="py-3 px-4">
                    <span className="text-[10px] font-bold bg-slate-100 text-slate-800 border border-slate-200 px-2.5 py-0.5 rounded-full uppercase">
                      {m.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ADD MEMBER MODAL */}
      {showAddMember && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Grant Hotel Membership</h2>
            <form onSubmit={handleAddMember} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">User Email Address</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="e.g. employee@hotel.com"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Role / Department</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="MANAGER">Manager (Operations, Audits, Approvals)</option>
                  <option value="RECEPTIONIST">Receptionist (Check-in, Check-out, Stays)</option>
                  <option value="HOUSEKEEPING">Housekeeping (Room Cleaning, Inspections)</option>
                  <option value="MAINTENANCE">Maintenance (Appliance Repairs, Tickets)</option>
                  <option value="ACCOUNTANT">Accountant (Revenue, Expenses, P&L)</option>
                  <option value="OWNER">Owner (Full Property Access)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddMember(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Add Member
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

