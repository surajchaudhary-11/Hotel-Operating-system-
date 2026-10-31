"use client";

import React, { useEffect, useState, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/context/auth-context";
import {
  Bot, Send, Sparkles, User, ShieldCheck, Database,
  ArrowRight, RefreshCw, MessageSquare, Trash2, Plus,
  AlertCircle, ChevronRight, CheckCircle2, Languages, ShieldAlert, X
} from "lucide-react";

interface ActionProposal {
  action_id: string;
  action_name: string;
  title: string;
  parameters: Record<string, any>;
  impact_summary: string;
  status: "pending_confirmation" | "executed" | "cancelled";
}

interface Message {
  id?: string;
  sender: "USER" | "ASSISTANT" | "TOOL";
  content: string;
  tool_calls?: string[];
  action_proposal?: ActionProposal | null;
  action_executed?: Record<string, any> | null;
  created_at?: string;
}

interface ConversationItem {
  id: string;
  title: string;
  created_at: string;
}

const CATEGORIZED_PROMPTS = [
  {
    category: "Operations",
    prompts: [
      "How many rooms are vacant today?",
      "Show me today's check-ins and check-outs",
      "Which rooms are waiting for housekeeping?",
    ]
  },
  {
    category: "Financials",
    prompts: [
      "What was today's room revenue and expenses?",
      "Show in-house stays with outstanding balance dues",
    ]
  },
  {
    category: "Maintenance & Stock",
    prompts: [
      "Show pending maintenance repair requests",
      "Which inventory items are running low?",
    ]
  },
  {
    category: "Actions & Hindi",
    prompts: [
      "Create a housekeeping task for Room 204",
      "आज कितने कमरे खाली हैं?",
    ]
  }
];

export default function AIAssistantPage() {
  const { activeHotel } = useAuth();
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ASSISTANT",
      content:
        "Hello! I'm your **HotelOS AI Operations Assistant**.\n\nI can help you understand your hotel's live operations, bookings, housekeeping, inventory, and financial performance using real verified database records. What would you like to know?",
      tool_calls: ["system_ready"],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Load conversation list on mount
  useEffect(() => {
    loadConversations();
  }, [activeHotel?.hotel_id]);

  const loadConversations = async () => {
    try {
      const res = await apiFetch<ConversationItem[]>("/ai/conversations");
      setConversations(res || []);
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  };

  const selectConversation = async (convId: string) => {
    setActiveConvId(convId);
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiFetch<any[]>(`/ai/conversations/${convId}/messages`);
      if (res && res.length > 0) {
        setMessages(
          res.map((m) => ({
            id: m.id,
            sender: m.sender,
            content: m.content,
            tool_calls: m.tool_calls,
            created_at: m.created_at,
          }))
        );
      }
    } catch (err: any) {
      setErrorMsg("Failed to load message history for this conversation.");
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    setActiveConvId(null);
    setErrorMsg(null);
    setMessages([
      {
        sender: "ASSISTANT",
        content:
          "Hello! I'm your **HotelOS AI Operations Assistant**.\n\nI can help you understand your hotel's live operations, bookings, housekeeping, inventory, and financial performance. What would you like to know?",
        tool_calls: ["system_ready"],
      },
    ]);
  };

  const deleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiFetch(`/ai/conversations/${convId}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        startNewConversation();
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  const handleSendMessage = async (
    text: string,
    actionPayload?: {
      confirm_action_id?: string;
      action_name?: string;
      action_parameters?: Record<string, any>;
      cancel_action_id?: string;
    }
  ) => {
    if (!text.trim() || loading) return;

    const userMessage: Message = { sender: "USER", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await apiFetch<any>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          conversation_id: activeConvId,
          confirm_action_id: actionPayload?.confirm_action_id,
          action_name: actionPayload?.action_name,
          action_parameters: actionPayload?.action_parameters,
          cancel_action_id: actionPayload?.cancel_action_id,
        }),
      });

      if (res.conversation_id && !activeConvId) {
        setActiveConvId(res.conversation_id);
        loadConversations();
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: "ASSISTANT",
          content: res.message,
          tool_calls: res.tools_executed,
          action_proposal: res.action_proposal,
          action_executed: res.action_executed,
          created_at: res.timestamp,
        },
      ]);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to reach AI assistant service.");
      setMessages((prev) => [
        ...prev,
        {
          sender: "ASSISTANT",
          content: "Sorry, I encountered an error: " + (err.message || "Service temporarily unavailable. Please retry."),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmAction = (proposal: ActionProposal) => {
    handleSendMessage(`Confirm ${proposal.title}`, {
      confirm_action_id: proposal.action_id,
      action_name: proposal.action_name,
      action_parameters: proposal.parameters,
    });
  };

  const handleCancelAction = (proposal: ActionProposal) => {
    handleSendMessage(`Cancel action`, {
      cancel_action_id: proposal.action_id,
    });
  };

  return (
    <div className="h-[calc(100vh-6rem)] flex bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Sidebar: Conversation History */}
      <div
        className={`${
          sidebarOpen ? "w-64" : "w-0 -ml-64"
        } transition-all duration-300 border-r border-slate-200 bg-slate-50 flex flex-col shrink-0 overflow-hidden hidden md:flex`}
      >
        <div className="p-3 border-b border-slate-200 flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
            <MessageSquare size={14} className="text-azure-600" />
            History
          </span>
          <button
            onClick={startNewConversation}
            className="flex items-center gap-1 px-2 py-1 bg-azure-600 hover:bg-azure-700 text-white rounded-lg text-xs font-medium shadow-sm transition"
          >
            <Plus size={13} />
            New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <p className="text-[11px] text-slate-400 text-center py-6">No previous conversations</p>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => selectConversation(c.id)}
                className={`group px-3 py-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition ${
                  activeConvId === c.id
                    ? "bg-white font-semibold text-azure-900 border border-azure-200 shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                <span className="truncate max-w-[160px]">{c.title || "Untitled Session"}</span>
                <button
                  onClick={(e) => deleteConversation(c.id, e)}
                  title="Delete conversation"
                  className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 transition"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Security Assurance Footer */}
        <div className="p-3 bg-slate-100/80 border-t border-slate-200 text-[10px] text-slate-500 flex items-center gap-2">
          <ShieldCheck size={14} className="text-emerald-600 shrink-0" />
          <span>Role-restricted • Zero SQL • Multi-tenant safe</span>
        </div>
      </div>

      {/* Main Chat Panel */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-azure-600 to-tyrian-800 flex items-center justify-center text-white shadow-md shadow-azure-900/20">
              <Bot size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold text-slate-900">HotelOS Intelligence Assistant</h1>
                <span className="text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  Live Tools
                </span>
                {activeHotel?.role && (
                  <span className="text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200 px-1.5 py-0.5 rounded">
                    Role: {activeHotel.role}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500">
                Connected to {activeHotel?.hotel_name || "your hotel"} • English & Hindi natural language supported
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={startNewConversation}
              className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 text-xs font-medium flex items-center gap-1.5 transition shadow-2xs"
            >
              <RefreshCw size={13} />
              Reset Chat
            </button>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-slate-50/40">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.sender === "USER" ? "justify-end" : "justify-start"}`}
            >
              {msg.sender === "ASSISTANT" && (
                <div className="w-8 h-8 rounded-lg bg-azure-600 text-white flex items-center justify-center shrink-0 text-xs shadow-sm mt-0.5">
                  <Bot size={16} />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed space-y-2 shadow-sm ${
                  msg.sender === "USER"
                    ? "bg-slate-900 text-white rounded-tr-none font-medium"
                    : "bg-white border border-slate-200 text-slate-800 rounded-tl-none"
                }`}
              >
                {/* Executed Tools Pill */}
                {msg.tool_calls && msg.tool_calls.length > 0 && msg.tool_calls[0] !== "system_ready" && (
                  <div className="flex flex-wrap items-center gap-1.5 pb-2 border-b border-slate-100">
                    <Database size={12} className="text-azure-600" />
                    <span className="text-[10px] font-mono font-semibold text-slate-400">Tools:</span>
                    {msg.tool_calls.map((t, tidx) => (
                      <span
                        key={tidx}
                        className="text-[9px] font-mono bg-azure-50 text-azure-700 px-2 py-0.5 rounded border border-azure-200/70"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}

                <div className="whitespace-pre-line prose prose-xs max-w-none">
                  {msg.content}
                </div>

                {/* Consequential Action Proposal Card */}
                {msg.action_proposal && (
                  <div className="mt-3 p-3.5 bg-amber-50/70 border border-amber-200/90 rounded-xl space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldAlert size={16} className="text-amber-600" />
                        <span className="font-bold text-xs text-amber-950">
                          {msg.action_proposal.title}
                        </span>
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        msg.action_proposal.status === "executed"
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                          : msg.action_proposal.status === "cancelled"
                          ? "bg-slate-200 text-slate-700 border border-slate-300"
                          : "bg-amber-100 text-amber-800 border border-amber-300 animate-pulse"
                      }`}>
                        {msg.action_proposal.status === "executed"
                          ? "✓ Executed"
                          : msg.action_proposal.status === "cancelled"
                          ? "✕ Cancelled"
                          : "Confirmation Required"}
                      </span>
                    </div>

                    <p className="text-[11px] text-amber-950/80">
                      {msg.action_proposal.impact_summary}
                    </p>

                    {/* Parameters Grid */}
                    <div className="bg-white/90 rounded-lg p-2.5 border border-amber-200/60 text-[11px] space-y-1">
                      {Object.entries(msg.action_proposal.parameters).map(([key, val]) => (
                        <div key={key} className="flex justify-between items-center text-slate-700">
                          <span className="font-mono text-[10px] text-slate-500 capitalize">{key.replace('_', ' ')}:</span>
                          <span className="font-semibold text-slate-900">{String(val)}</span>
                        </div>
                      ))}
                    </div>

                    {msg.action_proposal.status === "pending_confirmation" && (
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => handleConfirmAction(msg.action_proposal!)}
                          disabled={loading}
                          className="flex-1 py-1.5 px-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition"
                        >
                          <CheckCircle2 size={13} />
                          Confirm & Execute
                        </button>
                        <button
                          onClick={() => handleCancelAction(msg.action_proposal!)}
                          disabled={loading}
                          className="py-1.5 px-3 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {msg.sender === "USER" && (
                <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center shrink-0 text-xs shadow-sm mt-0.5">
                  <User size={16} />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-azure-600 text-white flex items-center justify-center shrink-0 text-xs shadow-sm">
                <Bot size={16} />
              </div>
              <div className="px-4 py-3 rounded-2xl bg-white border border-slate-200 text-xs text-slate-600 flex items-center gap-2 shadow-sm">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce"></div>
                  <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce [animation-delay:0.2s]"></div>
                  <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce [animation-delay:0.4s]"></div>
                </div>
                <span className="font-medium text-slate-600 pl-1">Executing backend operational tools...</span>
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle size={15} />
                <span>{errorMsg}</span>
              </div>
              <button
                onClick={() => handleSendMessage(input)}
                className="text-xs font-semibold text-rose-800 underline hover:no-underline"
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Categorized Suggested Prompt Pills */}
        <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 flex items-center gap-2 overflow-x-auto no-scrollbar shrink-0">
          <Sparkles size={14} className="text-azure-600 shrink-0" />
          {CATEGORIZED_PROMPTS.map((group, gidx) => (
            <div key={gidx} className="flex items-center gap-1.5 shrink-0">
              {group.prompts.map((p, pidx) => (
                <button
                  key={pidx}
                  onClick={() => handleSendMessage(p)}
                  disabled={loading}
                  className="text-[11px] bg-white hover:bg-azure-50 hover:text-azure-700 border border-slate-200 px-3 py-1 rounded-full text-slate-700 whitespace-nowrap transition shadow-2xs disabled:opacity-50"
                >
                  {p}
                </button>
              ))}
            </div>
          ))}
        </div>

        {/* Message Input Footer */}
        <div className="p-4 border-t border-slate-200 bg-white shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(input);
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about live room occupancy, bookings, housekeeping, inventory or revenue..."
              disabled={loading}
              className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-azure-500/20 focus:border-azure-500 transition shadow-xs"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="px-4 py-2.5 rounded-xl bg-azure-600 hover:bg-azure-700 text-white shadow-sm disabled:opacity-50 transition flex items-center gap-1.5 text-xs font-medium shrink-0"
            >
              <Send size={14} />
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
