"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Stethoscope,
  CheckCircle2,
  AlertTriangle,
  Clock,
  User,
  Phone,
  FileText,
  ClipboardList,
  ShieldCheck,
  ShieldAlert,
  Calendar,
  Pill,
  Activity,
  Printer,
  Edit3,
  Save,
  X,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  History,
  Lock,
  Eye,
  Check,
  Sparkles,
  Info,
  FolderOpen,
} from "lucide-react";
import { getAuthHeaders } from "@/lib/auth";

interface PatientClinicalDetail {
  patient: Record<string, any>;
  interview: {
    session_id?: string | null;
    status: string;
    started_at?: string | null;
    completed_at?: string | null;
    answered_count: number;
    answers: Array<{
      question_id: string;
      question_text: string;
      patient_answer: string;
      section: string;
      answered_at: string;
      input_method: string;
      skipped: boolean;
    }>;
  };
  triage_alerts: Array<{
    alert_id: string;
    category: string;
    priority: string;
    triggering_answer: string;
    detected_at: string;
    status: string;
    staff_acknowledged: boolean;
  }>;
  documents: Array<{
    document_id: string;
    original_filename: string;
    document_type: string;
    file_size: number;
    uploaded_at: string;
    processing_status: string;
    ocr_status?: string;
    verification_status: string;
    has_ocr: boolean;
    notes?: string;
  }>;
  ocr_extracted: {
    diagnoses: Array<any>;
    medications: Array<any>;
    investigations: Array<any>;
    procedures: Array<any>;
    allergies: Array<any>;
    unclear_findings: Array<any>;
  };
  timeline: {
    total_events: number;
    dated_events: Array<any>;
    undated_events: Array<any>;
    has_conflicts: boolean;
    conflict_count: number;
  };
  summary: {
    patient_id: string;
    token_number: string;
    summary_draft: string;
    sections: Record<string, any>;
    disclaimer: string;
    verification_status: string;
    generated_at: string;
    confirmed_by?: string;
    confirmed_at?: string;
    source_counts: Record<string, number>;
  };
  conflicts: Array<{
    event_id: string;
    title: string;
    notes: string;
    source: string;
    requires_physician_verification: boolean;
  }>;
  review_info: {
    doctor_review_status: string;
    physician_reviewed: boolean;
    physician_reviewed_at?: string | null;
    physician_confirmed: boolean;
    physician_confirmed_at?: string | null;
    confirmed_by?: string | null;
    physician_notes?: string | null;
    version_history: Array<{
      version: number;
      summary_draft: string;
      modified_at: string;
      modified_by: string;
      reason?: string;
    }>;
    original_ai_draft?: string | null;
  };
  ayush_history?: {
    has_ayush_history: boolean;
    total_ayush_answers: number;
    structured_data: any;
    answers: any[];
  } | null;
}

