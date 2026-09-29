"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ShieldCheck,
  Globe,
  CheckCircle2,
  XCircle,
  AlertCircle,
  User,
  Clock,
  ArrowLeft,
  ChevronRight,
  Info,
  Check,
  Stethoscope,
  Lock,
  ShieldAlert,
  History,
} from "lucide-react";
import { getAuthHeaders } from "@/lib/auth";

interface Patient {
  id: string;
  token_number: string;
  full_name: string;
  age: number;
  gender: string;
  phone_number: string;
  registration_status: string;
  selected_language?: string;
  consent_status?: string;
  consent_timestamp?: string;
}

interface ConsentRecord {
  consent_id: string;
  patient_id: string;
  session_id?: string;
  consent_type: string;
  status: string;
  timestamp: string;
  language: string;
  revocation_reason?: string;
}

interface LanguageInfo {
  code: string;
  name: string;
  native_name: string;
  ui_supported: boolean;
  voice_supported: boolean;
  description: string;
}

// Bilingual Consent Content
const CONTENT = {
  en: {
    languageTitle: "Select Preferred Language",
    languageSubtitle: "Choose the language for your clinical intake questions",
    voiceNote: "UI Text Supported • Speech/Voice arriving in Phase 6",
    consentTitle: "Patient Information & Informed Consent",
    consentSubtitle: "Please review the information below before proceeding with the AI clinical history assistant",
    badge: "Consent-First Workflow",
    sections: [
      {
        icon: "info",
        title: "1. What Information Will Be Collected?",
        body: "You will be asked about your current symptoms, how long you have had them, past medical conditions, current medications, drug allergies, and past surgeries.",
      },
      {
        icon: "purpose",
        title: "2. Why Is This Information Collected?",
        body: "To help your OPD doctor understand your health background quickly and accurately, minimizing repetition and clinic waiting times.",
      },
      {
        icon: "ai",
        title: "3. Role of the AI Assistant (Not a Doctor)",
        body: "MediKiosk is an administrative and clinical history collection assistant. The AI DOES NOT diagnose diseases or prescribe treatments. It only organizes your answers for your physician.",
      },
      {
        icon: "doctor",
        title: "4. Physician Review and Verification",
        body: "Your doctor will personally review, verify, and edit all recorded details before making any clinical decisions or treatment plans.",
      },
      {
        icon: "rights",
        title: "5. Your Right to Decline",
        body: "Participation is 100% voluntary. If you choose to decline, your OPD token and appointment remain fully valid, and your doctor will take your history manually in person.",
      },
    ],
    agreeBtn: "I Agree & Continue",
    agreeSubtitle: "मैं सहमत हूँ - आगे बढ़ें",
    declineBtn: "Decline Consent",
    declineSubtitle: "अस्वीकार करें",
    submitting: "Recording your consent decision...",
    successTitle: "Consent Granted Successfully",
    successSubtitle: "Your consent has been securely recorded in the hospital database.",
    nextStepTitle: "Ready for Phase 3: Clinical Interview",
    nextStepBody: "In Phase 3, you will answer structured clinical questions regarding your chief symptoms.",
    declinedTitle: "Consent Declined",
    declinedSubtitle: "AI history collection has been cancelled as per your preference.",
    declinedNotice: "Your OPD token remains completely active. Please proceed to the waiting area. Your doctor will take your complete clinical history manually during your consultation.",
    viewQueueBtn: "View OPD Queue",
    returnHomeBtn: "Return to Home",
  },
  hi: {
    languageTitle: "अपनी पसंदीदा भाषा चुनें",
    languageSubtitle: "अपने क्लिनिकल सवालों के लिए भाषा का चयन करें",
    voiceNote: "UI पाठ समर्थित • वाक्/आवाज़ सुविधा चरण 6 में आएगी",
    consentTitle: "मरीज़ सूचना एवं सूचित सहमति",
    consentSubtitle: "एआई क्लिनिकल इतिहास सहायक के साथ आगे बढ़ने से पहले कृपया नीचे दी गई जानकारी को पढ़ें",
    badge: "सहमति-प्रथम प्रक्रिया",
    sections: [
      {
        icon: "info",
        title: "1. कौन सी जानकारी एकत्र की जाएगी?",
        body: "आपसे आपके वर्तमान लक्षणों, बीमारी की अवधि, पिछली बीमारियों, वर्तमान दवाइयों, एलर्जी और पूर्व ऑपरेशनों के बारे में पूछा जाएगा।",
      },
      {
        icon: "purpose",
        title: "2. यह जानकारी क्यों एकत्र की जा रही है?",
        body: "ताकि आपके ओपीडी डॉक्टर आपकी स्वास्थ्य पृष्ठभूमि को जल्दी और सटीक रूप से समझ सकें और आपका प्रतीक्षा समय कम हो सके।",
      },
      {
        icon: "ai",
        title: "3. एआई सहायक की भूमिका (यह डॉक्टर नहीं है)",
        body: "MediKiosk केवल इतिहास एकत्र करने वाला सहायक है। यह एआई कोई निदान (डायग्नोसिस) नहीं करता और न ही दवा लिखता है। यह केवल डॉक्टर के लिए आपकी जानकारी व्यवस्थित करता है।",
      },
      {
        icon: "doctor",
        title: "4. डॉक्टर द्वारा समीक्षा और पुष्टि",
        body: "कोई भी चिकित्सकीय निर्णय लेने से पहले आपके डॉक्टर स्वयं इस पूरी जानकारी की समीक्षा, संपादन और पुष्टि करेंगे।",
      },
      {
        icon: "rights",
        title: "5. अस्वीकार करने का आपका अधिकार",
        body: "इस प्रक्रिया में भाग लेना पूरी तरह स्वैच्छिक है। यदि आप अस्वीकार करते हैं, तो भी आपका ओपीडी टोकन पूरी तरह मान्य रहेगा और डॉक्टर सीधे आपसे मिलकर जानकारी लेंगे।",
      },
    ],
    agreeBtn: "मैं सहमत हूँ - आगे बढ़ें",
    agreeSubtitle: "I Agree & Continue",
    declineBtn: "अस्वीकार करें",
    declineSubtitle: "Decline Consent",
    submitting: "आपकी सहमति का निर्णय दर्ज किया जा रहा है...",
    successTitle: "सहमति सफलतापूर्वक दर्ज की गई",
    successSubtitle: "आपकी सहमति अस्पताल के डेटाबेस में सुरक्षित रूप से दर्ज कर ली गई है।",
    nextStepTitle: "चरण 3 के लिए तैयार: क्लिनिकल साक्षात्कार",
    nextStepBody: "चरण 3 में, आप अपने मुख्य लक्षणों से संबंधित संरचित प्रश्नों के उत्तर देंगे।",
    declinedTitle: "सहमति अस्वीकार की गई",
    declinedSubtitle: "आपकी पसंद के अनुसार एआई इतिहास संग्रह रद्द कर दिया गया है।",
    declinedNotice: "आपका ओपीडी टोकन पूरी तरह मान्य है। कृपया प्रतीक्षा कक्ष में बैठें। परामर्श के दौरान आपके डॉक्टर व्यक्तिगत रूप से आपका पूरा इतिहास पूछेंगे।",
    viewQueueBtn: "ओपीडी कतार देखें",
    returnHomeBtn: "होम पर लौटें",
  },
};

