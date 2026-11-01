"use client";

import React, { useEffect, useState } from "react";
import { apiFetch, apiFetchCached, invalidateApiCache } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/utils";
import {
  Sparkles, Plus, CheckCircle, Clock, CheckSquare,
  Square, ShieldCheck, XCircle, AlertCircle, RefreshCw, Loader2
} from "lucide-react";

interface HousekeepingTask {
  id: string;
  room_id: string;
  room_number: string;
  assigned_to_name?: string;
  status: string;
  priority: string;
  started_at?: string;
  completed_at?: string;
  notes?: string;
  checklists: { id: string; item_key: string; is_completed: boolean }[];
}

interface Room {
  id: string;
  room_number: string;
}

export default function HousekeepingPage() {
  const [tasks, setTasks] = useState<HousekeepingTask[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Active checklist modal
  const [activeTask, setActiveTask] = useState<HousekeepingTask | null>(null);

  // New task modal
  const [showNewTaskModal, setShowNewTaskModal] = useState(false);
  const [selectedRoomId, setSelectedRoomId] = useState("");
  const [taskPriority, setTaskPriority] = useState("NORMAL");
  const [taskNotes, setTaskNotes] = useState("");

  const fetchTasks = async (force = false) => {
    if (force) {
      invalidateApiCache("/operations/housekeeping/tasks");
      setRefreshing(true);
    } else if (tasks.length === 0) {
      setLoading(true);
    }
    try {
      const [tasksData, roomsData] = await Promise.all([
        apiFetchCached<HousekeepingTask[]>("/operations/housekeeping/tasks", {}, 20000),
        apiFetchCached<Room[]>("/rooms", {}, 60000),
      ]);
      setTasks(tasksData);
      setRooms(roomsData);
      if (roomsData.length > 0 && !selectedRoomId) setSelectedRoomId(roomsData[0].id);
    } catch (e: any) {
      console.error("Failed to load tasks", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const handleStartTask = async (taskId: string) => {
    // Optimistic UI update: instant 0ms status change
    const prevTasks = tasks;
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: "IN_PROGRESS" } : t))
    );
    if (activeTask && activeTask.id === taskId) {
      setActiveTask((prev) => (prev ? { ...prev, status: "IN_PROGRESS" } : null));
    }

    try {
      await apiFetch(`/operations/housekeeping/tasks/${taskId}/start`, { method: "PATCH" });
      invalidateApiCache("/operations/housekeeping/tasks");
    } catch (err: any) {
      setTasks(prevTasks);
      alert("Failed to start task: " + err.message);
    }
  };

  const handleToggleChecklist = async (taskId: string, itemKey: string, currentStatus: boolean) => {
    // Optimistic UI update: instant checkbox toggle without re-rendering or fetching
    const newStatus = !currentStatus;
    setActiveTask((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        checklists: prev.checklists.map((c) =>
          c.item_key === itemKey ? { ...c, is_completed: newStatus } : c
        ),
      };
    });

    setTasks((prev) =>
      prev.map((t) => {
        if (t.id !== taskId) return t;
        return {
          ...t,
          checklists: t.checklists.map((c) =>
            c.item_key === itemKey ? { ...c, is_completed: newStatus } : c
          ),
        };
      })
    );

    try {
      await apiFetch(`/operations/housekeeping/tasks/${taskId}/checklist`, {
        method: "PATCH",
        body: JSON.stringify({ item_key: itemKey, is_completed: newStatus }),
      });
      invalidateApiCache("/operations/housekeeping/tasks");
    } catch (err: any) {
      alert("Failed to update checklist item: " + err.message);
      fetchTasks(true);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    // Optimistic UI update
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: "INSPECTION_PENDING" } : t))
    );
    setActiveTask(null);

    try {
      await apiFetch(`/operations/housekeeping/tasks/${taskId}/complete`, { method: "PATCH" });
      invalidateApiCache("/operations/housekeeping/tasks");
    } catch (err: any) {
      alert("Failed to complete task: " + err.message);
      fetchTasks(true);
    }
  };

  const handleInspection = async (taskId: string, roomId: string, pass: boolean) => {
    // Optimistic UI update
    const newStatus = pass ? "READY" : "INSPECTION_FAILED";
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t))
    );

    try {
      await apiFetch("/operations/housekeeping/inspections", {
        method: "POST",
        body: JSON.stringify({
          task_id: taskId,
          room_id: roomId,
          status: pass ? "PASSED" : "FAILED",
          rejection_reason: pass ? null : "Cleaning standards not met on bed linens or bathroom",
        }),
      });
      invalidateApiCache("/operations/housekeeping/tasks");
      invalidateApiCache("/rooms");
    } catch (err: any) {
      alert("Failed to submit inspection: " + err.message);
      fetchTasks(true);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await apiFetch("/operations/housekeeping/tasks", {
        method: "POST",
        body: JSON.stringify({
          room_id: selectedRoomId,
          priority: taskPriority,
          notes: taskNotes,
        }),
      });
      setShowNewTaskModal(false);
      setTaskNotes("");
      fetchTasks(true);
    } catch (err: any) {
      alert("Failed to create task: " + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Housekeeping & Field Inspections</h1>
          <p className="text-xs text-slate-500">Mobile-friendly cleaning checklists, timestamps & supervisor sign-offs</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchTasks(true)}
            disabled={refreshing}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 shadow-sm disabled:opacity-60"
            title="Refresh tasks"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin text-azure-600" : ""} />
          </button>
          <button
            onClick={() => setShowNewTaskModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-azure-600 hover:bg-azure-700 text-white shadow-sm transition"
          >
            <Plus size={15} />
            <span>Assign Cleaning</span>
          </button>
        </div>
      </div>

      {/* Task Cards Board */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-xl border border-slate-200">
          <Sparkles size={32} className="mx-auto text-azure-500 mb-2" />
          <p className="text-sm font-semibold text-slate-700">No active housekeeping tasks pending.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => {
            const completedCount = task.checklists.filter((c) => c.is_completed).length;
            const totalChecklist = task.checklists.length;

            return (
              <div
                key={task.id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-slate-300 transition"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 flex flex-col items-center justify-center shrink-0 border border-slate-200">
                    <span className="text-[10px] uppercase font-bold text-slate-500">Room</span>
                    <span className="text-base font-extrabold text-slate-900 leading-none">
                      {task.room_number}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900">
                        Assigned: {task.assigned_to_name || "Unassigned"}
                      </span>
                      <span
                        className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase ${
                          task.priority === "URGENT" || task.priority === "HIGH"
                            ? "bg-rose-50 text-rose-700 border border-rose-200"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {task.priority}
                      </span>
                    </div>

                    <p className="text-xs text-slate-500 mt-0.5 italic">{task.notes || "Standard checkout cleaning"}</p>

                    <div className="mt-2 flex items-center gap-4 text-[11px] text-slate-500">
                      <span>Checklist: <strong className="text-slate-800">{completedCount}/{totalChecklist} completed</strong></span>
                      {task.started_at && (
                        <span>Started: {formatTime(task.started_at)}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                  {task.status === "PENDING" && (
                    <button
                      onClick={() => handleStartTask(task.id)}
                      className="px-3 py-1.5 rounded-lg bg-azure-600 hover:bg-azure-700 text-white text-xs font-semibold shadow-sm transition"
                    >
                      Start Cleaning
                    </button>
                  )}

                  {task.status === "IN_PROGRESS" && (
                    <button
                      onClick={() => setActiveTask(task)}
                      className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-sm transition flex items-center gap-1.5"
                    >
                      <CheckSquare size={14} />
                      <span>Open Checklist</span>
                    </button>
                  )}

                  {task.status === "INSPECTION_PENDING" && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-purple-700 bg-purple-50 border border-purple-200 font-semibold px-2 py-1 rounded-lg">
                        Supervisor Inspection
                      </span>
                      <button
                        onClick={() => handleInspection(task.id, task.room_id, true)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition flex items-center gap-1"
                      >
                        <ShieldCheck size={14} />
                        <span>Pass</span>
                      </button>
                      <button
                        onClick={() => handleInspection(task.id, task.room_id, false)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-sm transition flex items-center gap-1"
                      >
                        <XCircle size={14} />
                        <span>Reject</span>
                      </button>
                    </div>
                  )}

                  {task.status === "READY" && (
                    <span className="flex items-center gap-1 text-xs text-emerald-700 font-bold bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg">
                      <CheckCircle size={14} />
                      <span>Inspected & Ready</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* INTERACTIVE CHECKLIST MODAL */}
      {activeTask && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-1">
              Room {activeTask.room_number} — Cleaning Checklist
            </h2>
            <p className="text-xs text-slate-500 mb-4">Tap items as you complete each task</p>

            <div className="space-y-2.5 mb-6">
              {activeTask.checklists.map((c) => (
                <button
                  key={c.id}
                  onClick={() => handleToggleChecklist(activeTask.id, c.item_key, c.is_completed)}
                  className={`w-full text-left p-3 rounded-xl border flex items-center gap-3 transition ${
                    c.is_completed
                      ? "bg-emerald-50/70 border-emerald-200 text-slate-800"
                      : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {c.is_completed ? (
                    <CheckCircle size={18} className="text-emerald-600 shrink-0" />
                  ) : (
                    <Square size={18} className="text-slate-400 shrink-0" />
                  )}
                  <span className={`text-xs font-medium ${c.is_completed ? "line-through text-slate-500" : ""}`}>
                    {c.item_key}
                  </span>
                </button>
              ))}
            </div>

            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <button
                onClick={() => setActiveTask(null)}
                className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Close
              </button>
              <button
                onClick={() => handleCompleteTask(activeTask.id)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm flex items-center gap-1.5"
              >
                <CheckCircle size={15} />
                <span>Submit for Inspection</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NEW TASK MODAL */}
      {showNewTaskModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900 mb-4">Assign Housekeeping Task</h2>
            <form onSubmit={handleCreateTask} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Room</label>
                <select
                  value={selectedRoomId}
                  onChange={(e) => setSelectedRoomId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      Room {r.room_number}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Priority</label>
                <select
                  value={taskPriority}
                  onChange={(e) => setTaskPriority(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                >
                  <option value="NORMAL">Normal</option>
                  <option value="HIGH">High (Next Guest Imminent)</option>
                  <option value="URGENT">Urgent (VIP Arrival)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Special Instructions</label>
                <textarea
                  value={taskNotes}
                  onChange={(e) => setTaskNotes(e.target.value)}
                  placeholder="e.g. Extra pillows requested, replace shower curtain"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-azure-500"
                  rows={2}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowNewTaskModal(false)}
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
                  <span>{isSubmitting ? "Assigning..." : "Assign Task"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