function PatientReviewContent() {
  const params = useParams();
  const router = useRouter();
  const patientId = (params?.patientId as string) || "";

  const [dossier, setDossier] = useState<PatientClinicalDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Editing State
  const [isEditingSummary, setIsEditingSummary] = useState<boolean>(false);
  const [editedDraft, setEditedDraft] = useState<string>("");
  const [physicianNotes, setPhysicianNotes] = useState<string>("");
  const [savingEdit, setSavingEdit] = useState<boolean>(false);

  // Verification Modal State
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [confirmDoctorNotes, setConfirmDoctorNotes] = useState<string>("");
  const [confirming, setConfirming] = useState<boolean>(false);

  // Active section accordions
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    profile: true,
    interview: true,
    triage: true,
    documents: true,
    ocr: true,
    timeline: true,
    conflicts: true,
    summary: true,
    ayush: true,
  });

  // History Drawer State
  const [showVersionHistory, setShowVersionHistory] = useState<boolean>(false);

  const fetchDossier = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/doctor/patients/${encodeURIComponent(patientId)}`, {
        cache: "no-store",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`Failed to load patient clinical dossier (${res.status})`);
      }
      const data: PatientClinicalDetail = await res.json();
      setDossier(data);
      setEditedDraft(data.summary?.summary_draft || "");
      setPhysicianNotes(data.review_info?.physician_notes || "");
    } catch (err: any) {
      setError(err.message || "Failed to load clinical dossier.");
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    fetchDossier();
  }, [fetchDossier]);

  const toggleSection = (sec: string) => {
    setExpandedSections((prev) => ({ ...prev, [sec]: !prev[sec] }));
  };

  const handleSaveDraft = async () => {
    if (!patientId) return;
    setSavingEdit(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/doctor/patients/${encodeURIComponent(patientId)}/summary`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          summary_draft: editedDraft,
          physician_notes: physicianNotes,
          doctor_name: "Attending Physician",
        }),
      });
      if (!res.ok) {
        throw new Error("Failed to save summary draft edits.");
      }
      setIsEditingSummary(false);
      await fetchDossier();
    } catch (err: any) {
      alert(err.message || "Could not save draft edit.");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleConfirmSummary = async () => {
    if (!patientId) return;
    setConfirming(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/doctor/patients/${encodeURIComponent(patientId)}/summary/confirm`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          doctor_notes: confirmDoctorNotes,
          confirmed_by: "Attending Physician",
        }),
      });
      if (!res.ok) {
        throw new Error("Failed to confirm clinical summary.");
      }
      setShowConfirmModal(false);
      await fetchDossier();
    } catch (err: any) {
      alert(err.message || "Could not confirm clinical summary.");
    } finally {
      setConfirming(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!patientId) return;
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/doctor/patients/${encodeURIComponent(patientId)}/review-status`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({ review_status: newStatus }),
      });
      if (!res.ok) {
        throw new Error("Failed to update status.");
      }
      await fetchDossier();
    } catch (err: any) {
      alert(err.message || "Could not update review status.");
    }
  };

  if (loading && !dossier) {
    return (
      <div className="max-w-4xl mx-auto py-24 text-center space-y-4">
        <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-base font-bold text-slate-800">
          Loading 8-Section Clinical Dossier for Attending Physician...
        </p>
      </div>
    );
  }

  if (error || !dossier) {
    return (
      <div className="max-w-3xl mx-auto py-16 space-y-4">
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-6 flex items-start space-x-3">
          <AlertTriangle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h3 className="font-bold text-base">Error Loading Dossier</h3>
            <p className="text-sm">{error || "Patient not found."}</p>
          </div>
        </div>
        <Link
          href="/doctor"
          className="inline-flex items-center space-x-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-bold transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Doctor Dashboard</span>
        </Link>
      </div>
    );
  }

  const p = dossier.patient;
  const isConfirmed = dossier.review_info?.physician_confirmed || dossier.summary?.verification_status === "physician_confirmed";

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20">
      {/* 1. TOP STICKY CLINICAL ACTIONS BAR */}
      <div className="sticky top-2 z-20 bg-slate-900/95 backdrop-blur-md text-white border border-slate-800 rounded-3xl p-4 sm:p-5 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Identity + Breadcrumb */}
        <div className="flex items-center space-x-3">
          <Link
            href="/doctor"
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition flex-shrink-0"
            title="Back to Doctor Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-black text-lg sm:text-xl text-white">{p.full_name}</span>
              <span className="px-2.5 py-0.5 rounded-lg bg-teal-500/20 text-teal-300 border border-teal-500/40 font-mono font-bold text-xs">
                {p.token_number}
              </span>
              <span className="text-xs text-slate-400">
                {p.age}y &bull; {p.gender} &bull; {p.address_city || "City N/A"}
              </span>
            </div>

            {/* Review Status Pill */}
            <div className="flex items-center space-x-2 mt-1">
              {isConfirmed ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Physician Confirmed</span>
                </span>
              ) : dossier.review_info.doctor_review_status === "in_review" ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>In Review</span>
                </span>
              ) : dossier.review_info.doctor_review_status === "needs_verification" ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center space-x-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Needs Verification</span>
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-700 text-slate-300 border border-slate-600 flex items-center space-x-1">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span>Pending Review</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Quick Switchers */}
          {!isConfirmed && (
            <div className="flex items-center space-x-1 bg-slate-800 p-1 rounded-xl border border-slate-700 text-xs font-bold">
              <button
                type="button"
                onClick={() => handleStatusChange("in_review")}
                className={`px-2.5 py-1 rounded-lg transition ${
                  dossier.review_info.doctor_review_status === "in_review"
                    ? "bg-indigo-600 text-white"
                    : "text-slate-300 hover:text-white"
                }`}
              >
                In Review
              </button>
              <button
                type="button"
                onClick={() => handleStatusChange("needs_verification")}
                className={`px-2.5 py-1 rounded-lg transition ${
                  dossier.review_info.doctor_review_status === "needs_verification"
                    ? "bg-amber-600 text-white"
                    : "text-slate-300 hover:text-white"
                }`}
              >
                Needs Verif
              </button>
            </div>
          )}

          {/* Edit Summary Action */}
          {!isConfirmed && (
            <button
              type="button"
              onClick={() => setIsEditingSummary(!isEditingSummary)}
              className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold border transition flex items-center space-x-1.5 ${
                isEditingSummary
                  ? "bg-amber-500 text-slate-950 border-amber-400"
                  : "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700"
              }`}
            >
              <Edit3 className="w-3.5 h-3.5" />
              <span>{isEditingSummary ? "Editing..." : "Edit Summary"}</span>
            </button>
          )}

          {/* Confirm Button */}
          {!isConfirmed ? (
            <button
              type="button"
              onClick={() => setShowConfirmModal(true)}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs sm:text-sm font-bold shadow-md transition flex items-center space-x-1.5"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Verify & Confirm</span>
            </button>
          ) : (
            <span className="px-3.5 py-2 bg-emerald-950 text-emerald-300 border border-emerald-700 rounded-xl text-xs font-bold flex items-center space-x-1.5">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span>Confirmed & Locked</span>
            </span>
          )}

          {/* Print */}
          <button
            type="button"
            onClick={() => window.print()}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition"
            title="Print Clinical Case Sheet"
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* CONFIRMED LOCK BANNER */}
      {isConfirmed && (
        <div className="bg-emerald-50 border-2 border-emerald-300 text-emerald-950 rounded-2xl p-4 flex items-start space-x-3 shadow-xs">
          <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-black text-emerald-950 text-sm sm:text-base">
                PHYSICIAN VERIFIED & CONFIRMED CLINICAL SUMMARY
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-200 text-emerald-900">
                Final Case Sheet
              </span>
            </div>
            <p className="text-xs sm:text-sm text-emerald-800 leading-relaxed">
              This clinical history has been formally verified, reviewed, and signed off by the attending physician
              on {new Date(dossier.review_info.physician_confirmed_at || "").toLocaleString("en-IN")}.
              {dossier.review_info.physician_notes && (
                <span className="block font-semibold mt-1">Doctor Notes: &quot;{dossier.review_info.physician_notes}&quot;</span>
              )}
            </p>
          </div>
        </div>
      )}

      {/* 2. SECTION 1 — PATIENT PROFILE */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <User className="w-5 h-5 text-teal-600" />
            <h2 className="text-base sm:text-lg font-bold text-slate-900">Section 1: Patient Profile & Demographics</h2>
          </div>
          <span className="text-xs font-mono font-bold text-slate-400">Authentic Registration Intake</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs sm:text-sm">
          <div>
            <span className="text-slate-500 font-semibold block">Full Legal Name:</span>
            <span className="font-bold text-slate-900">{p.full_name}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">OPD Token:</span>
            <span className="font-mono font-bold text-teal-700">{p.token_number}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Age & Gender:</span>
            <span className="font-bold text-slate-900">{p.age} yrs &bull; {p.gender}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Phone Number:</span>
            <span className="font-mono font-bold text-slate-800">{p.phone_number}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Location:</span>
            <span className="font-bold text-slate-900">
              {p.address_city || "Not provided"}{p.address_state ? `, ${p.address_state}` : ""}
            </span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Preferred Language:</span>
            <span className="font-bold uppercase text-slate-900">{p.selected_language}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Consent Status:</span>
            <span className="font-bold text-emerald-700 capitalize">{p.consent_status}</span>
          </div>
          <div>
            <span className="text-slate-500 font-semibold block">Registered At:</span>
            <span className="font-bold text-slate-800">
              {new Date(p.created_at).toLocaleDateString("en-IN")}
            </span>
          </div>
        </div>

        {p.initial_complaint && (
          <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200 text-xs sm:text-sm">
            <span className="font-bold text-slate-700 block mb-0.5">Initial OPD Chief Complaint:</span>
            <p className="font-semibold text-slate-900">{p.initial_complaint}</p>
          </div>
        )}
      </div>

      {/* 3. SECTION 2 — CLINICAL INTERVIEW (VERBATIM Q&A) */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <ClipboardList className="w-5 h-5 text-teal-600" />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 2: Clinical Intake Interview ({dossier.interview.answers.length} Responses)
              </h2>
              <p className="text-xs text-slate-500">
                Authentic verbatim patient answers &bull; Displayed exactly as recorded &bull; Zero alteration
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => toggleSection("interview")}
            className="text-slate-400 hover:text-slate-600"
          >
            {expandedSections.interview ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {expandedSections.interview && (
          <div className="space-y-3">
            {dossier.interview.answers.length === 0 ? (
              <p className="text-xs text-slate-400 italic py-4 text-center">
                Patient has not completed the adaptive clinical interview yet.
              </p>
            ) : (
              dossier.interview.answers.map((ans, idx) => (
                <div
                  key={idx}
                  className="bg-slate-50/80 border border-slate-200 rounded-2xl p-4 text-xs sm:text-sm space-y-1.5"
                >
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span className="uppercase font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded">
                      {ans.section.replace(/_/g, " ")}
                    </span>
                    <span>
                      Q#{idx + 1} &bull; {ans.input_method === "voice" ? "Microphone Input" : "Text Input"} &bull; {new Date(ans.answered_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>

                  <div className="font-semibold text-slate-800">
                    <span className="font-bold text-slate-500">Question:</span> {ans.question_text}
                  </div>

                  <div className="font-bold text-teal-950 pl-3 border-l-3 border-teal-600 bg-white py-2 px-2.5 rounded-r-xl shadow-2xs">
                    <span className="font-semibold text-slate-500 text-xs">Patient Response: </span>
                    {ans.patient_answer}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* 4. SECTION 3 — RED FLAGS / TRIAGE */}
      <div
        className={`border-2 rounded-3xl p-6 shadow-xs space-y-4 transition ${
          dossier.triage_alerts.length > 0 ? "bg-rose-50/30 border-rose-300" : "bg-white border-slate-200"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <ShieldAlert
              className={`w-5 h-5 ${dossier.triage_alerts.length > 0 ? "text-rose-600" : "text-slate-400"}`}
            />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 3: Red Flags & Triage Alerts ({dossier.triage_alerts.length})
              </h2>
              <p className="text-xs text-slate-500">
                AI Triage Alert &mdash; Physician Safety Support Only &bull; Not a Medical Diagnosis
              </p>
            </div>
          </div>
        </div>

        {dossier.triage_alerts.length === 0 ? (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs sm:text-sm text-emerald-800 flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>No red-flag warning signs were triggered during clinical intake.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {dossier.triage_alerts.map((al) => (
              <div
                key={al.alert_id}
                className="p-4 bg-white border-2 border-rose-400 rounded-2xl shadow-xs space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="px-2.5 py-0.5 rounded-md font-black text-xs bg-rose-600 text-white uppercase tracking-wider">
                    {al.priority} PRIORITY ALERT
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    Detected: {new Date(al.detected_at).toLocaleString("en-IN")}
                  </span>
                </div>

                <div className="text-xs sm:text-sm">
                  <span className="font-bold text-slate-900">Category:</span>{" "}
                  <span className="capitalize text-rose-900 font-bold">{al.category.replace(/_/g, " ")}</span>
                </div>

                <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-900">
                  <span className="font-bold text-slate-700">Triggering Patient Statement:</span> &quot;{al.triggering_answer}&quot;
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 5. SECTION 4 — MEDICAL DOCUMENTS */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <FolderOpen className="w-5 h-5 text-teal-600" />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 4: Medical Documents ({dossier.documents.length})
              </h2>
              <p className="text-xs text-slate-500">
                Authentic uploaded clinical files &bull; Original viewers &bull; OCR status
              </p>
            </div>
          </div>
        </div>

        {dossier.documents.length === 0 ? (
          <p className="text-xs text-slate-400 italic py-4 text-center">
            No medical documents uploaded for this patient.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {dossier.documents.map((doc) => (
              <div
                key={doc.document_id}
                className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm line-clamp-1">{doc.original_filename}</h4>
                    <span className="text-[11px] font-mono text-slate-500">ID: {doc.document_id}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-800 uppercase">
                    {doc.document_type}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                  <span>Size: {(doc.file_size / 1024).toFixed(1)} KB</span>
                  <span>&bull; Uploaded: {new Date(doc.uploaded_at).toLocaleDateString("en-IN")}</span>
                </div>

                <div className="pt-1 flex items-center space-x-2">
                  <a
                    href={`http://127.0.0.1:8000/api/patients/${encodeURIComponent(patientId)}/documents/${doc.document_id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-lg text-xs font-bold transition flex items-center space-x-1"
                  >
                    <ExternalLink className="w-3 h-3 text-slate-500" />
                    <span>View Original File</span>
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 6. SECTION 5 — OCR EXTRACTED INFORMATION */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <Activity className="w-5 h-5 text-teal-600" />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 5: OCR Extracted Medical Information
              </h2>
              <p className="text-xs text-slate-500">
                Structured clinical entities extracted from documents &bull; Uncertain items marked &quot;Needs verification&quot;
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => toggleSection("ocr")}
            className="text-slate-400 hover:text-slate-600"
          >
            {expandedSections.ocr ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {expandedSections.ocr && (
          <div className="space-y-4">
            {/* Medications */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <Pill className="w-3.5 h-3.5 text-teal-600" />
                <span>Extracted Medications ({dossier.ocr_extracted.medications.length})</span>
              </h4>
              {dossier.ocr_extracted.medications.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No medications extracted from documents.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {dossier.ocr_extracted.medications.map((m, idx) => (
                    <div key={idx} className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs space-y-1">
                      <div className="font-bold text-slate-900">{m.name}</div>
                      <div className="text-slate-600">
                        {m.dosage && <span className="mr-2">Dose: <strong>{m.dosage}</strong></span>}
                        {m.frequency && <span className="mr-2">Freq: <strong>{m.frequency}</strong></span>}
                        {m.duration && <span>Duration: <strong>{m.duration}</strong></span>}
                      </div>
                      <div className="text-[10px] text-slate-400">Source: {m.source_document}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Investigations */}
            <div className="pt-2 border-t border-slate-100">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                <Activity className="w-3.5 h-3.5 text-blue-600" />
                <span>Extracted Investigations / Lab Results ({dossier.ocr_extracted.investigations.length})</span>
              </h4>
              {dossier.ocr_extracted.investigations.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No lab investigations extracted from documents.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {dossier.ocr_extracted.investigations.map((inv, idx) => (
                    <div key={idx} className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs space-y-1">
                      <div className="font-bold text-slate-900">{inv.test_name}</div>
                      <div className="text-slate-700">
                        Result: <strong>{inv.result_value} {inv.unit || ""}</strong>
                        {inv.is_abnormal && <span className="ml-2 text-rose-700 font-bold">[ABNORMAL]</span>}
                      </div>
                      {inv.reference_range && <div className="text-slate-500 text-[11px]">Ref: {inv.reference_range}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Diagnoses & Allergies */}
            <div className="pt-2 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                  Extracted Diagnoses ({dossier.ocr_extracted.diagnoses.length})
                </h4>
                {dossier.ocr_extracted.diagnoses.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">None documented in records.</p>
                ) : (
                  <ul className="space-y-1 text-xs text-slate-800">
                    {dossier.ocr_extracted.diagnoses.map((d, i) => (
                      <li key={i} className="p-2 bg-slate-50 rounded-lg border border-slate-200 font-semibold">
                        &bull; {d.diagnosis} <span className="text-[10px] text-slate-400 font-normal">({d.source_document})</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                  Extracted Allergies ({dossier.ocr_extracted.allergies.length})
                </h4>
                {dossier.ocr_extracted.allergies.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">None documented in records.</p>
                ) : (
                  <ul className="space-y-1 text-xs">
                    {dossier.ocr_extracted.allergies.map((a, i) => (
                      <li key={i} className="p-2 bg-amber-50 border border-amber-200 rounded-lg font-bold text-amber-950">
                        &bull; {a.allergen} {a.reaction ? `(${a.reaction})` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 7. SECTION 6 — MEDICAL TIMELINE */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <Clock className="w-5 h-5 text-teal-600" />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 6: Chronological Medical Timeline ({dossier.timeline.total_events} Events)
              </h2>
              <p className="text-xs text-slate-500">
                Chronological dated events (newest first) &bull; Undated events under &quot;Date not specified&quot;
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => toggleSection("timeline")}
            className="text-slate-400 hover:text-slate-600"
          >
            {expandedSections.timeline ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>

        {expandedSections.timeline && (
          <div className="space-y-4">
            {dossier.timeline.dated_events.length > 0 && (
              <div className="relative pl-6 border-l-2 border-teal-400/40 space-y-3">
                {dossier.timeline.dated_events.map((ev, idx) => (
                  <div key={idx} className="relative group">
                    <div className="absolute -left-[31px] top-2 w-3.5 h-3.5 rounded-full bg-teal-600 border-2 border-white" />
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                          {ev.display_date}
                        </span>
                        <span className="font-semibold text-slate-500">{ev.source_label}</span>
                      </div>
                      <h5 className="font-bold text-slate-900 text-sm">{ev.title}</h5>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {dossier.timeline.undated_events.length > 0 && (
              <div className="pt-2 border-t border-slate-100 space-y-2">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block">
                  Events with unspecified date ({dossier.timeline.undated_events.length})
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {dossier.timeline.undated_events.map((ev, i) => (
                    <div key={i} className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>Date not specified</span>
                        <span>{ev.source_label}</span>
                      </div>
                      <h5 className="font-bold text-slate-800">{ev.title}</h5>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 8. SECTION 7 — CROSS-SOURCE CONFLICTS */}
      <div
        className={`border-2 rounded-3xl p-6 shadow-xs space-y-4 transition ${
          dossier.conflicts.length > 0 ? "bg-amber-50/40 border-amber-300" : "bg-white border-slate-200"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <AlertCircle
              className={`w-5 h-5 ${dossier.conflicts.length > 0 ? "text-amber-600" : "text-slate-400"}`}
            />
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900">
                Section 7: Cross-Source Conflicts ({dossier.conflicts.length})
              </h2>
              <p className="text-xs text-slate-500">
                Clinical discrepancies detected between interview & documents &bull; Physician verification required
              </p>
            </div>
          </div>
        </div>

        {dossier.conflicts.length === 0 ? (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs sm:text-sm text-emerald-800 flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>No conflicting information detected between intake answers and documents.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {dossier.conflicts.map((c, idx) => (
              <div key={idx} className="p-4 bg-white border-2 border-amber-400 rounded-2xl shadow-xs space-y-1.5">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded font-black text-xs bg-amber-500 text-slate-950 uppercase">
                    Conflict &mdash; Physician Verification Required
                  </span>
                </div>
                <h4 className="font-bold text-slate-900 text-sm">{c.title}</h4>
                <p className="text-xs sm:text-sm text-amber-950 font-semibold leading-relaxed">
                  {c.notes}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SECTION 9 — AYUSH CLINICAL HISTORY & DASHAVIDHA PARIKSHA */}
      {dossier.ayush_history?.has_ayush_history && (
        <div className="bg-white border-2 border-emerald-300 rounded-3xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-emerald-100 pb-3">
            <div className="flex items-center space-x-2.5">
              <span className="text-xl">🌿</span>
              <div>
                <h2 className="text-base sm:text-lg font-bold text-emerald-950">
                  Section 9: AYUSH Clinical History &amp; Dashavidha Pariksha
                </h2>
                <p className="text-xs text-emerald-700">
                  Classical Holistic Intake &bull; {dossier.ayush_history.total_ayush_answers} Patient Responses &bull; Strictly Non-Diagnostic
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => toggleSection("ayush")}
              className="text-slate-400 hover:text-slate-600"
            >
              {expandedSections.ayush ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          </div>

          {expandedSections.ayush && (
            <div className="space-y-4 text-xs">
              {/* Dashavidha Pariksha 10-Fold Assessment Matrix */}
              <div className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-900 text-sm uppercase tracking-wide">
                    Dashavidha Pariksha (10-Fold Clinical Framework)
                  </span>
                  <span className="text-[11px] font-mono text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full font-bold">
                    Patient-Reported &bull; Physician Discretion
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                  {dossier.ayush_history.structured_data?.dashavidha_pariksha &&
                    Object.entries(dossier.ayush_history.structured_data.dashavidha_pariksha).map(([key, val]) => (
                      <div key={key} className="p-2.5 bg-white border border-emerald-200 rounded-xl space-y-0.5">
                        <span className="font-bold uppercase tracking-wider text-[10px] text-emerald-700 block">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="text-slate-800 font-medium">
                          {String(val || "Not evaluated")}
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Core AYUSH Parameters Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <span className="text-[10px] font-bold uppercase text-slate-500 block">Agni (Digestion)</span>
                  <span className="font-bold text-slate-800 text-xs">
                    {dossier.ayush_history.structured_data?.agni || "Not reported"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <span className="text-[10px] font-bold uppercase text-slate-500 block">Koshta (Bowel)</span>
                  <span className="font-bold text-slate-800 text-xs">
                    {dossier.ayush_history.structured_data?.koshta || "Not reported"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <span className="text-[10px] font-bold uppercase text-slate-500 block">Ahara (Diet)</span>
                  <span className="font-bold text-slate-800 text-xs">
                    {dossier.ayush_history.structured_data?.ahara || "Not reported"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <span className="text-[10px] font-bold uppercase text-slate-500 block">Nidra (Sleep)</span>
                  <span className="font-bold text-slate-800 text-xs">
                    {dossier.ayush_history.structured_data?.nidra || "Not reported"}
                  </span>
                </div>
              </div>

              {/* Verbatim AYUSH Responses */}
              {dossier.ayush_history.answers?.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                    Patient-Reported AYUSH Responses ({dossier.ayush_history.answers.length})
                  </span>
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {dossier.ayush_history.answers.map((ans, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span className="font-semibold text-teal-800">{ans.question_text}</span>
                          <span className="font-mono text-[10px]">{ans.section}</span>
                        </div>
                        <p className="font-bold text-slate-900 text-xs">{ans.patient_answer}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 9. SECTION 8 — AI CLINICAL SUMMARY & PHYSICIAN REVIEW */}
      <div className="bg-white border-2 border-slate-200 rounded-3xl p-6 shadow-md space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-5 h-5 text-teal-600" />
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base sm:text-lg font-bold text-slate-900">
                  Section 8: AI Clinical Summary & Physician Review
                </h2>
                {dossier.review_info.version_history.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowVersionHistory(!showVersionHistory)}
                    className="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
                  >
                    <History className="w-3.5 h-3.5" />
                    <span>Version History ({dossier.review_info.version_history.length})</span>
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-500">
                14 Standard Clinical Sections &bull; Editable by Attending Physician &bull; Audit Trail Preserved
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {!isConfirmed && !isEditingSummary && (
              <button
                type="button"
                onClick={() => setIsEditingSummary(true)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
              >
                <Edit3 className="w-3.5 h-3.5 text-slate-600" />
                <span>Edit Case Summary</span>
              </button>
            )}
          </div>
        </div>

        {/* Version History Drawer if toggled */}
        {showVersionHistory && dossier.review_info.version_history.length > 0 && (
          <div className="p-4 bg-slate-900 text-slate-100 rounded-2xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="font-mono text-xs font-bold uppercase text-teal-400">
                Summary Revision History (Audit Trail)
              </span>
              <button
                type="button"
                onClick={() => setShowVersionHistory(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1 text-xs">
              {dossier.review_info.version_history.map((vh, i) => (
                <div key={i} className="p-2.5 bg-slate-800 rounded-xl space-y-1">
                  <div className="flex items-center justify-between font-mono text-slate-400 text-[11px]">
                    <span className="font-bold text-teal-300">Revision #{vh.version}</span>
                    <span>{new Date(vh.modified_at).toLocaleString("en-IN")} by {vh.modified_by}</span>
                  </div>
                  <p className="text-slate-300 italic">{vh.reason || "Physician draft edit"}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* EDITING MODE VS VIEWING MODE */}
        {isEditingSummary ? (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3.5 text-xs text-amber-900 flex items-start space-x-2">
              <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <strong>Physician Editing Mode Active:</strong> You can edit the clinical narrative below.
                Clicking &quot;Save Draft&quot; persists your changes to MongoDB, preserves previous drafts in version history,
                and sets the review status to &quot;In Review&quot;.
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                Narrative Clinical Summary Draft (Editable):
              </label>
              <textarea
                rows={16}
                value={editedDraft}
                onChange={(e) => setEditedDraft(e.target.value)}
                className="w-full p-4 font-mono text-xs sm:text-sm bg-slate-50 border-2 border-slate-300 rounded-2xl focus:border-teal-600 focus:outline-none transition resize-y leading-relaxed"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                Physician Clinical Commentary / Notes:
              </label>
              <input
                type="text"
                value={physicianNotes}
                onChange={(e) => setPhysicianNotes(e.target.value)}
                placeholder="e.g. Verified history with patient in OPD. Dosage confirmed. Advised endoscopy."
                className="w-full p-3 text-xs sm:text-sm bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setIsEditingSummary(false);
                  setEditedDraft(dossier.summary?.summary_draft || "");
                }}
                disabled={savingEdit}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs sm:text-sm font-bold transition"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSaveDraft}
                disabled={savingEdit}
                className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-xs sm:text-sm font-bold shadow-sm transition flex items-center space-x-1.5"
              >
                <Save className="w-4 h-4" />
                <span>{savingEdit ? "Saving..." : "Save Draft"}</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Structured Narrative Output */}
            <div className="bg-slate-900 text-slate-100 rounded-2xl p-6 shadow-inner space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                <span className="font-mono text-xs font-bold uppercase text-teal-400">
                  Physician Case Sheet Draft
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  Status: {dossier.summary?.verification_status || "needs_review"}
                </span>
              </div>
              <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-[500px] overflow-y-auto pr-2">
                {dossier.summary?.summary_draft}
              </pre>
            </div>

            {/* Verification Action Bar at bottom */}
            {!isConfirmed && (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="text-xs text-slate-600">
                  <span className="font-bold text-slate-900 block">Final Physician Verification:</span>
                  Review all 8 dimensions above before signing off on the case sheet.
                </div>

                <button
                  type="button"
                  onClick={() => setShowConfirmModal(true)}
                  className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-sm shadow-md transition flex items-center justify-center space-x-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Verify & Confirm Case Sheet</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 10. VERIFY & CONFIRM MODAL */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full space-y-5 shadow-2xl border-2 border-emerald-300 animate-in fade-in zoom-in-95 duration-150">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
              <CheckCircle2 className="w-7 h-7 text-emerald-600" />
            </div>

            <div className="space-y-1">
              <h3 className="text-xl font-black text-slate-900">
                Verify & Confirm Clinical Summary
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                Please verify that the information is accurate before confirming this clinical summary.
                Once confirmed, the case sheet will transition to <strong>Physician Confirmed</strong> status.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                Doctor Sign-Off Notes (Optional):
              </label>
              <textarea
                rows={3}
                value={confirmDoctorNotes}
                onChange={(e) => setConfirmDoctorNotes(e.target.value)}
                placeholder="e.g. Clinical history verified with patient in OPD. Diagnosis and plan confirmed."
                className="w-full p-3 text-xs sm:text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={confirming}
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs sm:text-sm font-bold transition"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleConfirmSummary}
                disabled={confirming}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs sm:text-sm font-bold shadow-md transition flex items-center space-x-1.5"
              >
                {confirming ? (
                  <span>Confirming...</span>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Confirm & Sign Off</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PatientReviewPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-4xl mx-auto py-24 text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-sm font-bold text-slate-700">Loading Clinical Dossier...</p>
        </div>
      }
    >
      <PatientReviewContent />
    </Suspense>
  );
}