function ConsentComponent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const patientIdParam = searchParams.get("patientId") || "";

  // State
  const [patientId, setPatientId] = useState(patientIdParam);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loadingPatient, setLoadingPatient] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<"en" | "hi">("en");
  const [availableLanguages, setAvailableLanguages] = useState<LanguageInfo[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [consentResult, setConsentResult] = useState<"granted" | "declined" | "revoked" | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Phase 12: Traceable Consent Lifecycle State
  const [consentHistory, setConsentHistory] = useState<ConsentRecord[]>([]);
  const [showRevokeModal, setShowRevokeModal] = useState<boolean>(false);
  const [revokeReason, setRevokeReason] = useState<string>("");
  const [isRevoking, setIsRevoking] = useState<boolean>(false);

  const t = CONTENT[selectedLanguage];

  const fetchConsentHistory = async (pid: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/patients/${pid}/consent/history`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setConsentHistory(data.history || []);
        if (data.current_status && ["granted", "declined", "revoked"].includes(data.current_status)) {
          setConsentResult(data.current_status as any);
        }
      }
    } catch (e) {
      console.error("Failed to load consent history", e);
    }
  };

  const handleRevokeConsent = async () => {
    if (!patient || !revokeReason.trim()) return;
    setIsRevoking(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/patients/${patient.id}/consent/revoke`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason: revokeReason.trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to revoke consent");
      }
      setShowRevokeModal(false);
      setRevokeReason("");
      setConsentResult("revoked");
      await fetchConsentHistory(patient.id);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to revoke consent");
    } finally {
      setIsRevoking(false);
    }
  };

  // Fetch supported languages from backend
  useEffect(() => {
    const fetchLanguages = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/languages");
        if (res.ok) {
          const langs = await res.json();
          setAvailableLanguages(langs);
        }
      } catch (err) {
        console.error("Failed to load languages", err);
      }
    };
    fetchLanguages();
  }, []);

  // Fetch patient details if patientId is provided
  useEffect(() => {
    if (!patientIdParam) return;
    const fetchPatient = async () => {
      setLoadingPatient(true);
      setErrorMessage(null);
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/patients/${patientIdParam}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) {
          throw new Error("Patient record not found in database.");
        }
        const data: Patient = await res.json();
        setPatient(data);
        if (data.selected_language === "hi" || data.selected_language === "en") {
          setSelectedLanguage(data.selected_language);
        }
        if (data.consent_status === "granted" || data.consent_status === "declined" || data.consent_status === "revoked") {
          setConsentResult(data.consent_status as any);
        }
        fetchConsentHistory(data.id);
      } catch (err: any) {
        setErrorMessage(err.message || "Could not fetch patient record.");
      } finally {
        setLoadingPatient(false);
      }
    };
    fetchPatient();
  }, [patientIdParam]);

  // Lookup patient by ID or Token if entered manually
  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId.trim()) return;
    setLoadingPatient(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/patients/${patientId.trim()}`);
      if (!res.ok) {
        throw new Error(`Patient with identifier '${patientId}' not found.`);
      }
      const data: Patient = await res.json();
      setPatient(data);
      if (data.selected_language === "hi" || data.selected_language === "en") {
        setSelectedLanguage(data.selected_language);
      }
      if (data.consent_status === "granted" || data.consent_status === "declined") {
        setConsentResult(data.consent_status as "granted" | "declined");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Could not find patient.");
    } finally {
      setLoadingPatient(false);
    }
  };

  // Submit Consent Decision
  const handleConsentDecision = async (status: "granted" | "declined") => {
    if (!patient) {
      setErrorMessage("No patient selected. Please look up a registered patient first.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/patients/${patient.id}/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_language: selectedLanguage,
          consent_status: status,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to record consent in database.");
      }

      const updatedPatient: Patient = await res.json();
      setPatient(updatedPatient);
      setConsentResult(status);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to connect to backend server.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // 1. RESULT SCREEN: CONSENT GRANTED
  if (consentResult === "granted" && patient) {
    return (
      <div className="max-w-2xl mx-auto py-8 space-y-6">
        <div className="bg-white border-2 border-emerald-500 rounded-3xl p-8 shadow-xl text-center space-y-6">
          <div className="w-20 h-20 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-12 h-12" />
          </div>

          <div className="space-y-2">
            <span className="inline-block bg-emerald-100 text-emerald-900 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              {t.badge}
            </span>
            <h1 className="text-3xl font-black text-slate-900">{t.successTitle}</h1>
            <p className="text-sm text-slate-600">{t.successSubtitle}</p>
          </div>

          {/* Patient Card */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 text-left text-sm space-y-2">
            <div className="flex justify-between items-center border-b border-slate-200 pb-2">
              <span className="font-bold text-slate-700">Patient / मरीज़</span>
              <span className="font-mono font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                {patient.token_number}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <span className="text-xs text-slate-500 block">Name</span>
                <span className="font-semibold text-slate-900">{patient.full_name}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Language Selected</span>
                <span className="font-semibold text-slate-900">
                  {selectedLanguage === "hi" ? "हिन्दी (Hindi)" : "English"}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Consent Status</span>
                <span className="font-semibold text-emerald-700">Granted / सहमति प्रदत्त</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Recorded At</span>
                <span className="text-xs font-mono text-slate-600">
                  {patient.consent_timestamp
                    ? new Date(patient.consent_timestamp).toLocaleTimeString()
                    : "Recorded"}
                </span>
              </div>
            </div>
          </div>

          {/* Phase 3 Ready Notice */}
          <div className="bg-teal-50 border border-teal-200 rounded-2xl p-4 text-left text-sm text-teal-950 flex items-start space-x-3">
            <Stethoscope className="w-6 h-6 text-teal-600 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block text-teal-900 font-bold">{t.nextStepTitle}</strong>
              <p className="text-xs sm:text-sm text-teal-800 mt-0.5">{t.nextStepBody}</p>
            </div>
          </div>

          {/* Primary Action: Start Clinical Interview */}
          <div className="pt-2">
            <Link
              href={`/interview?patientId=${patient.id}`}
              className="w-full py-5 px-6 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-2xl font-bold text-base sm:text-lg shadow-lg flex items-center justify-center space-x-3 transition group"
            >
              <Stethoscope className="w-6 h-6 text-teal-200" />
              <span>{selectedLanguage === "hi" ? "क्लिनिकल इंटरव्यू शुरू करें" : "Start Clinical Interview"}</span>
              <ChevronRight className="w-6 h-6 text-teal-200 group-hover:translate-x-1 transition" />
            </Link>
          </div>

          {/* Secondary Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Link
              href="/queue"
              className="w-full py-3.5 px-6 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-sm shadow-sm flex items-center justify-center space-x-2 transition"
            >
              <span>{t.viewQueueBtn}</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
            <Link
              href="/"
              className="w-full py-3.5 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-sm shadow-sm flex items-center justify-center transition"
            >
              <span>{t.returnHomeBtn}</span>
            </Link>
          </div>

          {/* Phase 12: Revocation Option */}
          <div className="pt-4 border-t border-slate-100 flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => setShowRevokeModal(true)}
              className="text-xs font-semibold text-rose-600 hover:text-rose-800 hover:underline flex items-center space-x-1"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Withdraw / Revoke Consent (सहमति वापस लें)</span>
            </button>
            <span className="text-[11px] text-slate-400">
              You can withdraw consent at any time. Your OPD appointment remains fully valid.
            </span>
          </div>
        </div>

        {/* Revoke Modal */}
        {showRevokeModal && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl space-y-4 border border-slate-100">
              <div className="w-12 h-12 bg-rose-100 text-rose-600 rounded-2xl flex items-center justify-center">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Withdraw Consent / सहमति वापस लें</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Withdrawing consent pauses AI-assisted clinical intake. Your doctor will take your complete clinical history manually during your consultation.
              </p>
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Reason for withdrawal / सहमति वापस लेने का कारण: <span className="text-rose-500">*</span>
                </label>
                <textarea
                  value={revokeReason}
                  onChange={(e) => setRevokeReason(e.target.value)}
                  placeholder="e.g. Prefer in-person consultation with physician..."
                  className="w-full p-3 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-rose-500 text-slate-900"
                  rows={3}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRevokeModal(false)}
                  className="flex-1 py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-xs"
                >
                  Cancel / रद्द करें
                </button>
                <button
                  type="button"
                  onClick={handleRevokeConsent}
                  disabled={!revokeReason.trim() || isRevoking}
                  className="flex-1 py-2.5 px-4 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold text-xs disabled:opacity-50"
                >
                  {isRevoking ? "Withdrawing..." : "Confirm Revoke"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // 1b. RESULT SCREEN: CONSENT REVOKED
  if (consentResult === "revoked" && patient) {
    return (
      <div className="max-w-2xl mx-auto py-8 space-y-6">
        <div className="bg-white border-2 border-rose-400 rounded-3xl p-8 shadow-xl text-center space-y-6">
          <div className="w-20 h-20 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <ShieldAlert className="w-12 h-12" />
          </div>

          <div className="space-y-2">
            <span className="inline-block bg-rose-100 text-rose-900 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              Consent Revoked / सहमति वापस ली गई
            </span>
            <h1 className="text-3xl font-black text-slate-900">Consent Withdrawn</h1>
            <p className="text-sm text-slate-600">
              AI clinical intake has been paused for this patient as per your request.
            </p>
          </div>

          <div className="bg-rose-50 border border-rose-200 rounded-2xl p-5 text-left text-sm text-rose-950 space-y-2">
            <div className="font-bold flex items-center space-x-2 text-rose-900">
              <Info className="w-5 h-5 text-rose-700" />
              <span>OPD Registration & Token Active</span>
            </div>
            <p className="text-xs sm:text-sm text-rose-900 leading-relaxed">
              Your appointment token ({patient.token_number}) remains 100% active. Your attending doctor will conduct your case-taking manually in person.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <Link
              href="/queue"
              className="w-full py-4 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-base shadow-md flex items-center justify-center space-x-2 transition"
            >
              <span>{t.viewQueueBtn}</span>
              <ChevronRight className="w-5 h-5" />
            </Link>
            <button
              onClick={() => setConsentResult(null)}
              className="w-full py-4 px-6 bg-white border-2 border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-base shadow-sm transition"
            >
              Renew / Re-Grant Consent
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 2. RESULT SCREEN: CONSENT DECLINED
  if (consentResult === "declined" && patient) {
    return (
      <div className="max-w-2xl mx-auto py-8 space-y-6">
        <div className="bg-white border-2 border-amber-400 rounded-3xl p-8 shadow-xl text-center space-y-6">
          <div className="w-20 h-20 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <XCircle className="w-12 h-12" />
          </div>

          <div className="space-y-2">
            <span className="inline-block bg-amber-100 text-amber-900 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              {t.declinedTitle}
            </span>
            <h1 className="text-3xl font-black text-slate-900">{t.declinedTitle}</h1>
            <p className="text-sm text-slate-600">{t.declinedSubtitle}</p>
          </div>

          {/* Informational Box */}
          <div className="bg-amber-50 border border-amber-300 rounded-2xl p-5 text-left text-sm text-amber-950 space-y-2">
            <div className="font-bold flex items-center space-x-2 text-amber-900">
              <Info className="w-5 h-5 text-amber-700" />
              <span>Your OPD Registration Remains Intact</span>
            </div>
            <p className="text-xs sm:text-sm text-amber-900 leading-relaxed">
              {t.declinedNotice}
            </p>
            <div className="pt-2 border-t border-amber-200 flex justify-between text-xs text-amber-800">
              <span>Token: <strong>{patient.token_number}</strong></span>
              <span>Patient: <strong>{patient.full_name}</strong></span>
            </div>
          </div>

          {/* Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <Link
              href="/queue"
              className="w-full py-4 px-6 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-base shadow-md flex items-center justify-center space-x-2 transition"
            >
              <span>{t.viewQueueBtn}</span>
              <ChevronRight className="w-5 h-5" />
            </Link>
            <button
              onClick={() => setConsentResult(null)}
              className="w-full py-4 px-6 bg-white border-2 border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-base shadow-sm transition"
            >
              Re-evaluate Consent
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. MAIN CONSENT & LANGUAGE VIEW
  return (
    <div className="max-w-3xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Top Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 text-sm font-semibold transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </Link>
        <span className="text-xs font-semibold text-teal-700 bg-teal-50 border border-teal-200 px-3 py-1 rounded-full uppercase tracking-wider">
          Step 2: Language & Consent
        </span>
      </div>

      {/* Patient Identifier Bar (if patient loaded) */}
      {patient ? (
        <div className="bg-teal-50 border border-teal-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-teal-600 text-white flex items-center justify-center font-bold">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">{patient.full_name}</h2>
              <p className="text-xs text-slate-600">
                {patient.age} yrs • {patient.gender} • +91 {patient.phone_number}
              </p>
            </div>
          </div>

          <div className="bg-white border border-teal-300 rounded-xl px-4 py-1.5 text-center">
            <span className="block text-[10px] uppercase font-bold text-teal-800">OPD Token</span>
            <span className="font-mono text-base font-black text-teal-900">{patient.token_number}</span>
          </div>
        </div>
      ) : (
        /* Patient Lookup Form if no patient is attached */
        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-800">
            Find Patient by Token or ID / मरीज़ खोजें
          </h3>
          <form onSubmit={handleLookup} className="flex gap-2">
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="Enter Token (e.g. MK-20260910-0001) or MongoDB ID"
              className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:border-teal-600 text-slate-900 font-medium"
            />
            <button
              type="submit"
              disabled={loadingPatient}
              className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-bold shadow-sm transition"
            >
              {loadingPatient ? "Searching..." : "Select"}
            </button>
          </form>
          <div className="text-xs text-slate-500">
            Or select a patient from the{" "}
            <Link href="/queue" className="text-teal-600 underline font-semibold">
              OPD Live Queue
            </Link>
            .
          </div>
        </div>
      )}

      {/* Error Alert */}
      {errorMessage && (
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-4 flex items-start space-x-3">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-semibold">{errorMessage}</div>
        </div>
      )}

      {/* Main Consent Card */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-10 shadow-sm space-y-8">
        {/* STEP A: LANGUAGE SELECTION */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center space-x-2">
              <Globe className="w-5 h-5 text-teal-600" />
              <h2 className="text-lg font-extrabold text-slate-900">{t.languageTitle}</h2>
            </div>
            <span className="text-xs text-slate-500 font-medium">{t.languageSubtitle}</span>
          </div>

          {/* Language Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* English Card */}
            <button
              type="button"
              onClick={() => setSelectedLanguage("en")}
              className={`p-5 rounded-2xl border-2 text-left transition flex items-center justify-between ${
                selectedLanguage === "en"
                  ? "border-teal-600 bg-teal-50/50 shadow-md ring-2 ring-teal-500/20"
                  : "border-slate-200 hover:border-slate-300 bg-white"
              }`}
            >
              <div>
                <span className="text-xl font-bold text-slate-900 block">English</span>
                <span className="text-xs text-slate-500">English Language Interface</span>
                <span className="inline-block mt-2 text-[11px] font-semibold text-teal-700 bg-teal-100 px-2 py-0.5 rounded">
                  UI Text Supported
                </span>
              </div>
              {selectedLanguage === "en" && (
                <div className="w-7 h-7 rounded-full bg-teal-600 text-white flex items-center justify-center">
                  <Check className="w-4 h-4" />
                </div>
              )}
            </button>

            {/* Hindi Card */}
            <button
              type="button"
              onClick={() => setSelectedLanguage("hi")}
              className={`p-5 rounded-2xl border-2 text-left transition flex items-center justify-between ${
                selectedLanguage === "hi"
                  ? "border-teal-600 bg-teal-50/50 shadow-md ring-2 ring-teal-500/20"
                  : "border-slate-200 hover:border-slate-300 bg-white"
              }`}
            >
              <div>
                <span className="text-xl font-bold text-slate-900 block">हिन्दी (Hindi)</span>
                <span className="text-xs text-slate-500">हिन्दी भाषा इंटरफ़ेस</span>
                <span className="inline-block mt-2 text-[11px] font-semibold text-teal-700 bg-teal-100 px-2 py-0.5 rounded">
                  UI पाठ समर्थित
                </span>
              </div>
              {selectedLanguage === "hi" && (
                <div className="w-7 h-7 rounded-full bg-teal-600 text-white flex items-center justify-center">
                  <Check className="w-4 h-4" />
                </div>
              )}
            </button>
          </div>

          <p className="text-xs text-slate-500 italic text-center sm:text-left">
            * Note: Voice/ASR input will be enabled in Phase 6. Current phase supports touchscreen and text intake.
          </p>
        </div>

        {/* STEP B: INFORMED CONSENT EXPLANATION */}
        <div className="space-y-4 pt-4 border-t border-slate-200">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-teal-600" />
            <div>
              <h2 className="text-xl font-extrabold text-slate-900">{t.consentTitle}</h2>
              <p className="text-xs text-slate-500">{t.consentSubtitle}</p>
            </div>
          </div>

          {/* Detailed 5-Point Explanation Container */}
          <div className="space-y-3 bg-slate-50 border border-slate-200 rounded-2xl p-5 sm:p-6 text-slate-800">
            {t.sections.map((section, idx) => (
              <div key={idx} className="pb-3 border-b border-slate-200 last:border-b-0 last:pb-0">
                <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-600" />
                  <span>{section.title}</span>
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 mt-1 pl-3 leading-relaxed">
                  {section.body}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* STEP C: DECISION BUTTONS */}
        <div className="pt-4 border-t border-slate-200 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Agree Button */}
            <button
              type="button"
              disabled={isSubmitting || !patient}
              onClick={() => handleConsentDecision("granted")}
              className={`p-5 rounded-2xl text-white font-bold shadow-lg transition flex flex-col items-center justify-center ${
                isSubmitting || !patient
                  ? "bg-teal-400 cursor-not-allowed"
                  : "bg-teal-600 hover:bg-teal-700 active:bg-teal-800 shadow-teal-700/20 group"
              }`}
            >
              <div className="flex items-center space-x-2 text-lg sm:text-xl">
                <CheckCircle2 className="w-6 h-6 text-teal-200" />
                <span>{t.agreeBtn}</span>
              </div>
              <span className="text-xs text-teal-100 font-normal mt-0.5">{t.agreeSubtitle}</span>
            </button>

            {/* Decline Button */}
            <button
              type="button"
              disabled={isSubmitting || !patient}
              onClick={() => handleConsentDecision("declined")}
              className={`p-5 rounded-2xl font-bold border-2 transition flex flex-col items-center justify-center ${
                isSubmitting || !patient
                  ? "bg-slate-100 border-slate-300 text-slate-400 cursor-not-allowed"
                  : "bg-white border-slate-300 text-slate-700 hover:bg-rose-50 hover:border-rose-300 hover:text-rose-700"
              }`}
            >
              <div className="flex items-center space-x-2 text-lg sm:text-xl">
                <XCircle className="w-6 h-6 text-slate-400 group-hover:text-rose-600" />
                <span>{t.declineBtn}</span>
              </div>
              <span className="text-xs text-slate-500 font-normal mt-0.5">{t.declineSubtitle}</span>
            </button>
          </div>

          {!patient && (
            <p className="text-xs text-rose-600 font-medium text-center">
              Please enter or select a registered patient above to record consent.
            </p>
          )}

          {isSubmitting && (
            <p className="text-xs text-teal-700 font-semibold text-center animate-pulse">
              {t.submitting}
            </p>
          )}
        </div>
      </div>

      {/* Phase 12: Traceable Consent Audit Trail */}
      {consentHistory.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
            <History className="w-5 h-5 text-teal-600" />
            <h3 className="text-base font-bold text-slate-900">
              Consent Lifecycle History / सहमति इतिहास
            </h3>
          </div>
          <div className="divide-y divide-slate-100">
            {consentHistory.map((rec) => (
              <div key={rec.consent_id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-1">
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-2 py-0.5 rounded-full font-bold uppercase tracking-wider text-[10px] ${
                      rec.status === "granted"
                        ? "bg-emerald-100 text-emerald-800"
                        : rec.status === "revoked"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {rec.status}
                  </span>
                  <span className="font-mono text-slate-500">{rec.consent_id}</span>
                  {rec.revocation_reason && (
                    <span className="text-rose-700 italic">"{rec.revocation_reason}"</span>
                  )}
                </div>
                <div className="text-slate-400 font-mono text-[11px]">
                  {new Date(rec.timestamp).toLocaleString()} ({rec.language.toUpperCase()})
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase 12: Privacy & Interoperability Architecture Card */}
      <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-sm space-y-3">
        <div className="flex items-center space-x-2 text-teal-400">
          <Lock className="w-5 h-5" />
          <h3 className="text-sm font-bold uppercase tracking-wider">
            MediKiosk Privacy & Audit Architecture
          </h3>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          All consent actions, interview answers, and document views are recorded in an append-only security ledger.
          MediKiosk strictly enforces physician-in-the-loop oversight. AI provides structured case summarization only and never autonomously diagnoses.
        </p>
      </div>
    </div>
  );
}

export default function ConsentPage() {
  return (
    <Suspense
      fallback={
        <div className="p-12 text-center text-slate-500">
          <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <span>Loading Consent Module...</span>
        </div>
      }
    >
      <ConsentComponent />
    </Suspense>
  );
}
