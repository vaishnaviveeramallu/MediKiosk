"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  UserPlus,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowLeft,
  ChevronRight,
  Sparkles,
  Phone,
  User,
  MapPin,
  FileText,
  Plus,
  Minus,
  Check,
  ShieldCheck,
} from "lucide-react";

interface RegisteredPatient {
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
  government_id_type?: string;
  government_id_number?: string;
  initial_complaint?: string;
  registration_status: string;
  created_at: string;
}

const COMMON_SYMPTOMS = [
  { label: "Fever", hindi: "बुखार" },
  { label: "Cough & Cold", hindi: "खांसी / जुकाम" },
  { label: "Body & Joint Pain", hindi: "बदन / जोड़ों में दर्द" },
  { label: "Stomach Pain", hindi: "पेट में दर्द" },
  { label: "Headache / Migraine", hindi: "सिरदर्द" },
  { label: "High BP / Diabetes Check", hindi: "बीपी / शुगर जांच" },
  { label: "Skin Rash / Allergy", hindi: "त्वचा एलर्जी" },
  { label: "Weakness / Dizziness", hindi: "कमज़ोरी / चक्कर" },
];

export default function RegisterPage() {
  // Form State
  const [fullName, setFullName] = useState("");
  const [age, setAge] = useState<number>(30);
  const [gender, setGender] = useState("Male");
  const [phone, setPhone] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [govIdType, setGovIdType] = useState("Aadhaar");
  const [govIdNumber, setGovIdNumber] = useState("");
  const [initialComplaint, setInitialComplaint] = useState("");

  // Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [registeredPatient, setRegisteredPatient] = useState<RegisteredPatient | null>(null);

  const handleSymptomClick = (symptom: string) => {
    if (initialComplaint.includes(symptom)) {
      // Remove
      const updated = initialComplaint
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s && s !== symptom)
        .join(", ");
      setInitialComplaint(updated);
    } else {
      // Add
      if (initialComplaint.trim()) {
        setInitialComplaint(`${initialComplaint.trim()}, ${symptom}`);
      } else {
        setInitialComplaint(symptom);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Frontend validation
    if (!fullName.trim() || fullName.trim().length < 2) {
      setErrorMessage("Please enter the patient's full name (at least 2 characters).");
      return;
    }

    const cleanPhone = phone.replace(/\D/g, "");
    if (cleanPhone.length !== 10) {
      setErrorMessage("Please enter a valid 10-digit mobile number.");
      return;
    }

    if (emergencyPhone.trim()) {
      const cleanEmerg = emergencyPhone.replace(/\D/g, "");
      if (cleanEmerg.length !== 10) {
        setErrorMessage("Emergency contact number must be 10 digits.");
        return;
      }
    }

    setIsSubmitting(true);

    const payload = {
      full_name: fullName.trim(),
      age: Number(age),
      gender,
      phone_number: cleanPhone,
      emergency_contact_name: emergencyName.trim() || null,
      emergency_contact_phone: emergencyPhone.trim() ? emergencyPhone.replace(/\D/g, "") : null,
      address_city: city.trim() || null,
      address_state: state.trim() || null,
      government_id_type: govIdType || null,
      government_id_number: govIdNumber.trim() || null,
      initial_complaint: initialComplaint.trim() || null,
    };

    try {
      const res = await fetch("http://127.0.0.1:8000/api/patients/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        let errText = "Registration failed. Please check inputs or contact desk.";
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            errText = errorData.detail.map((d: any) => d.msg || d).join(", ");
          } else {
            errText = String(errorData.detail);
          }
        }
        setErrorMessage(errText);
        setIsSubmitting(false);
        return;
      }

      const patientData: RegisteredPatient = await res.json();
      setRegisteredPatient(patientData);
    } catch (err: any) {
      setErrorMessage(
        "Could not connect to hospital server. Please ensure the backend is running at http://127.0.0.1:8000."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setFullName("");
    setAge(30);
    setGender("Male");
    setPhone("");
    setEmergencyName("");
    setEmergencyPhone("");
    setCity("");
    setState("");
    setGovIdNumber("");
    setInitialComplaint("");
    setRegisteredPatient(null);
    setErrorMessage(null);
  };

  // SUCCESS CONFIRMATION VIEW
  if (registeredPatient) {
    return (
      <div className="max-w-2xl mx-auto py-6 space-y-6">
        <div className="bg-white border-2 border-teal-500 rounded-3xl p-8 shadow-xl text-center space-y-6">
          <div className="w-20 h-20 bg-teal-100 text-teal-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-12 h-12" />
          </div>

          <div className="space-y-2">
            <span className="inline-block bg-teal-100 text-teal-900 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              Registration Successful • पंजीकरण सफल
            </span>
            <h1 className="text-3xl sm:text-4xl font-black text-slate-900">
              OPD Token Number
            </h1>
            <div className="inline-block bg-teal-50 border-2 border-teal-600 px-6 py-3 rounded-2xl">
              <span className="text-4xl sm:text-5xl font-mono font-extrabold text-teal-800 tracking-wider">
                {registeredPatient.token_number}
              </span>
            </div>
            <p className="text-sm text-slate-500 font-medium">
              Please note or remember this token number for your consultation.
            </p>
          </div>

          {/* Patient Details Snapshot */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 text-left space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-slate-200">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Patient Details
              </span>
              <span className="text-xs text-teal-700 font-semibold">
                Status: {registeredPatient.registration_status}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="block text-xs text-slate-500">Full Name</span>
                <span className="font-bold text-slate-900 text-base">
                  {registeredPatient.full_name}
                </span>
              </div>
              <div>
                <span className="block text-xs text-slate-500">Age & Gender</span>
                <span className="font-semibold text-slate-900">
                  {registeredPatient.age} yrs • {registeredPatient.gender}
                </span>
              </div>
              <div>
                <span className="block text-xs text-slate-500">Mobile Number</span>
                <span className="font-mono font-medium text-slate-900">
                  +91 {registeredPatient.phone_number}
                </span>
              </div>
              <div>
                <span className="block text-xs text-slate-500">Registration Time</span>
                <span className="text-slate-700 text-xs font-mono">
                  {new Date(registeredPatient.created_at).toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: true,
                  })}
                </span>
              </div>
            </div>

            {registeredPatient.initial_complaint && (
              <div className="pt-2 border-t border-slate-200 text-sm">
                <span className="block text-xs text-slate-500">Chief Complaint</span>
                <span className="text-slate-800 font-medium">
                  {registeredPatient.initial_complaint}
                </span>
              </div>
            )}
          </div>

          {/* Next Step Information */}
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-left text-sm text-amber-900 flex items-start space-x-3">
            <Clock className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <strong>Next Steps / अगला कदम:</strong>
              <p className="mt-0.5 text-xs sm:text-sm text-amber-800">
                Your registration has been saved in the hospital database. Please proceed to the OPD Waiting Hall. In Phase 2 & 3, you will complete your AI clinical history intake.
              </p>
            </div>
          </div>

          {/* Primary Action: Proceed to Consent */}
          <div className="pt-2">
            <Link
              href={`/consent?patientId=${registeredPatient.id}`}
              className="w-full py-5 px-6 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-2xl font-bold text-base sm:text-lg shadow-lg flex items-center justify-center space-x-3 transition group"
            >
              <ShieldCheck className="w-6 h-6 text-teal-200" />
              <span>Proceed to Language & Consent / भाषा व सहमति</span>
              <ChevronRight className="w-5 h-5 text-teal-200 group-hover:translate-x-1 transition" />
            </Link>
          </div>

          {/* Secondary Action Buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={handleReset}
              className="w-full py-3.5 px-6 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-sm transition"
            >
              Register Another Patient
            </button>
            <Link
              href="/queue"
              className="w-full py-3.5 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-sm shadow-sm flex items-center justify-center space-x-2 transition"
            >
              <span>View OPD Queue</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // REGISTRATION FORM VIEW
  return (
    <div className="max-w-3xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Top Bar */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 text-sm font-semibold transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </Link>
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Step 1: Patient Registration
        </span>
      </div>

      {/* Form Card */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-10 shadow-sm space-y-8">
        {/* Title Header */}
        <div className="border-b border-slate-200 pb-6">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-2xl bg-teal-100 text-teal-700 flex items-center justify-center">
              <UserPlus className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                Patient Registration
              </h1>
              <p className="text-sm text-slate-500 font-medium">
                नया मरीज़ पंजीकरण • High-Volume OPD Intake Form
              </p>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-4 flex items-start space-x-3">
            <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm font-semibold">{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Section 1: Basic Information */}
          <div className="space-y-5">
            <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <User className="w-5 h-5 text-teal-600" />
              <span>1. Basic Patient Information / प्राथमिक जानकारी</span>
            </h2>

            {/* Full Name */}
            <div>
              <label className="block text-sm font-bold text-slate-800 mb-1">
                Full Name / पूरा नाम <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Ramesh Chandra Sharma"
                className="w-full px-4 py-3.5 text-base sm:text-lg border-2 border-slate-300 rounded-xl focus:border-teal-600 focus:bg-teal-50/20 transition text-slate-900 font-medium"
                required
              />
              <span className="text-xs text-slate-500 mt-1 block">
                Enter name as listed in government ID or hospital card.
              </span>
            </div>

            {/* Age & Gender Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Age with touch counter */}
              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  Age / उम्र (Years) <span className="text-rose-500">*</span>
                </label>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setAge((prev) => Math.max(1, prev - 1))}
                    className="w-12 h-12 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 rounded-xl flex items-center justify-center text-slate-700 font-bold text-xl transition border border-slate-300"
                  >
                    <Minus className="w-5 h-5" />
                  </button>
                  <input
                    type="number"
                    min="1"
                    max="125"
                    value={age}
                    onChange={(e) => setAge(Number(e.target.value))}
                    className="flex-1 px-4 py-3 text-center text-xl font-bold border-2 border-slate-300 rounded-xl focus:border-teal-600 text-slate-900"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setAge((prev) => Math.min(125, prev + 1))}
                    className="w-12 h-12 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 rounded-xl flex items-center justify-center text-slate-700 font-bold text-xl transition border border-slate-300"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Gender Chips */}
              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  Gender / लिंग <span className="text-rose-500">*</span>
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {["Male", "Female", "Other"].map((g) => (
                    <button
                      type="button"
                      key={g}
                      onClick={() => setGender(g)}
                      className={`py-3 px-3 rounded-xl font-bold text-sm transition border-2 ${
                        gender === g
                          ? "bg-teal-600 text-white border-teal-600 shadow-sm"
                          : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Mobile Number */}
            <div>
              <label className="block text-sm font-bold text-slate-800 mb-1">
                Mobile Number / मोबाइल नंबर <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500 font-bold text-base">
                  +91
                </div>
                <input
                  type="tel"
                  maxLength={10}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  placeholder="9876543210"
                  className="w-full pl-14 pr-4 py-3.5 text-base sm:text-lg border-2 border-slate-300 rounded-xl focus:border-teal-600 focus:bg-teal-50/20 transition text-slate-900 font-mono tracking-wider"
                  required
                />
              </div>
              <span className="text-xs text-slate-500 mt-1 block">
                10-digit mobile number for OPD notifications and token SMS.
              </span>
            </div>
          </div>

          {/* Section 2: Emergency Contact & Address */}
          <div className="space-y-5 pt-4 border-t border-slate-200">
            <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <Phone className="w-5 h-5 text-teal-600" />
              <span>2. Attendant & Contact / परिजन संपर्क</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  Attendant / Kin Name (वैकल्पिक)
                </label>
                <input
                  type="text"
                  value={emergencyName}
                  onChange={(e) => setEmergencyName(e.target.value)}
                  placeholder="e.g. Sunita Sharma (Spouse)"
                  className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  Attendant Mobile Number (वैकल्पिक)
                </label>
                <input
                  type="tel"
                  maxLength={10}
                  value={emergencyPhone}
                  onChange={(e) => setEmergencyPhone(e.target.value.replace(/\D/g, ""))}
                  placeholder="10-digit number"
                  className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  City / Town / शहर
                </label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g. Hyderabad / Visakhapatnam"
                  className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  State / राज्य
                </label>
                <input
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  placeholder="e.g. Andhra Pradesh / Telangana"
                  className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Government ID (Optional / ABHA Ready) */}
          <div className="space-y-5 pt-4 border-t border-slate-200">
            <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <FileText className="w-5 h-5 text-teal-600" />
              <span>3. Government ID / पहचान पत्र (Optional)</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-bold text-slate-800 mb-1">ID Type</label>
                <select
                  value={govIdType}
                  onChange={(e) => setGovIdType(e.target.value)}
                  className="w-full px-3 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900 font-medium"
                >
                  <option value="Aadhaar">Aadhaar Card</option>
                  <option value="ABHA">ABHA Health ID</option>
                  <option value="Voter ID">Voter ID</option>
                  <option value="Passport">Passport</option>
                  <option value="Other">Other ID</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-sm font-bold text-slate-800 mb-1">
                  ID Number / पहचान संख्या
                </label>
                <input
                  type="text"
                  value={govIdNumber}
                  onChange={(e) => setGovIdNumber(e.target.value)}
                  placeholder="Optional ID number"
                  className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 transition text-slate-900 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Section 4: Chief Complaint / Reason for Visit */}
          <div className="space-y-5 pt-4 border-t border-slate-200">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-teal-600" />
                <span>4. Reason for Visit / मुख्य समस्या</span>
              </h2>
              <span className="text-xs text-slate-500">Touch pills or type below</span>
            </div>

            {/* Quick Touch Chips */}
            <div className="flex flex-wrap gap-2">
              {COMMON_SYMPTOMS.map((s) => {
                const isSelected = initialComplaint.includes(s.label);
                return (
                  <button
                    type="button"
                    key={s.label}
                    onClick={() => handleSymptomClick(s.label)}
                    className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition border ${
                      isSelected
                        ? "bg-teal-600 text-white border-teal-600 shadow-sm"
                        : "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200"
                    }`}
                  >
                    <span>{s.label}</span>
                    <span className="text-[11px] opacity-80 block font-normal">{s.hindi}</span>
                  </button>
                );
              })}
            </div>

            {/* Complaint Text Area */}
            <div>
              <textarea
                rows={3}
                value={initialComplaint}
                onChange={(e) => setInitialComplaint(e.target.value)}
                placeholder="Describe what brought you to the clinic today..."
                className="w-full px-4 py-3 border-2 border-slate-300 rounded-xl focus:border-teal-600 focus:bg-teal-50/20 transition text-slate-900 font-medium"
              />
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={isSubmitting}
              className={`w-full py-5 px-6 rounded-2xl font-bold text-lg sm:text-xl text-white shadow-lg transition flex items-center justify-center space-x-3 ${
                isSubmitting
                  ? "bg-teal-400 cursor-not-allowed"
                  : "bg-teal-600 hover:bg-teal-700 active:bg-teal-800 shadow-teal-700/20"
              }`}
            >
              {isSubmitting ? (
                <>
                  <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Registering in Hospital Database...</span>
                </>
              ) : (
                <>
                  <UserPlus className="w-6 h-6" />
                  <span>Generate OPD Token & Register</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
