"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Clock, Users, UserPlus, ShieldCheck, AlertCircle, AlertTriangle, FileText, ClipboardList, Stethoscope } from "lucide-react";

export default function Header() {
  const pathname = usePathname();
  const [time, setTime] = useState<string>("");
  const [dbStatus, setDbStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/health", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setDbStatus(data.database === "connected" ? "connected" : "disconnected");
        } else {
          setDbStatus("disconnected");
        }
      } catch {
        setDbStatus("disconnected");
      }
    };

    const checkAlerts = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/triage/alerts?status=active", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setActiveAlertsCount(Array.isArray(data) ? data.length : 0);
        }
      } catch {
        // Ignore background polling errors
      }
    };

    checkHealth();
    checkAlerts();
    const interval = setInterval(() => {
      checkHealth();
      checkAlerts();
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo & Hospital Kiosk Title */}
          <Link href="/" className="flex items-center space-x-3 group">
            <div className="w-12 h-12 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-md group-hover:bg-teal-700 transition">
              <Activity className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-2xl font-bold tracking-tight text-slate-900">MediKiosk</span>
                <span className="bg-teal-100 text-teal-800 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                  OPD Intake
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                AI Patient Case-Taking Software • अस्पताल ओपीडी कियोस्क
              </p>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-2">
            <Link
              href="/register"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname === "/register"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <UserPlus className="w-5 h-5" />
              <span>Register Patient</span>
            </Link>

            <Link
              href="/queue"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname === "/queue"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <Users className="w-5 h-5" />
              <span>OPD Queue</span>
            </Link>

            <Link
              href="/triage"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname === "/triage"
                  ? "bg-rose-600 text-white shadow-sm"
                  : activeAlertsCount > 0
                  ? "text-rose-700 bg-rose-50 hover:bg-rose-100 font-semibold"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <AlertTriangle className={`w-5 h-5 ${activeAlertsCount > 0 ? "text-rose-600 animate-pulse" : ""}`} />
              <span>Triage</span>
              {activeAlertsCount > 0 && (
                <span className="ml-1 px-2 py-0.5 text-xs font-black bg-rose-600 text-white rounded-full">
                  {activeAlertsCount}
                </span>
              )}
            </Link>

            <Link
              href="/documents"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname === "/documents"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <FileText className="w-5 h-5" />
              <span>Documents</span>
            </Link>

            <Link
              href="/summary"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname === "/summary"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <ClipboardList className="w-5 h-5" />
              <span>Summary</span>
            </Link>

            <Link
              href="/doctor"
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-medium text-base transition ${
                pathname?.startsWith("/doctor")
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-indigo-900 bg-indigo-50/70 hover:bg-indigo-100/80 font-semibold"
              }`}
            >
              <Stethoscope className={`w-5 h-5 ${pathname?.startsWith("/doctor") ? "text-white" : "text-indigo-600"}`} />
              <span>Doctor</span>
            </Link>
          </nav>

          {/* Right Status Panel */}
          <div className="hidden md:flex items-center space-x-4">
            {/* DB Health Indicator */}
            <div
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${
                dbStatus === "connected"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : dbStatus === "checking"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-rose-50 text-rose-700 border-rose-200"
              }`}
              title={
                dbStatus === "connected"
                  ? "MongoDB Database Connected"
                  : "Connecting to Backend / Database"
              }
            >
              {dbStatus === "connected" ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>DB Online</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>{dbStatus === "checking" ? "Checking DB..." : "DB Offline"}</span>
                </>
              )}
            </div>

            {/* Live Clock */}
            <div className="flex items-center space-x-1.5 text-slate-600 text-sm font-mono bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
              <Clock className="w-4 h-4 text-slate-400" />
              <span>{time || "00:00:00"}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
