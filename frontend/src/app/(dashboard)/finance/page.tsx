"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  TrendingUp, Plus, DollarSign, Calculator, RefreshCw,
  FileText, CheckCircle2, AlertCircle, ArrowUpRight, HelpCircle
} from "lucide-react";

interface Expense {
  id: string;
  category_name: string;
  room_number?: string;
  amount: number;
  expense_date: string;
  payment_method: string;
  description: string;
  is_allocated: boolean;
}

interface ExpenseCategory {
  id: string;
  name: string;
}

interface RoomProfitabilityItem {
  room_id: string;
  room_number: string;
  room_type: string;
  available_nights: number;
  occupied_nights: number;
  occupancy_rate: number;
  earned_revenue: number;
  direct_maintenance_expenses: number;
  allocated_expenses: number;
  operating_contribution: number;
  adr: number;
  revpar: number;
}

interface Room {
  id: string;
  room_number: string;
}

export default function FinancePage() {
  const [summary, setSummary] = useState<any>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [profitability, setProfitability] = useState<RoomProfitabilityItem[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);

  // Record Expense Modal
  const [showExpenseModal, setShowExpenseModal] = useState(false);
  const [expCategory, setExpCategory] = useState("");
  const [expAmount, setExpAmount] = useState("");
  const [expMethod, setExpMethod] = useState("UPI");
  const [expDesc, setExpDesc] = useState("");
  const [expRoomId, setExpRoomId] = useState("");

  // Scenario Calculator
  const [simPrice, setSimPrice] = useState("4500");
  const [simOccupancy, setSimOccupancy] = useState("75");
  const [simMaintenance, setSimMaintenance] = useState("3000");
  const [simUtility, setSimUtility] = useState("4000");
  const [simulationResult, setSimulationResult] = useState<any>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [sumData, expData, catData, profData, roomsData] = await Promise.all([
        apiFetch<any>("/finance/summary"),
        apiFetch<Expense[]>("/finance/expenses"),
        apiFetch<ExpenseCategory[]>("/finance/categories"),
        apiFetch<RoomProfitabilityItem[]>("/finance/room-profitability"),
        apiFetch<Room[]>("/rooms"),
      ]);
      setSummary(sumData);
      setExpenses(expData);
      setCategories(catData);
      setProfitability(profData);
      setRooms(roomsData);
      if (catData.length > 0 && !expCategory) setExpCategory(catData[0].id);
    } catch (e: any) {
      console.error("Error loading finance data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Run scenario simulation
  useEffect(() => {
    const runSimulation = async () => {
      try {
        const res = await apiFetch<any>("/finance/scenario-simulation", {
          method: "POST",
          body: JSON.stringify({
            base_price: parseFloat(simPrice) || 0,
            expected_occupancy_rate: parseFloat(simOccupancy) || 0,
            estimated_maintenance_monthly: parseFloat(simMaintenance) || 0,
            estimated_allocated_utility_monthly: parseFloat(simUtility) || 0,
            days_in_month: 30,
          }),
        });
        setSimulationResult(res);
      } catch (e) {
        console.error(e);
      }
    };
    runSimulation();
  }, [simPrice, simOccupancy, simMaintenance, simUtility]);

  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/finance/expenses", {
        method: "POST",
        body: JSON.stringify({
          category_id: expCategory,
          amount: parseFloat(expAmount) || 0,
          payment_method: expMethod,
          description: expDesc,
          room_id: expRoomId || null,
        }),
      });
      setShowExpenseModal(false);
      setExpAmount("");
      setExpDesc("");
      fetchData();
    } catch (err: any) {
      alert("Failed to log expense: " + err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Financials & Room Profitability</h1>
          <p className="text-xs text-slate-500">USALI Operating Contribution, Accrual Revenue vs. Cash Flow & Scenario Modeling</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setShowExpenseModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Record Expense</span>
          </button>
        </div>
      </div>

      {/* Top Financial Breakdown Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 uppercase">Today&apos;s Earned Revenue (Accrual)</span>
          <p className="text-2xl font-bold text-slate-900 mt-1">{formatCurrency(summary?.today_revenue ?? 0)}</p>
          <p className="text-[11px] text-slate-400 mt-2">Nightly room tariff earned by stays</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 uppercase">Today&apos;s Cash Collections</span>
          <p className="text-2xl font-bold text-emerald-600 mt-1">{formatCurrency(summary?.today_collections ?? 0)}</p>
          <p className="text-[11px] text-slate-400 mt-2">Cash, UPI & card inflows</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 uppercase">Today&apos;s Operating Expenses</span>
          <p className="text-2xl font-bold text-rose-600 mt-1">{formatCurrency(summary?.today_expenses ?? 0)}</p>
          <p className="text-[11px] text-slate-400 mt-2">Direct room & shared facility costs</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-500 uppercase">Operating Contribution (GOP)</span>
          <p className="text-2xl font-bold text-tyrian-700 mt-1">{formatCurrency(summary?.today_operating_contribution ?? 0)}</p>
          <p className="text-[11px] text-slate-400 mt-2">USALI standard: Revenue - Operating Costs</p>
        </div>
      </div>

      {/* ROOM-WISE PROFITABILITY TABLE */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Room-Wise Financial Contribution Matrix</h2>
            <p className="text-xs text-slate-500">ADR, RevPAR, Direct Expenses & Allocated Costs per Room</p>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
            <HelpCircle size={13} className="text-slate-400" />
            <span>USALI Operating Contribution (Not Net Profit)</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Room</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Occupancy</th>
                <th className="py-3 px-4">Earned Revenue</th>
                <th className="py-3 px-4">Direct Repairs</th>
                <th className="py-3 px-4">Allocated Share</th>
                <th className="py-3 px-4">Operating Contribution</th>
                <th className="py-3 px-4">ADR</th>
                <th className="py-3 px-4">RevPAR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {profitability.map((item) => (
                <tr key={item.room_id} className="hover:bg-slate-50 transition">
                  <td className="py-3 px-4 font-bold text-slate-900">Room {item.room_number}</td>
                  <td className="py-3 px-4 text-slate-500">{item.room_type}</td>
                  <td className="py-3 px-4">
                    <span className="font-semibold text-slate-800">{item.occupancy_rate}%</span>
                    <span className="text-[10px] text-slate-400 block">({item.occupied_nights}/{item.available_nights} nights)</span>
                  </td>
                  <td className="py-3 px-4 font-bold text-azure-700">{formatCurrency(item.earned_revenue)}</td>
                  <td className="py-3 px-4 text-rose-600 font-medium">{formatCurrency(item.direct_maintenance_expenses)}</td>
                  <td className="py-3 px-4 text-slate-500">{formatCurrency(item.allocated_expenses)}</td>
                  <td className="py-3 px-4 font-extrabold text-tyrian-700">{formatCurrency(item.operating_contribution)}</td>
                  <td className="py-3 px-4 font-medium">{formatCurrency(item.adr)}</td>
                  <td className="py-3 px-4 font-medium">{formatCurrency(item.revpar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* SCENARIO SIMULATION CALCULATOR */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-azure-50 text-azure-600 flex items-center justify-center">
            <Calculator size={18} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Scenario Profitability Calculator</h2>
            <p className="text-xs text-slate-500">Simulate room pricing, occupancy targets, maintenance & power costs</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-50 border border-slate-200 mb-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Room Base Price (₹)</label>
            <input
              type="number"
              value={simPrice}
              onChange={(e) => setSimPrice(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-azure-500 font-semibold"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Expected Occupancy (%)</label>
            <input
              type="number"
              min={0}
              max={100}
              value={simOccupancy}
              onChange={(e) => setSimOccupancy(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-azure-500 font-semibold"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Estimated Maintenance (₹/mo)</label>
            <input
              type="number"
              value={simMaintenance}
              onChange={(e) => setSimMaintenance(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-azure-500 font-semibold"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Allocated Power & Utility (₹/mo)</label>
            <input
              type="number"
              value={simUtility}
              onChange={(e) => setSimUtility(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-azure-500 font-semibold"
            />
          </div>
        </div>

        {simulationResult && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
            <div className="p-3 bg-azure-50 border border-azure-100 rounded-xl">
              <span className="text-[10px] font-bold text-azure-700 uppercase">Simulated Monthly Revenue</span>
              <p className="text-lg font-bold text-azure-900 mt-0.5">{formatCurrency(simulationResult.simulated_monthly_revenue)}</p>
            </div>
            <div className="p-3 bg-rose-50 border border-rose-100 rounded-xl">
              <span className="text-[10px] font-bold text-rose-700 uppercase">Simulated Operating Costs</span>
              <p className="text-lg font-bold text-rose-900 mt-0.5">{formatCurrency(simulationResult.simulated_operating_expenses)}</p>
            </div>
            <div className="p-3 bg-tyrian-50 border border-tyrian-100 rounded-xl">
              <span className="text-[10px] font-bold text-tyrian-700 uppercase">Simulated Operating Contribution</span>
              <p className="text-lg font-bold text-tyrian-900 mt-0.5">{formatCurrency(simulationResult.simulated_operating_contribution)}</p>
            </div>
            <div className="p-3 bg-slate-100 border border-slate-200 rounded-xl">
              <span className="text-[10px] font-bold text-slate-700 uppercase">Simulated RevPAR</span>
              <p className="text-lg font-bold text-slate-900 mt-0.5">{formatCurrency(simulationResult.simulated_revpar)}</p>
            </div>
          </div>
        )}
      </div>

      {/* RECORD EXPENSE MODAL */}
      {showExpenseModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Record Operating Expense</h2>
            <form onSubmit={handleCreateExpense} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Expense Category</label>
                <select
                  value={expCategory}
                  onChange={(e) => setExpCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Amount (₹)</label>
                <input
                  type="number"
                  required
                  value={expAmount}
                  onChange={(e) => setExpAmount(e.target.value)}
                  placeholder="e.g. 2500"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Method</label>
                <select
                  value={expMethod}
                  onChange={(e) => setExpMethod(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="UPI">UPI</option>
                  <option value="CASH">Cash</option>
                  <option value="NEFT_RTGS">Bank Transfer (NEFT/RTGS)</option>
                  <option value="CARD">Debit / Credit Card</option>
                  <option value="CREDIT_VENDOR">Credit Vendor Ledger</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Assign Direct to Room (Optional)</label>
                <select
                  value={expRoomId}
                  onChange={(e) => setExpRoomId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="">Property-Wide Shared Operating Expense</option>
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>Direct to Room {r.room_number}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Expense Description / Invoice Notes</label>
                <textarea
                  required
                  value={expDesc}
                  onChange={(e) => setExpDesc(e.target.value)}
                  placeholder="e.g. Purchased water bottles and coffee sachets for guest amenities"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500"
                  rows={2}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowExpenseModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-azure-600 hover:bg-azure-700 text-white rounded-lg shadow-sm"
                >
                  Save Expense
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

