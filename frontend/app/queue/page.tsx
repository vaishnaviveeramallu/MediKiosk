"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Users,
  Search,
  RefreshCw,
  UserPlus,
  Clock,
  CheckCircle,
  AlertCircle,
  ArrowLeft,
  ChevronRight,
  Filter,
  Phone,
  ShieldCheck,
  ShieldAlert,
  Stethoscope,
  FileCheck,
  FileText,
  ClipboardList,
} from "lucide-react";

interface Patient {
  id: string;
  token_number: string;
  full_name: string;
  age: number;
  gender: string;
  phone_number: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  address_city?: string;
  address_state?: string;
  initial_complaint?: string;
  registration_status: string;
  created_at: string;
  selected_language?: string;
  consent_status?: string;
  consent_timestamp?: string;
}

export default function QueuePage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const fetchPatients = useCallback(async () => {
    try {
      setError(null);
      const url = search.trim()
        ? `http://127.0.0.1:8000/api/patients?search=${encodeURIComponent(search.trim())}`
        : "http://127.0.0.1:8000/api/patients";

      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to fetch patients (${res.status})`);
      }
      const data: Patient[] = await res.json();
      setPatients(data);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError("Could not load OPD queue. Check if backend is running at http://127.0.0.1:8000.");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchPatients();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchPatients]);

  return (
    <div className="max-w-6xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link
            href="/"
            className="inline-flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 text-sm font-semibold transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Home</span>
          </Link>
          <div className="flex items-center space-x-3 mt-2">
            <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                OPD Patient Queue
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 font-medium">
                लाइव ओपीडी कतार • Real-time patient registrations from MongoDB
              </p>
            </div>
          </div>
        </div>

        {/* Right Header Buttons */}
        <div className="flex items-center space-x-3">
          <Link
            href="/register"
            className="flex items-center space-x-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-bold shadow-sm transition"
          >
            <UserPlus className="w-4 h-4" />
            <span>New Registration</span>
          </Link>

          <button
            onClick={() => {
              setLoading(true);
              fetchPatients();
            }}
            className="flex items-center space-x-1.5 px-3 py-2.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-medium shadow-sm transition"
            title="Refresh patient list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-600" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Control Bar: Search & Status */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, token (MK-...), or phone..."
            className="w-full pl-11 pr-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:border-teal-600 transition"
          />
        </div>

        {/* Status Indicators */}
        <div className="flex items-center space-x-4 text-xs text-slate-600 justify-between md:justify-end">
          <label className="flex items-center space-x-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-teal-600 rounded focus:ring-teal-500 border-slate-300"
            />
            <span className="font-medium">Auto-refresh (5s)</span>
          </label>

          <div className="flex items-center space-x-1 text-slate-400 font-mono">
            <Clock className="w-3.5 h-3.5" />
            <span>Updated: {lastUpdated.toLocaleTimeString()}</span>
          </div>

          <span className="bg-slate-100 text-slate-800 font-bold px-3 py-1 rounded-lg border border-slate-200">
            Total: {patients.length}
          </span>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-rose-50 border border-rose-300 rounded-2xl p-4 flex items-center space-x-3 text-rose-900 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {/* Main Queue List / Cards */}
      {loading && patients.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center space-y-3">
          <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-slate-600 font-medium">Fetching real-time queue from database...</p>
        </div>
      ) : patients.length === 0 ? (
        /* Genuine Empty State (ZERO MOCK DATA) */
        <div className="bg-white border-2 border-dashed border-slate-300 rounded-3xl p-12 text-center space-y-4">
          <div className="w-16 h-16 bg-slate-100 text-slate-400 rounded-2xl flex items-center justify-center mx-auto">
            <Users className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h3 className="text-xl font-bold text-slate-800">
              No Patients in Queue
            </h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              There are currently no patients registered in the database. All records must originate from genuine patient registration sessions.
            </p>
          </div>
          <div className="pt-2">
            <Link
              href="/register"
              className="inline-flex items-center space-x-2 px-6 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-bold text-sm shadow-md transition"
            >
              <UserPlus className="w-4 h-4" />
              <span>Register First Patient</span>
            </Link>
          </div>
        </div>
      ) : (
        /* Real Dynamic Patient Records */
        <div className="space-y-3">
          {patients.map((patient, index) => (
            <div
              key={patient.id}
              className="bg-white border border-slate-200 hover:border-teal-400 rounded-2xl p-5 shadow-sm transition hover:shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              {/* Left Column: Token + Patient Identity */}
              <div className="flex items-start sm:items-center space-x-4">
                {/* Token Badge */}
                <div className="bg-teal-50 border border-teal-300 rounded-xl px-4 py-2 text-center flex-shrink-0">
                  <span className="block text-[10px] uppercase font-bold text-teal-800 tracking-wider">
                    OPD Token
                  </span>
                  <span className="font-mono text-lg font-black text-teal-900">
                    {patient.token_number}
                  </span>
                </div>

                {/* Patient Details */}
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-lg font-bold text-slate-900">
                      {patient.full_name}
                    </h3>
                    <span className="text-xs bg-slate-100 text-slate-700 font-semibold px-2 py-0.5 rounded-md">
                      {patient.age} yrs • {patient.gender}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1">
                    <span className="flex items-center space-x-1 font-mono">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      <span>+91 {patient.phone_number}</span>
                    </span>

                    {patient.address_city && (
                      <span>
                        • {patient.address_city}
                        {patient.address_state ? `, ${patient.address_state}` : ""}
                      </span>
                    )}

                    <span className="flex items-center space-x-1 text-slate-400">
                      <Clock className="w-3.5 h-3.5" />
                      <span>
                        {new Date(patient.created_at).toLocaleTimeString("en-IN", {
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: true,
                        })}
                      </span>
                    </span>
                  </div>

                  {/* Complaint */}
                  {patient.initial_complaint && (
                    <p className="text-xs text-slate-700 font-medium mt-2 bg-slate-50 border border-slate-100 p-2 rounded-lg inline-block">
                      <strong className="text-slate-500 font-semibold">Chief Symptom:</strong>{" "}
                      {patient.initial_complaint}
                    </p>
                  )}
                </div>
              </div>

              {/* Right Column: Consent Status, Interview Status & Actions */}
              <div className="flex flex-wrap items-center justify-between md:justify-end gap-2.5 pt-3 md:pt-0 border-t md:border-t-0 border-slate-100">
                {/* 1. Consent Status Badge */}
                {patient.consent_status === "granted" ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Consent: Granted ({patient.selected_language === "hi" ? "हिन्दी" : "English"})</span>
                  </span>
                ) : patient.consent_status === "declined" ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300">
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
                    <span>Consent: Declined</span>
                  </span>
                ) : (
                  <Link
                    href={`/consent?patientId=${patient.id}`}
                    className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold border border-slate-300 transition flex items-center space-x-1"
                  >
                    <span>Give Consent</span>
                    <ChevronRight className="w-3 h-3" />
                  </Link>
                )}

                {/* 2. Clinical Interview Action / Status */}
                {patient.registration_status === "interview_completed" ? (
                  <Link
                    href={`/interview?patientId=${patient.id}`}
                    className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold bg-teal-50 text-teal-800 border border-teal-300 hover:bg-teal-100 transition"
                  >
                    <FileCheck className="w-3.5 h-3.5 text-teal-600" />
                    <span>View Intake</span>
                  </Link>
                ) : patient.registration_status === "interview_in_progress" ? (
                  <Link
                    href={`/interview?patientId=${patient.id}`}
                    className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white shadow-sm transition"
                  >
                    <Stethoscope className="w-3.5 h-3.5" />
                    <span>Resume Intake</span>
                    <ChevronRight className="w-3 h-3" />
                  </Link>
                ) : patient.consent_status === "granted" ? (
                  <Link
                    href={`/interview?patientId=${patient.id}`}
                    className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white shadow-sm transition"
                  >
                    <Stethoscope className="w-3.5 h-3.5" />
                    <span>Start Intake</span>
                    <ChevronRight className="w-3 h-3" />
                  </Link>
                ) : null}

                {/* 3. Medical Documents Action */}
                <Link
                  href={`/documents?patientId=${patient.id}`}
                  className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold bg-slate-100 hover:bg-teal-50 hover:text-teal-700 text-slate-700 border border-slate-200 transition"
                  title="Upload or view medical documents"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Docs</span>
                </Link>

                {/* 4. Clinical Summary & Timeline Action */}
                <Link
                  href={`/summary?patientId=${patient.id}`}
                  className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition"
                  title="View Medical Timeline and AI Clinical Summary"
                >
                  <ClipboardList className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Summary</span>
                </Link>

                <span className="text-[11px] font-mono text-slate-400" title={`ID: ${patient.id}`}>
                  #{patient.id.slice(-6)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
