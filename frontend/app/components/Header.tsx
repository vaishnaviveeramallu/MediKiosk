"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Clock,
  Users,
  UserPlus,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  FileText,
  ClipboardList,
  Stethoscope,
  LogIn,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { getUser, clearAuth, AuthUser } from "@/lib/auth";

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [time, setTime] = useState<string>("");
  const [dbStatus, setDbStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);

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
    const syncUser = () => {
      setCurrentUser(getUser());
    };
    syncUser();

    window.addEventListener("medikiosk-auth-changed", syncUser);
    return () => window.removeEventListener("medikiosk-auth-changed", syncUser);
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
          setActiveAlertsCount(Array.isArray(data) ? data.length : (data.active_count || 0));
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

  const handleLogout = async () => {
    try {
      await fetch("http://127.0.0.1:8000/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore network errors on logout
    }
    clearAuth();
    router.push("/login");
  };

  const isPatient = currentUser?.role === "patient";
  const isDoctor = currentUser?.role === "doctor";
  const isTriage = currentUser?.role === "triage_staff";

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
            {/* Patients and unauthenticated visitors can register */}
            {(!currentUser || isPatient) && (
              <Link
                href="/register"
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                  pathname === "/register"
                    ? "bg-teal-600 text-white shadow-sm"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <UserPlus className="w-4 h-4" />
                <span>Register</span>
              </Link>
            )}

            <Link
              href="/queue"
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                pathname === "/queue"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <Users className="w-4 h-4" />
              <span>Queue</span>
            </Link>

            {/* Triage Dashboard: Hidden for patient users */}
            {!isPatient && (
              <Link
                href="/triage"
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                  pathname === "/triage"
                    ? "bg-rose-600 text-white shadow-sm"
                    : activeAlertsCount > 0
                    ? "text-rose-700 bg-rose-50 hover:bg-rose-100 font-semibold"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <AlertTriangle className={`w-4 h-4 ${activeAlertsCount > 0 ? "text-rose-600 animate-pulse" : ""}`} />
                <span>Triage</span>
                {activeAlertsCount > 0 && (
                  <span className="ml-1 px-1.5 py-0.2 text-xs font-black bg-rose-600 text-white rounded-full">
                    {activeAlertsCount}
                  </span>
                )}
              </Link>
            )}

            <Link
              href="/documents"
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                pathname === "/documents"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Documents</span>
            </Link>

            <Link
              href="/summary"
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                pathname === "/summary"
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <ClipboardList className="w-4 h-4" />
              <span>Summary</span>
            </Link>

            {/* Doctor Dashboard: Hidden for patient users */}
            {!isPatient && (
              <Link
                href="/doctor"
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-sm transition ${
                  pathname?.startsWith("/doctor")
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-indigo-900 bg-indigo-50/70 hover:bg-indigo-100/80 font-semibold"
                }`}
              >
                <Stethoscope className={`w-4 h-4 ${pathname?.startsWith("/doctor") ? "text-white" : "text-indigo-600"}`} />
                <span>Doctor</span>
              </Link>
            )}
          </nav>

          {/* Right Status Panel & Auth Info */}
          <div className="hidden lg:flex items-center space-x-3">
            {/* DB Health Indicator */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
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
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>DB Online</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>{dbStatus === "checking" ? "Checking..." : "DB Offline"}</span>
                </>
              )}
            </div>

            {/* User Session Badge / Login Action */}
            {currentUser ? (
              <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
                <div
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 border ${
                    currentUser.role === "doctor"
                      ? "bg-indigo-50 text-indigo-800 border-indigo-200"
                      : currentUser.role === "triage_staff"
                      ? "bg-amber-50 text-amber-800 border-amber-200"
                      : "bg-teal-50 text-teal-800 border-teal-200"
                  }`}
                >
                  <UserIcon className="w-3.5 h-3.5" />
                  <span className="max-w-[120px] truncate">{currentUser.full_name}</span>
                  <span className="text-[10px] uppercase px-1 py-0.2 rounded bg-white/70 font-mono">
                    {currentUser.role}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Sign out of MediKiosk"
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Log In</span>
              </Link>
            )}

            {/* Live Clock */}
            <div className="flex items-center space-x-1.5 text-slate-600 text-xs font-mono bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{time || "00:00:00"}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
