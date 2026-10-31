"use client";

import React, { useState, useRef, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  Bot, Sparkles, X, Send, Trash2, Maximize2, ShieldCheck,
  ChevronDown, ArrowRight, CornerDownLeft, ShieldAlert, CheckCircle2
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
  sender: "USER" | "ASSISTANT";
  content: string;
  tool_calls?: string[];
  action_proposal?: ActionProposal | null;
  action_executed?: Record<string, any> | null;
  created_at?: string;
}

const QUICK_QUESTIONS = [
  "How many rooms are vacant?",
  "What is today's revenue?",
  "Show pending maintenance",
  "आज कितने कमरे खाली हैं?",
];

export function AIFloatingAssistant() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ASSISTANT",
      content:
        "Hello! I'm your **HotelOS Operations Assistant**.\n\nAsk me about room occupancy, check-ins, housekeeping, inventory, or today's revenue.",
      tool_calls: ["system_ready"]
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // If already on the dedicated /ai page, don't show the floating widget
  if (pathname === "/ai") {
    return null;
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, loading, isOpen]);

  const handleSend = async (
    text: string,
    actionPayload?: {
      confirm_action_id?: string;
      action_name?: string;
      action_parameters?: Record<string, any>;
      cancel_action_id?: string;
    }
  ) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { sender: "USER", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch<any>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          confirm_action_id: actionPayload?.confirm_action_id,
          action_name: actionPayload?.action_name,
          action_parameters: actionPayload?.action_parameters,
          cancel_action_id: actionPayload?.cancel_action_id,
        })
      });

      if (res.conversation_id && !conversationId) {
        setConversationId(res.conversation_id);
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: "ASSISTANT",
          content: res.message,
          tool_calls: res.tools_executed,
          action_proposal: res.action_proposal,
          action_executed: res.action_executed,
          created_at: res.timestamp
        }
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "ASSISTANT",
          content: "Sorry, I encountered an error: " + (err.message || "Unable to reach server")
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmAction = (proposal: ActionProposal) => {
    handleSend(`Confirm ${proposal.title}`, {
      confirm_action_id: proposal.action_id,
      action_name: proposal.action_name,
      action_parameters: proposal.parameters
    });
  };

  const handleCancelAction = (proposal: ActionProposal) => {
    handleSend(`Cancel action`, {
      cancel_action_id: proposal.action_id
    });
  };

  const handleClear = () => {
    setMessages([
      {
        sender: "ASSISTANT",
        content: "Conversation cleared. How can I help with hotel operations?",
        tool_calls: ["system_ready"]
      }
    ]);
    setConversationId(null);
  };

  return (
    <>
      {/* Floating Toggle Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 bg-gradient-to-r from-azure-600 to-tyrian-800 text-white rounded-full shadow-lg shadow-azure-950/20 hover:shadow-xl hover:scale-105 transition-all duration-200 group border border-white/20"
          aria-label="Open AI Assistant"
        >
          <div className="relative">
            <Bot size={20} className="animate-pulse" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2 border-azure-700"></span>
          </div>
          <span className="font-medium text-sm pr-1">Ask HotelOS</span>
          <Sparkles size={15} className="text-amber-300 opacity-80 group-hover:rotate-12 transition-transform" />
        </button>
      )}

      {/* Floating Assistant Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-[92vw] sm:w-[400px] h-[560px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 duration-200">
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-slate-900 via-tyrian-950 to-slate-900 text-white flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-azure-600 flex items-center justify-center text-white shadow">
                <Bot size={18} />
              </div>
              <div>
                <h3 className="text-xs font-semibold tracking-wide flex items-center gap-1.5">
                  HotelOS Operations Assistant
                </h3>
                <p className="text-[10px] text-slate-300 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping"></span>
                  Grounded in Live Property DB
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleClear}
                title="Clear Chat"
                className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-white/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
              <Link
                href="/ai"
                title="Expand to Full Page"
                className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-white/10 transition-colors"
              >
                <Maximize2 size={14} />
              </Link>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-white/10 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages Body */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-50 text-xs">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${m.sender === "USER" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 leading-relaxed shadow-sm ${
                    m.sender === "USER"
                      ? "bg-azure-600 text-white rounded-br-xs"
                      : "bg-white text-slate-800 border border-slate-200 rounded-bl-xs"
                  }`}
                >
                  <p className="whitespace-pre-line">{m.content}</p>

                  {/* Consequential Action Proposal Card */}
                  {m.action_proposal && (
                    <div className="mt-2.5 p-2.5 bg-amber-50/80 border border-amber-200/90 rounded-xl space-y-2 text-[11px]">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-bold text-amber-950">
                          <ShieldAlert size={14} className="text-amber-600 shrink-0" />
                          <span>{m.action_proposal.title}</span>
                        </div>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                          m.action_proposal.status === "executed"
                            ? "bg-emerald-100 text-emerald-800"
                            : m.action_proposal.status === "cancelled"
                            ? "bg-slate-200 text-slate-700"
                            : "bg-amber-100 text-amber-800 animate-pulse"
                        }`}>
                          {m.action_proposal.status === "executed"
                            ? "✓ Done"
                            : m.action_proposal.status === "cancelled"
                            ? "✕ Cancelled"
                            : "Confirm?"}
                        </span>
                      </div>

                      <p className="text-[10px] text-amber-950/80 leading-normal">
                        {m.action_proposal.impact_summary}
                      </p>

                      {m.action_proposal.status === "pending_confirmation" && (
                        <div className="flex items-center gap-1.5 pt-1">
                          <button
                            onClick={() => handleConfirmAction(m.action_proposal!)}
                            disabled={loading}
                            className="flex-1 py-1 px-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-md text-[10px] font-semibold flex items-center justify-center gap-1 shadow-xs transition"
                          >
                            <CheckCircle2 size={11} />
                            Confirm
                          </button>
                          <button
                            onClick={() => handleCancelAction(m.action_proposal!)}
                            disabled={loading}
                            className="py-1 px-2 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-md text-[10px] font-medium transition"
                          >
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tool Badge */}
                  {m.tool_calls && m.tool_calls.length > 0 && m.tool_calls[0] !== "system_ready" && (
                    <div className="mt-2 pt-1.5 border-t border-slate-100 flex flex-wrap gap-1">
                      {m.tool_calls.map((t, tidx) => (
                        <span
                          key={tidx}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-100 text-slate-600 border border-slate-200"
                        >
                          <ShieldCheck size={10} className="text-azure-600" />
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-slate-500 bg-white border border-slate-200 rounded-xl px-3 py-2 w-fit">
                <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce"></div>
                <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce [animation-delay:0.2s]"></div>
                <div className="w-2 h-2 rounded-full bg-azure-600 animate-bounce [animation-delay:0.4s]"></div>
                <span className="text-[11px] font-medium text-slate-600 pl-1">Querying hotel ledger...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompts Bar */}
          <div className="px-3 py-1.5 bg-slate-100 border-t border-slate-200 flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
            {QUICK_QUESTIONS.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(q)}
                disabled={loading}
                className="whitespace-nowrap px-2.5 py-1 text-[10px] font-medium bg-white text-slate-700 hover:text-azure-700 hover:bg-azure-50 border border-slate-200 rounded-full transition-colors shrink-0 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            className="p-2.5 bg-white border-t border-slate-200 flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about rooms, guests, revenue..."
              disabled={loading}
              className="flex-1 px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-azure-500/20 focus:border-azure-500"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="w-8 h-8 rounded-xl bg-azure-600 text-white flex items-center justify-center hover:bg-azure-700 disabled:opacity-50 disabled:hover:bg-azure-600 transition-colors shadow-sm shrink-0"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}

