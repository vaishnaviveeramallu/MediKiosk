"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Stethoscope,
  Search,
  Filter,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  User,
  FileText,
  ClipboardList,
  ShieldCheck,
  ChevronRight,
  ShieldAlert,
  Calendar,
  Phone,
  Activity,
  UserCheck,
  AlertCircle,
} from "lucide-react";
import { getAuthHeaders } from "@/lib/auth";

interface DoctorQueuePatient {
  patient_id: string;
  token_number: string;
  full_name: string;
  age: number;
  gender: string;
  phone_number: string;
  address_city?: string | null;
  registration_date: string;
  preferred_language: string;
  initial_complaint?: string | null;
  triage_status: "normal" | "high_alert" | "critical";
  active_triage_alerts: number;
  highest_triage_priority?: string | null;
  interview_status: "not_started" | "in_progress" | "completed";
  interview_answers_count: number;
  document_count: number;
  processed_document_count: number;
  has_summary: boolean;
  summary_status: "not_generated" | "ai_generated" | "physician_reviewed" | "physician_confirmed";
  doctor_review_status: "pending_review" | "in_review" | "needs_verification" | "physician_confirmed";
  has_conflicts: boolean;
  conflict_count: number;
  last_activity: string;
}

interface DoctorQueueResponse {
  total_patients: number;
  pending_review_count: number;
  in_review_count: number;
  needs_verification_count: number;
  confirmed_count: number;
  high_triage_count: number;
  patients: DoctorQueuePatient[];
}

interface IntegrationComponentStatus {
  name: string;
  status: string;
  configured: boolean;
  message: string;
  endpoint_url?: string | null;
  details?: Record<string, any> | null;
}

interface SystemIntegrationsStatusResponse {
  timestamp: string;
  system_version: string;
  components: Record<string, IntegrationComponentStatus>;
}

