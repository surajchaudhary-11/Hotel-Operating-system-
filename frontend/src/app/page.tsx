"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { ArrowRight } from "lucide-react";

export default function HomePage() {
  const { user, isLoading, memberships } = useAuth();
  const router = useRouter();
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      if (user) {
        if (memberships.length === 0) {
          router.replace("/onboard");
        } else {
          router.replace("/overview");
        }
      } else {
        router.replace("/login");
      }
    }
  }, [user, isLoading, memberships, router]);

  // Fallback timeout in case navigation or auth evaluation is delayed
  useEffect(() => {
    const timer = setTimeout(() => {
      setTimedOut(true);
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f8fafc",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
      className="min-h-screen flex items-center justify-center bg-slate-50 px-4"
    >
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "16px",
            background: "linear-gradient(135deg, #0284c7 0%, #66023c 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontWeight: "bold",
            fontSize: "24px",
            boxShadow: "0 10px 25px -5px rgba(2, 132, 199, 0.4)",
          }}
          className="w-14 h-14 rounded-2xl bg-gradient-to-br from-azure-600 to-tyrian-800 flex items-center justify-center text-white font-extrabold text-2xl shadow-xl shadow-azure-900/20 animate-pulse"
        >
          H
        </div>

        <div>
          <h1
            style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a", margin: "0" }}
            className="text-xl font-bold text-slate-900"
          >
            HotelOS
          </h1>
          <p
            style={{ fontSize: "13px", color: "#64748b", marginTop: "4px" }}
            className="text-slate-500 text-xs font-medium mt-1"
          >
            Hospitality Operating System
          </p>
        </div>

        {timedOut && (
          <div className="mt-4 flex flex-col gap-2.5 w-full">
            <Link
              href="/login"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "10px 16px",
                borderRadius: "12px",
                backgroundColor: "#0284c7",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: "600",
                textDecoration: "none",
              }}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-azure-600 hover:bg-azure-700 text-white text-xs font-semibold shadow-sm transition"
            >
              <span>Continue to Login</span>
              <ArrowRight size={14} />
            </Link>

            <Link
              href="/overview"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "8px 16px",
                borderRadius: "12px",
                backgroundColor: "#ffffff",
                color: "#475569",
                fontSize: "12px",
                fontWeight: "500",
                border: "1px solid #e2e8f0",
                textDecoration: "none",
              }}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200 transition"
            >
              <span>Open Dashboard</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
