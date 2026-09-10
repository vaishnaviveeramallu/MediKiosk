"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ShieldAlert,
  Clock,
  User,
  RefreshCw,
  CheckCircle2,
  Check,
  Search,
  ArrowLeft,
  Filter,
  FileText,
  AlertCircle,
  MessageSquare,
  Building,
  ChevronRight,
  Send,
  ExternalLink,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

interface TriageAlert {
  alert_id: string;
  patient_id: string;
  token_number: string;
  patient_name?: string;
  full_name?: string;
  language?: string;
  priority: "URGENT" | "HIGH";
  detected_category?: string;
  category?: string;
  title_en?: string;
  title_hi?: string;
  rule_description?: string;
  description_en?: string;
  description_hi?: string;
  patient_instruction_en?: string;
  patient_instruction_hi?: string;
  triggering_answer?: string;
  triggering_text?: string;
  detected_keywords?: string[];
  question_id?: string;
  status: "active" | "acknowledged" | "handled";
  detected_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  handled_at?: string | null;
  handled_by?: string | null;
  staff_notes?: string | null;
}

export default function TriageDashboardPage() {
  const [alerts, setAlerts] = useState<TriageAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "acknowledged" | "handled">("all");
  const [priorityFilter, setPriorityFilter] = useState<"all" | "URGENT" | "HIGH">("all");
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [staffNotesMap, setStaffNotesMap] = useState<Record<string, string>>({});
  const [staffName, setStaffName] = useState("OPD Nurse / Triage Officer");

  const fetchAlerts = useCallback(async () => {
    try {
      setError(null);
      let url = "http://127.0.0.1:8000/api/triage/alerts";
      const params = new URLSearchParams();

      if (statusFilter !== "all") {
        params.append("status", statusFilter);
      }
      if (priorityFilter !== "all") {
        params.append("priority", priorityFilter);
      }

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to fetch triage alerts (${res.status})`);
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.alerts || [];
      setAlerts(list);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError("Could not load triage alerts. Please check backend connection.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      fetchAlerts();
    }, 5000);
    return () => clearInterval(timer);
  }, [autoRefresh, fetchAlerts]);

  // Update alert status (acknowledge or handle)
  const handleUpdateStatus = async (
    alertId: string,
    newStatus: "acknowledged" | "handled"
  ) => {
    setActionLoading(alertId);
    try {
      const notes = staffNotesMap[alertId] || "";
      const res = await fetch(`http://127.0.0.1:8000/api/triage/alerts/${encodeURIComponent(alertId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: newStatus,
          staff_id: staffName.trim() || "Staff Nurse",
          staff_notes: notes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to update alert.");
      }

      // Refresh alerts list
      await fetchAlerts();
    } catch (err: any) {
      alert(`Error updating triage alert: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Filter alerts locally by search
  const filteredAlerts = alerts.filter((a) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    const token = (a.token_number || "").toLowerCase();
    const name = (a.patient_name || a.full_name || "").toLowerCase();
    const title = (a.title_en || a.detected_category || a.category || "").toLowerCase();
    const answer = (a.triggering_answer || a.triggering_text || "").toLowerCase();
    return token.includes(query) || name.includes(query) || title.includes(query) || answer.includes(query);
  });

  const activeCount = alerts.filter((a) => a.status === "active").length;
  const ackCount = alerts.filter((a) => a.status === "acknowledged").length;
  const handledCount = alerts.filter((a) => a.status === "handled").length;

  const formatDateTime = (isoString?: string | null) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 space-y-6">
      {/* Top Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link
            href="/queue"
            className="inline-flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 text-sm font-semibold transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to OPD Queue</span>
          </Link>
          <div className="flex items-center space-x-3 mt-2">
            <div className="w-11 h-11 rounded-2xl bg-rose-600 text-white flex items-center justify-center shadow-md">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                  Hospital Triage Dashboard
                </h1>
                <span className="bg-rose-100 text-rose-800 text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider">
                  Phase 6 Live
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Real-time Red-Flag Warning Monitor • अस्पताल ओपीडी ट्रायज डैशबोर्ड
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Refresh, Auto-refresh, Staff Identity */}
        <div className="flex items-center flex-wrap gap-2 sm:gap-3">
          <div className="flex items-center space-x-2 bg-white px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-700">
            <UserCheck className="w-4 h-4 text-teal-600" />
            <span className="font-semibold hidden md:inline">Staff:</span>
            <input
              type="text"
              value={staffName}
              onChange={(e) => setStaffName(e.target.value)}
              className="w-36 text-xs bg-slate-50 border border-slate-200 px-2 py-1 rounded font-medium focus:outline-none focus:border-teal-500"
              placeholder="Your Name / Title"
            />
          </div>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-2 rounded-xl text-xs font-bold border transition flex items-center space-x-1.5 ${
              autoRefresh
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                autoRefresh ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
              }`}
            />
            <span>{autoRefresh ? "Auto-refresh: ON" : "Auto-refresh: OFF"}</span>
          </button>

          <button
            onClick={() => fetchAlerts()}
            className="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm transition"
            title="Refresh alerts now"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-600" : ""}`} />
          </button>
        </div>
      </div>

      {/* Clinical Non-Diagnostic Safety Banner */}
      <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-start space-x-3 text-xs sm:text-sm text-amber-950">
        <ShieldAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-bold">
            Automated Clinical Safety & Triage Alert Notification System
          </p>
          <p className="text-amber-900 text-xs leading-relaxed">
            This dashboard highlights urgent symptoms reported by patients during clinical intake. 
            It is strictly a safety flagging tool to prioritize attention and does NOT provide medical diagnosis or therapeutic orders.
            Patients marked URGENT should be immediately evaluated by the OPD triage nurse or emergency medical officer.
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-white border-2 border-rose-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">Active Alerts</span>
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
          </div>
          <div className="mt-2 text-3xl font-black text-rose-600">{activeCount}</div>
          <span className="text-[11px] text-slate-500 font-medium">Requires immediate staff review</span>
        </div>

        <div className="bg-white border border-amber-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-700 uppercase tracking-wider">Acknowledged</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-3xl font-black text-amber-600">{ackCount}</div>
          <span className="text-[11px] text-slate-500 font-medium">Staff attending / evaluated</span>
        </div>

        <div className="bg-white border border-emerald-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">Handled</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-3xl font-black text-emerald-600">{handledCount}</div>
          <span className="text-[11px] text-slate-500 font-medium">Triage complete / redirected</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Total Red Flags</span>
            <ShieldAlert className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-3xl font-black text-slate-800">{alerts.length}</div>
          <span className="text-[11px] text-slate-500 font-medium">Recorded in MongoDB</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by token, patient, symptom..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>

        {/* Status Tabs */}
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-xl w-full md:w-auto overflow-x-auto">
          {(
            [
              { id: "all", label: "All" },
              { id: "active", label: `Active (${activeCount})` },
              { id: "acknowledged", label: `Acknowledged (${ackCount})` },
              { id: "handled", label: `Handled (${handledCount})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
                statusFilter === tab.id
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Priority Filter */}
        <div className="flex items-center space-x-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as any)}
            className="text-xs border border-slate-200 rounded-xl px-3 py-2 bg-white text-slate-700 font-semibold focus:outline-none focus:border-teal-500"
          >
            <option value="all">All Priorities</option>
            <option value="URGENT">URGENT Priority Only</option>
            <option value="HIGH">HIGH Priority Only</option>
          </select>
        </div>
      </div>

      {/* Alerts Stream */}
      {loading && alerts.length === 0 ? (
        <div className="py-16 text-center space-y-3">
          <div className="w-10 h-10 border-4 border-rose-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading triage alerts...</p>
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-3xl p-12 text-center space-y-4 shadow-sm">
          <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-slate-800">No Triage Alerts Found</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              {statusFilter === "active"
                ? "There are currently zero unhandled red-flag alerts in the hospital OPD queue."
                : "No triage alerts match the selected status or search filter."}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAlerts.map((alert) => {
            const isActive = alert.status === "active";
            const isAck = alert.status === "acknowledged";
            const isHandled = alert.status === "handled";
            const isUrgent = alert.priority === "URGENT";

            return (
              <div
                key={alert.alert_id}
                className={`bg-white rounded-2xl border-2 transition shadow-sm overflow-hidden ${
                  isActive
                    ? isUrgent
                      ? "border-rose-400 ring-2 ring-rose-100"
                      : "border-amber-400 ring-2 ring-amber-100"
                    : isAck
                    ? "border-amber-200 bg-amber-50/20"
                    : "border-slate-200 opacity-80"
                }`}
              >
                {/* Header Strip */}
                <div
                  className={`px-5 py-3 flex flex-wrap items-center justify-between gap-2 text-xs font-semibold ${
                    isActive
                      ? isUrgent
                        ? "bg-rose-50 text-rose-800 border-b border-rose-100"
                        : "bg-amber-50 text-amber-800 border-b border-amber-100"
                      : isAck
                      ? "bg-amber-50/70 text-amber-900 border-b border-amber-100"
                      : "bg-slate-50 text-slate-700 border-b border-slate-100"
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2.5 py-1 rounded-md text-[11px] font-black tracking-wider uppercase ${
                        isUrgent ? "bg-rose-600 text-white" : "bg-amber-600 text-white"
                      }`}
                    >
                      {alert.priority}
                    </span>
                    <span
                      className={`px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${
                        isActive
                          ? "bg-rose-100 text-rose-900 border border-rose-300 animate-pulse"
                          : isAck
                          ? "bg-amber-100 text-amber-900 border border-amber-300"
                          : "bg-emerald-100 text-emerald-900 border border-emerald-300"
                      }`}
                    >
                      {alert.status.toUpperCase()}
                    </span>
                    <span className="font-mono text-slate-500">ID: {alert.alert_id}</span>
                  </div>

                  <div className="flex items-center space-x-1.5 text-slate-500">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Detected: {formatDateTime(alert.detected_at)}</span>
                  </div>
                </div>

                {/* Body Content */}
                <div className="p-5 space-y-4">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    {/* Patient & Alert Info */}
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center space-x-3">
                        <span className="font-mono font-bold text-sm bg-teal-50 text-teal-700 px-3 py-1 rounded-lg border border-teal-200">
                          {alert.token_number}
                        </span>
                        <h2 className="text-xl font-extrabold text-slate-900">
                          {alert.patient_name || alert.full_name}
                        </h2>
                        <span className="text-xs uppercase font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          Lang: {alert.language || "en"}
                        </span>
                      </div>

                      <div className="space-y-1 pt-1">
                        <div className="flex items-baseline space-x-2">
                          <h4 className="text-base font-bold text-rose-900">
                            {alert.title_en || alert.detected_category || alert.category}
                          </h4>
                          {alert.title_hi && (
                            <span className="text-xs text-slate-500">({alert.title_hi})</span>
                          )}
                        </div>
                        <p className="text-xs text-slate-600">
                          {alert.rule_description || alert.description_en}
                        </p>
                      </div>
                    </div>

                    {/* Quick Link to Patient Interview */}
                    <div className="flex-shrink-0">
                      <Link
                        href={`/interview?patientId=${encodeURIComponent(alert.patient_id)}`}
                        className="inline-flex items-center space-x-1.5 text-xs font-bold text-teal-700 hover:text-teal-900 bg-teal-50 px-3 py-2 rounded-xl border border-teal-200 transition"
                      >
                        <span>View Intake Session</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>

                  {/* Triggering Answer Box */}
                  <div className="bg-rose-50/60 border border-rose-200 rounded-xl p-3.5 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-rose-900 uppercase tracking-wider flex items-center space-x-1">
                        <MessageSquare className="w-3.5 h-3.5 text-rose-600" />
                        <span>Patient Reported Text</span>
                      </span>
                      <span className="text-[11px] font-mono text-rose-700">
                        Question ID: {alert.question_id || "N/A"}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-slate-900 italic font-mono bg-white p-2.5 rounded-lg border border-rose-100">
                      &ldquo;{alert.triggering_answer || alert.triggering_text}&rdquo;
                    </p>
                    {alert.detected_keywords && alert.detected_keywords.length > 0 && (
                      <div className="flex items-center space-x-1.5 pt-1 text-[11px]">
                        <span className="text-slate-500 font-semibold">Flagged terms:</span>
                        <div className="flex flex-wrap gap-1">
                          {alert.detected_keywords.map((kw, idx) => (
                            <span
                              key={idx}
                              className="bg-rose-100 text-rose-800 font-mono font-bold px-1.5 py-0.5 rounded text-[10px]"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Patient Instruction Recommended */}
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-700 space-y-1">
                    <span className="font-bold uppercase tracking-wider text-slate-500">
                      Action Required:
                    </span>
                    <p className="font-medium text-slate-800">{alert.patient_instruction_en || alert.rule_description || "Immediate staff evaluation recommended."}</p>
                    {alert.patient_instruction_hi && (
                      <p className="text-slate-500 text-[11px]">{alert.patient_instruction_hi}</p>
                    )}
                  </div>

                  {/* Audit Trail & Staff Action Panel */}
                  <div className="pt-2 border-t border-slate-100 space-y-3">
                    {/* Status Info if Acknowledged/Handled */}
                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
                      {alert.acknowledged_at && (
                        <div>
                          <span className="font-semibold text-slate-700">Acknowledged:</span>{" "}
                          {formatDateTime(alert.acknowledged_at)} by{" "}
                          <span className="font-medium text-slate-900">{alert.acknowledged_by || "Staff"}</span>
                        </div>
                      )}
                      {alert.handled_at && (
                        <div>
                          <span className="font-semibold text-slate-700">Handled:</span>{" "}
                          {formatDateTime(alert.handled_at)} by{" "}
                          <span className="font-medium text-slate-900">{alert.handled_by || "Staff"}</span>
                        </div>
                      )}
                      {alert.staff_notes && (
                        <div className="w-full bg-slate-100 p-2 rounded-lg text-slate-800">
                          <span className="font-bold">Staff Notes:</span> {alert.staff_notes}
                        </div>
                      )}
                    </div>

                    {/* Action Controls for Staff */}
                    {!isHandled && (
                      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                        <input
                          type="text"
                          placeholder="Add clinical triage note (e.g. Escorted to Room 4 / Vitals checked)..."
                          value={staffNotesMap[alert.alert_id] || ""}
                          onChange={(e) =>
                            setStaffNotesMap({
                              ...staffNotesMap,
                              [alert.alert_id]: e.target.value,
                            })
                          }
                          className="flex-1 text-xs border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-teal-500"
                        />

                        {isActive && (
                          <button
                            disabled={actionLoading === alert.alert_id}
                            onClick={() => handleUpdateStatus(alert.alert_id, "acknowledged")}
                            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center justify-center space-x-1.5 disabled:opacity-50"
                          >
                            <Clock className="w-3.5 h-3.5" />
                            <span>Acknowledge Alert</span>
                          </button>
                        )}

                        <button
                          disabled={actionLoading === alert.alert_id}
                          onClick={() => handleUpdateStatus(alert.alert_id, "handled")}
                          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center justify-center space-x-1.5 disabled:opacity-50"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Mark as Handled</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
