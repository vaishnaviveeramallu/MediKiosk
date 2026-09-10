"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowLeft,
  RefreshCw,
  Copy,
  Check,
  Printer,
  ShieldAlert,
  Search,
  User,
  Stethoscope,
  Pill,
  Calendar,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  AlertCircle,
  Activity,
  Layers,
  FileCheck,
  FolderOpen,
} from "lucide-react";

interface TimelineEvent {
  event_id: string;
  event_date?: string | null;
  display_date: string;
  event_type: string;
  title: string;
  details: Record<string, any>;
  source: string;
  source_label: string;
  source_document_id?: string | null;
  source_session_id?: string | null;
  verification_status: string;
  is_conflict: boolean;
  conflict_notes?: string | null;
}

interface MedicalTimelineData {
  patient_id: string;
  token_number: string;
  patient_name: string;
  total_events: number;
  dated_events: TimelineEvent[];
  undated_events: TimelineEvent[];
  has_conflicts: boolean;
  conflict_count: number;
  generated_at: string;
}

interface SummarySection {
  section_id: string;
  section_number: number;
  title: string;
  content: string;
  items: Array<Record<string, any>>;
  is_available: boolean;
  source_references: string[];
  requires_verification: boolean;
}

interface ClinicalSummaryData {
  patient_id: string;
  token_number: string;
  patient_name: string;
  summary_draft: string;
  sections: Record<string, SummarySection>;
  disclaimer: string;
  verification_status: string;
  generated_at: string;
  source_counts: {
    interview_answers: number;
    documents: number;
    triage_alerts: number;
  };
  conflicting_findings: string[];
}

interface PatientRecord {
  id: string;
  token_number: string;
  full_name: string;
  age?: number;
  gender?: string;
  address_city?: string;
  registration_status?: string;
  initial_complaint?: string;
}

function SummaryContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const patientIdParam = searchParams.get("patientId") || "";

  const [patientId, setPatientId] = useState<string>(patientIdParam);
  const [patient, setPatient] = useState<PatientRecord | null>(null);
  const [allPatients, setAllPatients] = useState<PatientRecord[]>([]);

  const [timeline, setTimeline] = useState<MedicalTimelineData | null>(null);
  const [summary, setSummary] = useState<ClinicalSummaryData | null>(null);

  const [loading, setLoading] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"summary" | "timeline">("summary");
  const [copied, setCopied] = useState<boolean>(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [allExpanded, setAllExpanded] = useState<boolean>(true);

  // 1. Load patient queue for selector dropdown
  useEffect(() => {
    async function loadPatients() {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/patients", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setAllPatients(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        console.warn("Could not load patients list", err);
      }
    }
    loadPatients();
  }, []);

  // 2. Fetch Patient, Timeline and Summary
  const fetchData = useCallback(
    async (pid: string, forceRegen: boolean = false) => {
      if (!pid) return;
      if (forceRegen) {
        setRegenerating(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        // Fetch patient profile
        const patRes = await fetch(`http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid)}`, {
          cache: "no-store",
        });
        if (patRes.ok) {
          const patData = await patRes.json();
          setPatient(patData);
        }

        // Fetch / Regenerate Timeline
        const timelineUrl = forceRegen
          ? `http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid)}/timeline/generate`
          : `http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid)}/timeline`;
        const timelineRes = await fetch(timelineUrl, {
          method: forceRegen ? "POST" : "GET",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
        });

        if (timelineRes.ok) {
          const timelineData = await timelineRes.json();
          setTimeline(timelineData);
        } else {
          const errBody = await timelineRes.json().catch(() => ({}));
          throw new Error(errBody.detail || "Failed to retrieve medical timeline.");
        }

        // Fetch / Regenerate Summary
        const summaryUrl = forceRegen
          ? `http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid)}/summary/regenerate`
          : `http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid)}/summary`;
        const summaryRes = await fetch(summaryUrl, {
          method: forceRegen ? "POST" : "GET",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
        });

        if (summaryRes.ok) {
          const summaryData = await summaryRes.json();
          setSummary(summaryData);

          // Initialize all sections as expanded by default
          const expState: Record<string, boolean> = {};
          if (summaryData.sections) {
            Object.keys(summaryData.sections).forEach((k) => {
              expState[k] = true;
            });
          }
          setExpandedSections(expState);
        } else {
          const errBody = await summaryRes.json().catch(() => ({}));
          throw new Error(errBody.detail || "Failed to retrieve clinical summary.");
        }
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred.");
      } finally {
        setLoading(false);
        setRegenerating(false);
      }
    },
    []
  );

  useEffect(() => {
    if (patientIdParam) {
      setPatientId(patientIdParam);
      fetchData(patientIdParam);
    }
  }, [patientIdParam, fetchData]);

  const handlePatientSelect = (pid: string) => {
    setPatientId(pid);
    router.push(`/summary?patientId=${encodeURIComponent(pid)}`);
  };

  const handleCopySummary = async () => {
    if (!summary?.summary_draft) return;
    try {
      await navigator.clipboard.writeText(summary.summary_draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
      const textArea = document.createElement("textarea");
      textArea.value = summary.summary_draft;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const toggleSection = (secId: string) => {
    setExpandedSections((prev) => ({ ...prev, [secId]: !prev[secId] }));
  };

  const toggleAllSections = () => {
    const nextState = !allExpanded;
    setAllExpanded(nextState);
    if (summary?.sections) {
      const exp: Record<string, boolean> = {};
      Object.keys(summary.sections).forEach((k) => {
        exp[k] = nextState;
      });
      setExpandedSections(exp);
    }
  };

  const getEventTypeBadgeColor = (type: string) => {
    switch (type) {
      case "triage_alert":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "allergy_documented":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "diagnosis_documented":
        return "bg-indigo-100 text-indigo-800 border-indigo-300";
      case "medication_prescribed":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "investigation_result":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "procedure_performed":
      case "hospital_discharge":
        return "bg-purple-100 text-purple-800 border-purple-300";
      default:
        return "bg-teal-100 text-teal-800 border-teal-300";
    }
  };

  const formatEventType = (type: string) => {
    return type
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  };

  // Convert sections object to ordered array (1 to 14)
  const orderedSections: SummarySection[] = summary?.sections
    ? Object.values(summary.sections).sort((a, b) => a.section_number - b.section_number)
    : [];

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* 1. CLINICAL SAFETY BANNER (Phase 9 Non-Diagnostic Guard) */}
      <div className="bg-amber-500/15 border-2 border-amber-500/60 rounded-2xl p-4 sm:p-5 flex items-start space-x-3.5 shadow-sm">
        <ShieldAlert className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-black text-amber-950 text-sm sm:text-base tracking-wide uppercase">
              AI-Generated Clinical Draft — Physician Verification Required
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-200 text-amber-900 border border-amber-400">
              Needs Review
            </span>
          </div>
          <p className="text-xs sm:text-sm text-amber-900 leading-relaxed">
            This medical timeline and clinical summary are automated organizational drafts synthesized
            strictly from authentic patient intake responses and uploaded clinical records.{" "}
            <strong>They do not constitute an autonomous diagnosis or treatment plan.</strong> The attending
            physician must independently examine the patient, confirm all clinical findings, and make all
            diagnostic and prescription decisions.
          </p>
        </div>
      </div>

      {/* 2. PATIENT SELECTOR & ACTIONS HEADER */}
      <div className="bg-white border-2 border-slate-200 rounded-3xl p-5 sm:p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Patient Info or Selector */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1.5">
              <User className="w-3.5 h-3.5" />
              <span>Select Patient:</span>
            </label>
            <select
              value={patientId}
              onChange={(e) => handlePatientSelect(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-1.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">-- Choose Patient in Queue --</option>
              {allPatients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.token_number} - {p.full_name} ({p.age ? `${p.age}y` : "Adult"}, {p.gender || "Patient"})
                </option>
              ))}
            </select>
          </div>

          {patient && (
            <div className="flex flex-wrap items-center gap-2.5 pt-1">
              <span className="text-xl font-black text-slate-900">{patient.full_name}</span>
              <span className="px-3 py-1 rounded-xl bg-teal-600 text-white font-mono font-bold text-xs shadow-xs">
                OPD: {patient.token_number}
              </span>
              <span className="text-xs font-medium text-slate-500">
                {patient.age} yrs • {patient.gender}
                {patient.address_city ? ` • ${patient.address_city}` : ""}
              </span>
              {patient.initial_complaint && (
                <span className="text-xs font-semibold bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-lg">
                  Complaint: {patient.initial_complaint}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Right: Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {patientId && (
            <>
              <button
                type="button"
                onClick={() => fetchData(patientId, true)}
                disabled={loading || regenerating}
                className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl text-xs sm:text-sm font-bold shadow-sm transition flex items-center space-x-1.5"
                title="Re-aggregate interview responses and document findings"
              >
                <RefreshCw className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`} />
                <span>{regenerating ? "Synthesizing..." : "Regenerate Summary"}</span>
              </button>

              <button
                type="button"
                onClick={handleCopySummary}
                disabled={!summary}
                className="px-3.5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs sm:text-sm font-bold border border-slate-300 transition flex items-center space-x-1.5"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4 text-slate-600" />}
                <span>{copied ? "Copied!" : "Copy Summary"}</span>
              </button>

              <button
                type="button"
                onClick={() => window.print()}
                className="px-3.5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs sm:text-sm font-bold border border-slate-300 transition flex items-center space-x-1.5"
                title="Print clinical summary draft"
              >
                <Printer className="w-4 h-4 text-slate-600" />
                <span>Print</span>
              </button>

              <Link
                href={`/documents?patientId=${encodeURIComponent(patientId)}`}
                className="px-3.5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs sm:text-sm font-bold border border-slate-300 transition flex items-center space-x-1.5"
              >
                <FolderOpen className="w-4 h-4 text-slate-600" />
                <span>Documents</span>
              </Link>
            </>
          )}

          <Link
            href="/queue"
            className="px-3.5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs sm:text-sm font-bold border border-slate-300 transition flex items-center space-x-1.5"
          >
            <ArrowLeft className="w-4 h-4 text-slate-600" />
            <span>Queue</span>
          </Link>
        </div>
      </div>

      {/* 3. ERROR BANNER */}
      {error && (
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-4 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{error}</div>
        </div>
      )}

      {/* 4. LOADING STATE */}
      {loading && !summary && (
        <div className="bg-white border-2 border-slate-200 rounded-3xl p-16 text-center space-y-4 shadow-sm">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-base font-bold text-slate-800">
            Synthesizing Medical Timeline & 14-Section Clinical Summary...
          </p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Aggregating authentic MongoDB interview answers, OCR-extracted findings, and triage warnings.
          </p>
        </div>
      )}

      {/* 5. NO PATIENT SELECTED STATE */}
      {!patientId && !loading && (
        <div className="bg-white border-2 border-dashed border-slate-300 rounded-3xl p-16 text-center space-y-4">
          <ClipboardList className="w-12 h-12 text-slate-400 mx-auto" />
          <h3 className="text-lg font-bold text-slate-800">Please Select a Patient</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Choose an active patient from the dropdown above or navigate from the OPD Queue to view their
            medical timeline and clinical summary.
          </p>
          <div className="pt-2">
            <Link
              href="/queue"
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-bold shadow-sm transition"
            >
              <span>Go to OPD Queue</span>
            </Link>
          </div>
        </div>
      )}

      {/* 6. MAIN CONTENT TABS & VIEWS */}
      {patientId && !loading && (
        <div className="space-y-6">
          {/* TAB SWITCHER & METADATA BAR */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
            {/* Tabs */}
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setActiveTab("summary")}
                className={`px-5 py-2.5 rounded-xl font-bold text-sm transition flex items-center space-x-2 ${
                  activeTab === "summary"
                    ? "bg-teal-600 text-white shadow-sm"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                <ClipboardList className="w-4 h-4" />
                <span>14-Section Clinical Summary</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("timeline")}
                className={`px-5 py-2.5 rounded-xl font-bold text-sm transition flex items-center space-x-2 ${
                  activeTab === "timeline"
                    ? "bg-teal-600 text-white shadow-sm"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                <Clock className="w-4 h-4" />
                <span>Chronological Timeline</span>
                {timeline && (
                  <span
                    className={`ml-1 px-2 py-0.5 rounded-full text-xs font-bold ${
                      activeTab === "timeline" ? "bg-teal-700 text-white" : "bg-slate-200 text-slate-800"
                    }`}
                  >
                    {timeline.total_events}
                  </span>
                )}
              </button>
            </div>

            {/* Source Provenance Indicators */}
            {summary && (
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-600">
                <span className="px-2.5 py-1 bg-slate-100 rounded-lg border border-slate-200">
                  {summary.source_counts.interview_answers} Interview Responses
                </span>
                <span className="px-2.5 py-1 bg-slate-100 rounded-lg border border-slate-200">
                  {summary.source_counts.documents} Medical Documents
                </span>
                {summary.source_counts.triage_alerts > 0 && (
                  <span className="px-2.5 py-1 bg-rose-50 text-rose-800 rounded-lg border border-rose-200 font-bold">
                    {summary.source_counts.triage_alerts} Triage Alerts
                  </span>
                )}
                {timeline?.has_conflicts && (
                  <span className="px-2.5 py-1 bg-amber-50 text-amber-800 rounded-lg border border-amber-300 font-bold flex items-center space-x-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span>{timeline.conflict_count} Conflict(s) Detected</span>
                  </span>
                )}
              </div>
            )}
          </div>

          {/* TAB 1: 14-SECTION CLINICAL SUMMARY */}
          {activeTab === "summary" && summary && (
            <div className="space-y-6">
              {/* Expand / Collapse All Controls */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs text-slate-500 font-medium">
                  <Sparkles className="w-4 h-4 text-teal-600" />
                  <span>
                    Physician-ready structured clinical history synthesized strictly from real patient records.
                  </span>
                </div>

                <button
                  type="button"
                  onClick={toggleAllSections}
                  className="text-xs font-bold text-teal-700 hover:text-teal-900 flex items-center space-x-1 transition"
                >
                  {allExpanded ? (
                    <>
                      <ChevronUp className="w-3.5 h-3.5" />
                      <span>Collapse All</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3.5 h-3.5" />
                      <span>Expand All</span>
                    </>
                  )}
                </button>
              </div>

              {/* Sections Accordion */}
              <div className="space-y-4">
                {orderedSections.map((sec) => {
                  const isExpanded = expandedSections[sec.section_id] ?? true;
                  const isSectionUnavailable = !sec.is_available;
                  const isRedFlagSection = sec.section_id === "red_flags_triage" && sec.is_available;
                  const isConflictSection = sec.section_id === "requires_verification" && sec.is_available;

                  return (
                    <div
                      key={sec.section_id}
                      className={`border-2 rounded-2xl transition shadow-xs overflow-hidden ${
                        isRedFlagSection
                          ? "border-rose-300 bg-rose-50/40"
                          : isConflictSection
                          ? "border-amber-300 bg-amber-50/40"
                          : isSectionUnavailable
                          ? "border-slate-200 bg-slate-50/50"
                          : "border-slate-200 bg-white hover:border-teal-300"
                      }`}
                    >
                      {/* Section Header */}
                      <button
                        type="button"
                        onClick={() => toggleSection(sec.section_id)}
                        className="w-full px-5 py-4 flex items-center justify-between text-left focus:outline-none"
                      >
                        <div className="flex items-center space-x-3">
                          <span
                            className={`w-7 h-7 rounded-lg flex items-center justify-center font-black text-xs ${
                              isRedFlagSection
                                ? "bg-rose-600 text-white"
                                : isConflictSection
                                ? "bg-amber-600 text-white"
                                : isSectionUnavailable
                                ? "bg-slate-200 text-slate-600"
                                : "bg-teal-600 text-white"
                            }`}
                          >
                            {sec.section_number}
                          </span>
                          <div>
                            <h4
                              className={`text-sm sm:text-base font-bold ${
                                isRedFlagSection
                                  ? "text-rose-950"
                                  : isConflictSection
                                  ? "text-amber-950"
                                  : "text-slate-900"
                              }`}
                            >
                              {sec.title}
                            </h4>
                            <div className="flex flex-wrap items-center gap-2 mt-0.5">
                              {isSectionUnavailable ? (
                                <span className="text-[11px] font-semibold text-slate-400 italic">
                                  Not available in provided history/documents
                                </span>
                              ) : (
                                sec.source_references.map((src, i) => (
                                  <span
                                    key={i}
                                    className="text-[10px] font-bold px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md border border-slate-200"
                                  >
                                    {src}
                                  </span>
                                ))
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center space-x-2">
                          {isExpanded ? (
                            <ChevronUp className="w-5 h-5 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-slate-400" />
                          )}
                        </div>
                      </button>

                      {/* Section Content */}
                      {isExpanded && (
                        <div className="px-5 pb-5 pt-1 border-t border-slate-100">
                          {isSectionUnavailable ? (
                            <p className="text-xs sm:text-sm text-slate-400 italic font-mono bg-slate-100/60 p-3 rounded-xl">
                              {sec.content}
                            </p>
                          ) : (
                            <div className="space-y-3">
                              <p className="text-xs sm:text-sm text-slate-800 whitespace-pre-line leading-relaxed font-sans">
                                {sec.content}
                              </p>

                              {/* Structured Items Cards if present */}
                              {sec.items && sec.items.length > 0 && (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2">
                                  {sec.items.map((it, idx) => (
                                    <div
                                      key={idx}
                                      className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs space-y-1"
                                    >
                                      {it.drug_name && (
                                        <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                                          <Pill className="w-3.5 h-3.5 text-teal-600" />
                                          <span>{it.drug_name}</span>
                                        </div>
                                      )}
                                      {it.dosage && (
                                        <div className="text-slate-600">
                                          Dosage: <span className="font-semibold">{it.dosage}</span>
                                        </div>
                                      )}
                                      {it.frequency && (
                                        <div className="text-slate-600">
                                          Frequency: <span className="font-semibold">{it.frequency}</span>
                                        </div>
                                      )}
                                      {it.test_name && (
                                        <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                                          <Activity className="w-3.5 h-3.5 text-blue-600" />
                                          <span>{it.test_name}</span>
                                        </div>
                                      )}
                                      {it.result_value && (
                                        <div
                                          className={`font-semibold ${
                                            it.is_abnormal ? "text-rose-700 font-bold" : "text-slate-700"
                                          }`}
                                        >
                                          Result: {it.result_value} {it.unit || ""}{" "}
                                          {it.is_abnormal ? "(ABNORMAL)" : ""}
                                        </div>
                                      )}
                                      {it.reference_range && (
                                        <div className="text-slate-500 text-[11px]">
                                          Ref Range: {it.reference_range}
                                        </div>
                                      )}
                                      {it.allergen && (
                                        <div className="font-bold text-amber-900 flex items-center space-x-1.5">
                                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                                          <span>{it.allergen}</span>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Raw Physician Draft Preview Box */}
              <div className="bg-slate-900 text-slate-100 rounded-3xl p-6 space-y-3 shadow-md">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-teal-400" />
                    <h4 className="font-mono font-bold text-sm text-teal-400 uppercase tracking-wider">
                      Physician-Ready Narrative Draft (Full Text)
                    </h4>
                  </div>
                  <button
                    type="button"
                    onClick={handleCopySummary}
                    className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold transition flex items-center space-x-1.5"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? "Copied!" : "Copy Full Draft"}</span>
                  </button>
                </div>
                <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto pr-2">
                  {summary.summary_draft}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 2: CHRONOLOGICAL MEDICAL TIMELINE */}
          {activeTab === "timeline" && timeline && (
            <div className="space-y-6">
              {/* Conflicts Callout if present */}
              {timeline.has_conflicts && (
                <div className="bg-amber-50 border-2 border-amber-300 text-amber-950 rounded-2xl p-4 flex items-start space-x-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <strong className="block font-black text-amber-900 text-sm">
                      Clinical Contradiction Detected ({timeline.conflict_count} Discrepancy)
                    </strong>
                    <p className="text-xs text-amber-800 leading-relaxed">
                      MediKiosk has identified conflicting data between patient interview responses and
                      uploaded documents. To ensure diagnostic safety, conflicting records are flagged below
                      with:{" "}
                      <code className="bg-amber-100 px-1 py-0.5 rounded text-amber-900 font-bold">
                        Conflicting information — physician verification required.
                      </code>
                    </p>
                  </div>
                </div>
              )}

              {/* DATED EVENTS (Chronological Descending) */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4 text-teal-600" />
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                    Dated Events ({timeline.dated_events.length}) — Sorted Chronologically (Newest First)
                  </h3>
                </div>

                {timeline.dated_events.length === 0 ? (
                  <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 text-center text-xs text-slate-500 italic">
                    No events with specific calendar dates found. See undated events below.
                  </div>
                ) : (
                  <div className="relative pl-6 sm:pl-8 border-l-2 border-teal-500/40 space-y-4 my-2">
                    {timeline.dated_events.map((ev) => (
                      <div key={ev.event_id} className="relative group">
                        {/* Timeline Node Icon */}
                        <div className="absolute -left-[31px] sm:-left-[39px] top-3.5 w-4 h-4 rounded-full bg-teal-600 border-2 border-white shadow-xs" />

                        {/* Event Card */}
                        <div
                          className={`border-2 rounded-2xl p-4 transition shadow-xs space-y-2 ${
                            ev.is_conflict
                              ? "border-amber-400 bg-amber-50/50"
                              : ev.event_type === "triage_alert"
                              ? "border-rose-300 bg-rose-50/40"
                              : "border-slate-200 bg-white hover:border-teal-300"
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              {/* Date Badge */}
                              <span className="px-2.5 py-0.5 rounded-md font-mono text-xs font-bold bg-slate-900 text-white shadow-xs">
                                {ev.display_date}
                              </span>

                              {/* Event Type Badge */}
                              <span
                                className={`px-2.5 py-0.5 rounded-md text-xs font-bold border ${getEventTypeBadgeColor(
                                  ev.event_type
                                )}`}
                              >
                                {formatEventType(ev.event_type)}
                              </span>

                              {/* Source Provenance Badge */}
                              <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                                {ev.source_label}
                              </span>
                            </div>

                            {/* Verification Status */}
                            <span className="text-[11px] font-bold text-amber-700 bg-amber-100/80 px-2 py-0.5 rounded border border-amber-300 self-start sm:self-auto">
                              Needs Review
                            </span>
                          </div>

                          {/* Event Title */}
                          <h4 className="text-sm sm:text-base font-bold text-slate-900">{ev.title}</h4>

                          {/* Conflict Callout inside event */}
                          {ev.is_conflict && ev.conflict_notes && (
                            <div className="bg-amber-100 border border-amber-300 text-amber-950 p-2.5 rounded-xl text-xs font-semibold flex items-start space-x-2">
                              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                              <span>{ev.conflict_notes}</span>
                            </div>
                          )}

                          {/* Details Metadata */}
                          {ev.details && Object.keys(ev.details).length > 0 && (
                            <div className="text-xs text-slate-600 bg-slate-50 rounded-xl p-2.5 space-y-1">
                              {Object.entries(ev.details).map(([k, v]) => (
                                <div key={k} className="flex items-center space-x-1.5">
                                  <span className="font-semibold text-slate-500 capitalize">
                                    {k.replace(/_/g, " ")}:
                                  </span>
                                  <span className="text-slate-800 font-mono">
                                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* UNDATED EVENTS SECTION (Zero Date Guessing Guard) */}
              <div className="space-y-3 pt-4 border-t border-slate-200">
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-slate-500" />
                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                      Events With Unspecified Date ({timeline.undated_events.length})
                    </h3>
                    <p className="text-xs text-slate-500">
                      Isolated under <em>&quot;Date not specified&quot;</em>. MediKiosk enforces a zero-guessing policy
                      to prevent clinical chronological errors.
                    </p>
                  </div>
                </div>

                {timeline.undated_events.length === 0 ? (
                  <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-center text-xs text-slate-400 italic">
                    No undated events.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {timeline.undated_events.map((ev) => (
                      <div
                        key={ev.event_id}
                        className={`border-2 rounded-2xl p-4 transition shadow-xs space-y-2 ${
                          ev.is_conflict
                            ? "border-amber-400 bg-amber-50/50"
                            : "border-slate-200 bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-slate-200 text-slate-700">
                            Date not specified
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getEventTypeBadgeColor(
                              ev.event_type
                            )}`}
                          >
                            {formatEventType(ev.event_type)}
                          </span>
                        </div>

                        <h5 className="text-xs sm:text-sm font-bold text-slate-900">{ev.title}</h5>

                        {ev.is_conflict && ev.conflict_notes && (
                          <div className="bg-amber-100 border border-amber-300 text-amber-950 p-2 rounded-lg text-[11px] font-semibold">
                            {ev.conflict_notes}
                          </div>
                        )}

                        <div className="text-[11px] text-slate-500 font-medium">
                          Source: {ev.source_label}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SummaryPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-2xl mx-auto py-16 text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-sm text-slate-600">Loading Medical Summary Portal...</p>
        </div>
      }
    >
      <SummaryContent />
    </Suspense>
  );
}