function DoctorDashboardContent() {
  const router = useRouter();

  const [queueData, setQueueData] = useState<DoctorQueueResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Phase 12: Healthcare Interoperability Status
  const [integrations, setIntegrations] = useState<SystemIntegrationsStatusResponse | null>(null);
  const [showIntegrations, setShowIntegrations] = useState<boolean>(false);

  // Filter States
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedTriage, setSelectedTriage] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  const fetchIntegrations = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/integrations/status", {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setIntegrations(data);
      }
    } catch (e) {
      console.error("Failed to load integrations status", e);
    }
  };

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.append("search", searchTerm.trim());
      if (selectedTriage !== "all") params.append("triage", selectedTriage);
      if (selectedStatus !== "all") params.append("status", selectedStatus);

      const res = await fetch(`http://127.0.0.1:8000/api/doctor/queue?${params.toString()}`, {
        cache: "no-store",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`Failed to load queue (${res.status})`);
      }
      const data: DoctorQueueResponse = await res.json();
      setQueueData(data);
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred while loading patient queue.");
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedTriage, selectedStatus]);

  useEffect(() => {
    fetchQueue();
    fetchIntegrations();
  }, [fetchQueue]);

  const getReviewStatusBadge = (status: string) => {
    switch (status) {
      case "physician_confirmed":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Physician Confirmed</span>
          </span>
        );
      case "in_review":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
            <Clock className="w-3.5 h-3.5 text-indigo-600" />
            <span>In Review</span>
          </span>
        );
      case "needs_verification":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Needs Verification</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
            <User className="w-3.5 h-3.5 text-slate-500" />
            <span>Pending Review</span>
          </span>
        );
    }
  };

  const getTriageBadge = (p: DoctorQueuePatient) => {
    if (p.triage_status === "critical" || p.triage_status === "high_alert") {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
          <span>{p.highest_triage_priority || "HIGH"} ALERT ({p.active_triage_alerts})</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
        <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
        <span>Normal</span>
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-16">
      {/* 1. DOCTOR DASHBOARD HEADER */}
      <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-teal-500 text-slate-950 flex items-center justify-center font-bold shadow-md">
              <Stethoscope className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Doctor Dashboard</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  OPD Clinical Portal
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400">
                Attending Physician Review &bull; Real-Time Intake Dossiers &bull; Case Sheet Sign-Off
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="px-3.5 py-2 bg-slate-800 rounded-xl border border-slate-700 text-xs text-slate-300 font-mono flex items-center space-x-2">
            <UserCheck className="w-4 h-4 text-teal-400" />
            <span>Role: Attending Physician</span>
          </div>

          <button
            type="button"
            onClick={fetchQueue}
            disabled={loading}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-xs sm:text-sm font-bold shadow-sm transition flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Phase 12: Healthcare Interoperability & Integration Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-sm text-white space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Healthcare Interoperability & Security Architecture
            </span>
            <span className="text-[11px] text-slate-400 hidden sm:inline">
              (Truthful Status &bull; Zero Mock Data)
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowIntegrations(!showIntegrations)}
            className="text-xs font-semibold text-teal-400 hover:text-teal-300 underline"
          >
            {showIntegrations ? "Hide Subsystems" : "View Subsystems Status"}
          </button>
        </div>

        {showIntegrations && integrations && (
          <div className="pt-3 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 text-xs">
            {Object.entries(integrations.components).map(([key, comp]) => (
              <div key={key} className="bg-slate-800/90 rounded-xl p-3 border border-slate-700/60 flex flex-col justify-between space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 capitalize">{key.replace("_", " ")}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      comp.status === "AVAILABLE" || comp.status === "CONFIGURED"
                        ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700"
                        : comp.status === "LOCAL_ONLY"
                        ? "bg-blue-900/60 text-blue-300 border border-blue-700"
                        : "bg-amber-900/60 text-amber-300 border border-amber-700"
                    }`}
                  >
                    {comp.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-tight">
                  {comp.message}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. CLINICAL METRICS CHIPS */}
      {queueData && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Total Patients</span>
            <span className="text-2xl font-black text-slate-900 mt-1 block">{queueData.total_patients}</span>
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Pending Review</span>
            <span className="text-2xl font-black text-slate-700 mt-1 block">{queueData.pending_review_count}</span>
          </div>

          <div className="bg-white border border-indigo-200 bg-indigo-50/40 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-indigo-700 uppercase tracking-wider block">In Review</span>
            <span className="text-2xl font-black text-indigo-900 mt-1 block">{queueData.in_review_count}</span>
          </div>

          <div className="bg-white border border-amber-200 bg-amber-50/40 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-amber-800 uppercase tracking-wider block">Needs Verification</span>
            <span className="text-2xl font-black text-amber-900 mt-1 block">{queueData.needs_verification_count}</span>
          </div>

          <div className="bg-white border border-emerald-200 bg-emerald-50/40 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider block">Confirmed</span>
            <span className="text-2xl font-black text-emerald-900 mt-1 block">{queueData.confirmed_count}</span>
          </div>

          <div className="bg-white border border-rose-200 bg-rose-50/40 rounded-2xl p-4 shadow-xs">
            <span className="text-[11px] font-bold text-rose-800 uppercase tracking-wider block">Urgent Alerts</span>
            <span className="text-2xl font-black text-rose-900 mt-1 block">{queueData.high_triage_count}</span>
          </div>
        </div>
      )}

      {/* 3. SEARCH & FILTERS CONTROLS */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search bar */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by Patient Name, OPD Token, or Patient ID..."
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          {/* Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500">
              <Filter className="w-3.5 h-3.5" />
              <span>Filters:</span>
            </div>

            <select
              value={selectedTriage}
              onChange={(e) => setSelectedTriage(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="all">Triage: All</option>
              <option value="high_alert">Triage: Urgent / High</option>
              <option value="normal">Triage: Normal</option>
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="all">Status: All</option>
              <option value="pending_review">Pending Review</option>
              <option value="in_review">In Review</option>
              <option value="needs_verification">Needs Verification</option>
              <option value="physician_confirmed">Physician Confirmed</option>
            </select>
          </div>
        </div>
      </div>

      {/* 4. ERROR MESSAGE */}
      {error && (
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-4 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{error}</div>
        </div>
      )}

      {/* 5. PATIENT QUEUE LIST */}
      {loading && !queueData && (
        <div className="bg-white border border-slate-200 rounded-3xl p-16 text-center space-y-3">
          <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-bold text-slate-700">Loading Doctor Patient Queue...</p>
        </div>
      )}

      {!loading && queueData && queueData.patients.length === 0 && (
        <div className="bg-white border-2 border-dashed border-slate-300 rounded-3xl p-16 text-center space-y-3">
          <ClipboardList className="w-12 h-12 text-slate-300 mx-auto" />
          <h3 className="text-lg font-bold text-slate-800">No Patients Match Current Filters</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Try adjusting your search criteria or resetting triage and review filters.
          </p>
        </div>
      )}

      {!loading && queueData && queueData.patients.length > 0 && (
        <div className="space-y-3.5">
          {queueData.patients.map((p) => (
            <div
              key={p.patient_id}
              className={`bg-white border-2 rounded-2xl p-5 shadow-xs transition hover:shadow-md flex flex-col lg:flex-row lg:items-center justify-between gap-4 ${
                p.doctor_review_status === "physician_confirmed"
                  ? "border-emerald-200 bg-emerald-50/10"
                  : p.doctor_review_status === "needs_verification"
                  ? "border-amber-300 bg-amber-50/15"
                  : p.triage_status === "critical" || p.triage_status === "high_alert"
                  ? "border-rose-300 bg-rose-50/10"
                  : "border-slate-200 hover:border-teal-400"
              }`}
            >
              {/* Left Column: Token + Patient Demographics */}
              <div className="flex items-start space-x-4">
                <div className="w-16 h-16 rounded-2xl bg-teal-600 text-white flex flex-col items-center justify-center font-bold shadow-xs flex-shrink-0">
                  <span className="text-[10px] uppercase font-mono tracking-widest text-teal-200">OPD</span>
                  <span className="font-mono text-xs font-black">{p.token_number.replace(/^MK-/, "")}</span>
                </div>

                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base sm:text-lg font-black text-slate-900">{p.full_name}</h3>
                    <span className="text-xs bg-slate-100 text-slate-700 font-semibold px-2 py-0.5 rounded-md">
                      {p.age}y &bull; {p.gender}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      ID: #{p.patient_id.slice(-6)}
                    </span>
                  </div>

                  {p.initial_complaint && (
                    <p className="text-xs text-slate-700 font-medium line-clamp-1">
                      <span className="font-bold text-slate-900">Complaint:</span> {p.initial_complaint}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 pt-0.5">
                    <span className="flex items-center space-x-1 font-mono">
                      <Phone className="w-3 h-3 text-slate-400" />
                      <span>{p.phone_number}</span>
                    </span>
                    {p.address_city && (
                      <span>&bull; {p.address_city}</span>
                    )}
                    <span>
                      &bull; Registered: {new Date(p.registration_date).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className="uppercase font-bold px-1.5 py-0.2 bg-slate-100 rounded text-[10px]">
                      {p.preferred_language}
                    </span>
                  </div>
                </div>
              </div>

              {/* Middle / Right Column: Badges & Open Review Action */}
              <div className="flex flex-wrap items-center justify-between lg:justify-end gap-3 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-100">
                {/* Clinical Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  {/* Triage */}
                  {getTriageBadge(p)}

                  {/* Interview Status */}
                  <span
                    className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                      p.interview_status === "completed"
                        ? "bg-teal-50 text-teal-800 border-teal-200"
                        : "bg-slate-50 text-slate-600 border-slate-200"
                    }`}
                  >
                    <ClipboardList className="w-3.5 h-3.5 text-teal-600" />
                    <span>Intake: {p.interview_answers_count} Ans</span>
                  </span>

                  {/* Documents count */}
                  {p.document_count > 0 && (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                      <FileText className="w-3.5 h-3.5 text-slate-500" />
                      <span>{p.document_count} Doc{p.document_count > 1 ? "s" : ""}</span>
                    </span>
                  )}

                  {/* Conflicts Flag */}
                  {p.has_conflicts && (
                    <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-amber-100 text-amber-900 border border-amber-300">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                      <span>{p.conflict_count} Conflict</span>
                    </span>
                  )}

                  {/* Doctor Review Status */}
                  {getReviewStatusBadge(p.doctor_review_status)}
                </div>

                {/* Open Review Action Button */}
                <Link
                  href={`/doctor/patient/${p.patient_id}`}
                  className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs sm:text-sm font-bold shadow-xs transition flex items-center space-x-1.5 ml-auto lg:ml-0"
                >
                  <Stethoscope className="w-4 h-4 text-teal-400" />
                  <span>Review Patient</span>
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DoctorDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-3xl mx-auto py-16 text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-sm font-bold text-slate-700">Loading Doctor Dashboard...</p>
        </div>
      }
    >
      <DoctorDashboardContent />
    </Suspense>
  );
}
