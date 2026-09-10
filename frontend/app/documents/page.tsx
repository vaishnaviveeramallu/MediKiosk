"use client";

import React, { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText,
  Upload,
  Camera,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Trash2,
  ExternalLink,
  Clock,
  User,
  ShieldCheck,
  FileCheck,
  X,
  RefreshCw,
  Search,
  ChevronRight,
  Eye,
  Download,
  FileType,
  Sparkles,
  Stethoscope,
  Pill,
  Activity,
  Copy,
  Check,
  FileSearch,
  ShieldAlert,
  ClipboardList,
} from "lucide-react";

interface PatientContext {
  patient_id: string;
  token_number: string;
  full_name: string;
  age?: number;
  gender?: string;
  registration_status?: string;
  selected_language?: string;
}

interface ExtractedPatientInfo {
  name?: string | null;
  age?: string | null;
  gender?: string | null;
  document_date?: string | null;
  confidence?: number;
}

interface ExtractedMedication {
  name: string;
  dosage?: string | null;
  dose?: string | null;
  frequency?: string | null;
  duration?: string | null;
  route?: string | null;
  confidence?: number;
  verification_status?: string;
}

interface ExtractedInvestigation {
  test_name: string;
  result_value?: string | null;
  unit?: string | null;
  reference_range?: string | null;
  test_date?: string | null;
  is_abnormal?: boolean | null;
  confidence?: number;
  verification_status?: string;
}

interface ExtractedDiagnosis {
  diagnosis: string;
  symptoms?: string[];
  type?: string | null;
  confidence?: number;
  verification_status?: string;
}

interface ExtractedProcedure {
  procedure_name: string;
  procedure_date?: string | null;
  notes?: string | null;
  confidence?: number;
  verification_status?: string;
}

interface ExtractedAllergy {
  allergen: string;
  reaction?: string | null;
  severity?: string | null;
  confidence?: number;
  verification_status?: string;
}

interface ExtractedMedicalData {
  patient_info?: ExtractedPatientInfo | null;
  diagnoses?: ExtractedDiagnosis[];
  medications?: ExtractedMedication[];
  investigations?: ExtractedInvestigation[];
  procedures?: ExtractedProcedure[];
  allergies?: ExtractedAllergy[];
  other_findings?: string[];
  doctor_info?: string | null;
  hospital_clinic_info?: string | null;
  unclear_findings?: string[];
  requires_physician_review?: boolean;
  extraction_notes?: string | null;
}

interface OCRMetadata {
  engine: string;
  languages: string[];
  page_count: number;
  confidence?: number | null;
  processing_time_ms: number;
  handwritten_detected?: boolean;
  handwriting_disclaimer?: string | null;
}

interface UploadedDocument {
  document_id: string;
  patient_id: string;
  token_number: string;
  original_filename: string;
  document_type: string;
  content_type: string;
  file_size: number;
  file_hash: string;
  uploaded_at: string;
  upload_status: string;
  processing_status: string;
  notes?: string | null;
  raw_ocr_text?: string | null;
  ocr_metadata?: OCRMetadata | null;
  extracted_data?: ExtractedMedicalData | null;
  verification_status?: string;
  verified_by?: string | null;
  verified_at?: string | null;
  verification_notes?: string | null;
}

const CATEGORY_OPTIONS = [
  { id: "prescription", label_en: "Prescription", label_hi: "पर्चा / दवा की पर्ची" },
  { id: "lab_report", label_en: "Laboratory Report", label_hi: "लैब / रक्त जांच रिपोर्ट" },
  { id: "discharge_summary", label_en: "Discharge Summary", label_hi: "डिस्चार्ज सारांश" },
  { id: "medical_report", label_en: "Medical Report", label_hi: "चिकित्सा रिपोर्ट" },
  { id: "imaging_scan", label_en: "Imaging / Scan Report", label_hi: "एक्स-रे / सीटी / एमआरआई स्कैन" },
  { id: "other", label_en: "Other / Not sure", label_hi: "अन्य / निश्चित नहीं" },
] as const;

function DocumentsComponent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const patientIdParam = searchParams.get("patientId") || "";

  const [patientIdInput, setPatientIdInput] = useState(patientIdParam);
  const [patient, setPatient] = useState<PatientContext | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Staged file state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("prescription");
  const [notes, setNotes] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragOver, setIsDragOver] = useState(false);

  // Processing & Review Modal State
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [activeReviewDoc, setActiveReviewDoc] = useState<UploadedDocument | null>(null);
  const [reviewTab, setReviewTab] = useState<"entities" | "raw_text">("entities");
  const [copiedText, setCopiedText] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  // Deletion state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  // Load Patient & Documents
  const loadPatientData = useCallback(async (pid: string) => {
    if (!pid.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch patient profile
      const pRes = await fetch(`http://127.0.0.1:8000/api/patients/${encodeURIComponent(pid.trim())}`);
      if (!pRes.ok) {
        throw new Error("Patient record not found. Please check Token Number or Patient ID.");
      }
      const pData = await pRes.json();
      const canonicalPid = pData.id || pData._id || pData.patient_id;

      setPatient({
        patient_id: canonicalPid,
        token_number: pData.token_number || "",
        full_name: pData.full_name || "Registered Patient",
        age: pData.age,
        gender: pData.gender,
        registration_status: pData.status,
        selected_language: pData.language || pData.consent?.language || "en",
      });

      // 2. Fetch uploaded documents
      const dRes = await fetch(`http://127.0.0.1:8000/api/patients/${encodeURIComponent(canonicalPid)}/documents`);
      if (dRes.ok) {
        const dData = await dRes.json();
        setDocuments(dData.documents || []);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load patient records.");
      setPatient(null);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (patientIdParam) {
      loadPatientData(patientIdParam);
    } else {
      setLoading(false);
    }
  }, [patientIdParam, loadPatientData]);

  const handlePatientSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientIdInput.trim()) return;
    router.push(`/documents?patientId=${encodeURIComponent(patientIdInput.trim())}`);
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndStageFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndStageFile(e.target.files[0]);
    }
  };

  const validateAndStageFile = (file: File) => {
    setError(null);
    setSuccessMessage(null);

    const allowedExtensions = [".pdf", ".jpg", ".jpeg", ".png"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setError("Unsupported file format. Please upload PDF, JPG, JPEG, or PNG files only.");
      return;
    }

    // 10 MB limit
    if (file.size > 10 * 1024 * 1024) {
      setError("File size exceeds 10 MB. Please upload a smaller document.");
      return;
    }

    if (file.size === 0) {
      setError("The selected file is empty. Please choose a valid document.");
      return;
    }

    setSelectedFile(file);
  };

  // Upload handler
  const handleUploadSubmit = async () => {
    if (!selectedFile || !patient) return;

    setIsUploading(true);
    setError(null);
    setSuccessMessage(null);
    setUploadProgress(20);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("document_type", selectedCategory);
    if (notes.trim()) {
      formData.append("notes", notes.trim());
    }

    try {
      setUploadProgress(50);
      const res = await fetch(`http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents`, {
        method: "POST",
        body: formData,
      });

      setUploadProgress(85);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        if (res.status === 409) {
          throw new Error(errorData.detail || "This document has already been uploaded for this patient.");
        }
        throw new Error(errorData.detail || `Upload failed (Status ${res.status}).`);
      }

      const createdDoc = await res.json();
      setUploadProgress(100);
      setSuccessMessage(`Document "${selectedFile.name}" uploaded successfully.`);

      // Reset form
      setSelectedFile(null);
      setNotes("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (cameraInputRef.current) cameraInputRef.current.value = "";

      // Refresh documents
      await loadPatientData(patient.patient_id);
    } catch (err: any) {
      setError(err.message || "Failed to upload document. Please try again.");
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  // Phase 8: OCR & Medical Entity Processing Handler
  const handleProcessDocument = async (documentId: string) => {
    if (!patient) return;
    setProcessingId(documentId);
    setError(null);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents/${encodeURIComponent(
          documentId
        )}/process`,
        { method: "POST" }
      );

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to process document.");
      }

      const procData = await res.json();
      setSuccessMessage(`Document processed successfully: text extracted and clinical findings ready for review.`);

      // Refresh documents list
      await loadPatientData(patient.patient_id);

      // Open review modal immediately for the processed document
      const updatedDocsRes = await fetch(
        `http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents/${encodeURIComponent(
          documentId
        )}`
      );
      if (updatedDocsRes.ok) {
        const updatedDoc = await updatedDocsRes.json();
        setActiveReviewDoc(updatedDoc);
      }
    } catch (err: any) {
      setError(err.message || "Error processing document.");
    } finally {
      setProcessingId(null);
    }
  };

  // Phase 8: Physician Verification Handler
  const handleVerifyDocument = async (documentId: string) => {
    if (!patient) return;
    setIsVerifying(true);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents/${encodeURIComponent(
          documentId
        )}/verification`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            verification_status: "verified",
            verified_by: "OPD Medical Officer",
            verification_notes: "Clinical records verified by hospital medical officer.",
          }),
        }
      );
      if (!res.ok) {
        throw new Error("Failed to update verification status.");
      }
      const updated = await res.json();
      setActiveReviewDoc(updated);
      await loadPatientData(patient.patient_id);
      setSuccessMessage("Document marked as verified by physician.");
    } catch (err: any) {
      setError(err.message || "Error updating verification.");
    } finally {
      setIsVerifying(false);
    }
  };

  // Delete handler
  const handleDeleteDocument = async (documentId: string, filename: string) => {
    if (!patient) return;
    if (!confirm(`Are you sure you want to remove document "${filename}"?`)) return;

    setDeletingId(documentId);
    setError(null);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents/${encodeURIComponent(
          documentId
        )}`,
        { method: "DELETE" }
      );

      if (!res.ok) {
        throw new Error("Could not delete document.");
      }

      setSuccessMessage(`Document "${filename}" deleted successfully.`);
      if (activeReviewDoc?.document_id === documentId) {
        setActiveReviewDoc(null);
      }
      await loadPatientData(patient.patient_id);
    } catch (err: any) {
      setError(err.message || "Deletion error.");
    } finally {
      setDeletingId(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDateTime = (isoString: string): string => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  const isHindi = patient?.selected_language === "hi";

  // No patient selected view
  if (!patient && !loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="bg-white border-2 border-slate-200 rounded-3xl p-8 shadow-sm space-y-6 text-center">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto border border-teal-200">
            <FileText className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-slate-900">Medical Documents Portal</h1>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Upload and manage prescriptions, lab results, and previous medical records linked to your OPD token.
            </p>
          </div>

          <form onSubmit={handlePatientSearch} className="space-y-4 max-w-md mx-auto text-left">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Enter Patient ID or OPD Token Number:
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={patientIdInput}
                  onChange={(e) => setPatientIdInput(e.target.value)}
                  placeholder="e.g. MK-20260910-0048 or 6aa2..."
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-300 rounded-2xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono text-sm"
                />
                <button
                  type="submit"
                  className="absolute right-2 top-2 px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1"
                >
                  <Search className="w-3.5 h-3.5" />
                  <span>Lookup</span>
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl p-3 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </form>

          <div className="pt-4 border-t border-slate-100 flex justify-center space-x-4 text-xs font-medium text-slate-500">
            <Link href="/register" className="text-teal-600 hover:underline">
              New Patient Registration
            </Link>
            <span>•</span>
            <Link href="/queue" className="text-teal-600 hover:underline">
              View OPD Queue
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (loading || !patient) {
    return (
      <div className="py-20 text-center space-y-4">
        <RefreshCw className="w-8 h-8 text-teal-600 animate-spin mx-auto" />
        <p className="text-sm font-medium text-slate-600">Loading patient documents and medical records...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Patient Header Card */}
      <div className="bg-white border-2 border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-600 text-white flex items-center justify-center font-bold font-mono text-sm shadow-sm">
            {patient.token_number || "PT"}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-900">{patient.full_name}</h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-100 text-teal-800">
                {patient.token_number}
              </span>
            </div>
            <p className="text-xs text-slate-500">
              {patient.gender || "Patient"} • {patient.age ? `${patient.age} yrs` : "Adult"}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Link
            href={`/summary?patientId=${encodeURIComponent(patient.patient_id)}`}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-xs"
          >
            <ClipboardList className="w-3.5 h-3.5" />
            <span>Clinical Summary</span>
          </Link>
          <Link
            href={`/interview?patientId=${encodeURIComponent(patient.patient_id)}`}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>Clinical Intake</span>
          </Link>
          <Link
            href="/queue"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>OPD Queue</span>
          </Link>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-900 rounded-2xl p-4 flex items-start space-x-3 shadow-sm">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{error}</div>
        </div>
      )}

      {successMessage && (
        <div className="bg-emerald-50 border-2 border-emerald-300 text-emerald-900 rounded-2xl p-4 flex items-start space-x-3 shadow-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{successMessage}</div>
        </div>
      )}

      {/* Upload Zone Card */}
      <div className="bg-white border-2 border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
            <Upload className="w-5 h-5 text-teal-600" />
            <span>Select & Upload Document</span>
          </h2>
          <p className="text-xs sm:text-sm text-slate-500">
            {isHindi
              ? "पूर्व पर्चे, लैब जांच रिपोर्ट या डिस्चार्ज सारांश यहां अपलोड करें।"
              : "Upload prior prescriptions, lab reports, discharge summaries, or imaging scans to assist the doctor."}
          </p>
        </div>

        {/* 1. Category Selection */}
        <div className="space-y-2">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
            Document Category / दस्तावेज़ का प्रकार:
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
            {CATEGORY_OPTIONS.map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                  selectedCategory === cat.id
                    ? "border-teal-600 bg-teal-50/70 ring-2 ring-teal-500/20"
                    : "border-slate-200 hover:border-slate-300 bg-white"
                }`}
              >
                <span
                  className={`text-xs sm:text-sm font-bold ${
                    selectedCategory === cat.id ? "text-teal-900" : "text-slate-800"
                  }`}
                >
                  {cat.label_en}
                </span>
                <span className="text-[11px] text-slate-500 mt-0.5">{cat.label_hi}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 2. Drag and Drop Area */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center transition flex flex-col items-center justify-center space-y-3 ${
            isDragOver
              ? "border-teal-500 bg-teal-50/50"
              : "border-slate-300 hover:border-teal-400 bg-slate-50/60"
          }`}
        >
          <div className="w-12 h-12 rounded-2xl bg-white text-teal-600 shadow-sm border border-slate-200 flex items-center justify-center">
            <Upload className="w-6 h-6" />
          </div>

          <div className="space-y-1">
            <p className="text-sm font-bold text-slate-800">
              Drag and drop your document here, or browse
            </p>
            <p className="text-xs text-slate-500">
              Supported formats: <strong className="text-slate-700">PDF, JPG, JPEG, PNG</strong> (Max 10 MB)
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-xs sm:text-sm font-bold shadow-sm transition flex items-center space-x-2"
            >
              <FileText className="w-4 h-4" />
              <span>Choose File / फाइल चुनें</span>
            </button>

            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs sm:text-sm font-bold shadow-sm transition flex items-center space-x-2"
            >
              <Camera className="w-4 h-4" />
              <span>Scan / Camera / फोटो खींचें</span>
            </button>
          </div>
        </div>

        {/* 3. Staged File Card */}
        {selectedFile && (
          <div className="bg-slate-50 border-2 border-teal-200 rounded-2xl p-4 sm:p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-teal-600 text-white flex items-center justify-center font-bold text-xs uppercase flex-shrink-0">
                  {selectedFile.name.split(".").pop() || "DOC"}
                </div>
                <div className="min-w-0">
                  <h4 className="text-sm font-bold text-slate-900 truncate max-w-xs sm:max-w-md">
                    {selectedFile.name}
                  </h4>
                  <p className="text-xs text-slate-500">
                    {formatFileSize(selectedFile.size)} • Category:{" "}
                    <strong className="text-teal-700">
                      {CATEGORY_OPTIONS.find((c) => c.id === selectedCategory)?.label_en}
                    </strong>
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                disabled={isUploading}
                className="text-slate-400 hover:text-slate-600 p-1"
                title="Cancel file"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Optional Notes / विशेष विवरण:
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Blood test report from August 2026, or previous cardiology prescription"
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            {isUploading && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-bold text-teal-800">
                  <span>Uploading document safely...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-teal-600 transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-1">
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                disabled={isUploading}
                className="px-4 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUploadSubmit}
                disabled={isUploading}
                className="px-5 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-md transition flex items-center space-x-1.5"
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Uploading...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-3.5 h-3.5" />
                    <span>Confirm & Upload / अपलोड करें</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Uploaded Documents List */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="space-y-0.5">
            <h2 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
              <FileCheck className="w-5 h-5 text-teal-600" />
              <span>Uploaded Documents ({documents.length})</span>
            </h2>
            <p className="text-xs text-slate-500">
              Medical records stored in MongoDB with AI OCR and structured entity extraction.
            </p>
          </div>

          <button
            onClick={() => loadPatientData(patient.patient_id)}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
            title="Refresh documents"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <FileText className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <h4 className="text-base font-bold text-slate-700">No Medical Documents Uploaded</h4>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                You have not uploaded any previous prescriptions or reports yet. You may upload them above or proceed to your consultation.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => {
              const catObj = CATEGORY_OPTIONS.find((c) => c.id === doc.document_type);
              const isProcessingThis = processingId === doc.document_id;
              const downloadUrl = `http://127.0.0.1:8000/api/patients/${encodeURIComponent(
                patient.patient_id
              )}/documents/${encodeURIComponent(doc.document_id)}/file`;

              return (
                <div
                  key={doc.document_id}
                  className="bg-white border-2 border-slate-100 hover:border-teal-200 rounded-2xl p-4 sm:p-5 transition shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="flex items-start space-x-3.5 flex-1 min-w-0">
                    <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-700 border border-teal-200 flex items-center justify-center flex-shrink-0 font-bold font-mono text-xs">
                      {doc.content_type.includes("pdf") ? "PDF" : "IMG"}
                    </div>

                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-slate-900 text-sm truncate max-w-xs sm:max-w-md" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-teal-100 text-teal-800">
                          {catObj?.label_en || doc.document_type}
                        </span>

                        {/* Phase 8 Processing Status Badge */}
                        {doc.processing_status === "processed" && (
                          <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center space-x-1">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Processed</span>
                          </span>
                        )}
                        {doc.processing_status === "needs_review" && (
                          <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-900 border border-amber-200 flex items-center space-x-1">
                            <AlertTriangle className="w-3 h-3" />
                            <span>Needs Review</span>
                          </span>
                        )}
                        {doc.processing_status === "processing" && (
                          <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-900 border border-blue-200 flex items-center space-x-1">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>Reading & Extracting...</span>
                          </span>
                        )}
                        {doc.processing_status === "uploaded" && (
                          <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
                            Uploaded
                          </span>
                        )}
                        {doc.processing_status === "failed" && (
                          <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-200">
                            Failed
                          </span>
                        )}

                        {/* Verification Status Pill */}
                        {doc.verification_status === "verified" ? (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Verified by {doc.verified_by || "Physician"}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-50 text-slate-500 border border-slate-200">
                            Unverified
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 font-medium">
                        <span>Size: {formatFileSize(doc.file_size)}</span>
                        <span>Uploaded: {formatDateTime(doc.uploaded_at)}</span>
                        <span className="font-mono text-[11px] text-slate-400">ID: {doc.document_id}</span>
                      </div>

                      {doc.notes && (
                        <p className="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 italic">
                          Note: {doc.notes}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap items-center gap-2 self-end sm:self-center">
                    {/* Process Button */}
                    {doc.processing_status === "uploaded" && (
                      <button
                        type="button"
                        onClick={() => handleProcessDocument(doc.document_id)}
                        disabled={isProcessingThis}
                        className="px-3 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-sm"
                      >
                        {isProcessingThis ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            <span>Reading...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>Process Document</span>
                          </>
                        )}
                      </button>
                    )}

                    {/* Review Extracted Data Button */}
                    {(doc.processing_status === "processed" || doc.processing_status === "needs_review") && (
                      <button
                        type="button"
                        onClick={() => setActiveReviewDoc(doc)}
                        className="px-3 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
                      >
                        <ClipboardList className="w-3.5 h-3.5" />
                        <span>Review Extracted Data</span>
                      </button>
                    )}

                    {/* View Original File */}
                    <a
                      href={downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-2 bg-slate-100 hover:bg-teal-50 hover:text-teal-700 text-slate-700 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Original</span>
                    </a>

                    {/* Delete */}
                    <button
                      type="button"
                      onClick={() => handleDeleteDocument(doc.document_id, doc.original_filename)}
                      disabled={deletingId === doc.document_id}
                      className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition"
                      title="Delete document"
                    >
                      {deletingId === doc.document_id ? (
                        <RefreshCw className="w-4 h-4 animate-spin text-rose-500" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Phase 8: Medical Review Modal */}
      {activeReviewDoc && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
          <div className="bg-white border border-slate-200 rounded-3xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-slate-100 flex items-start justify-between bg-slate-50/50">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <h3 className="text-lg font-bold text-slate-900">
                    Clinical Document Review
                  </h3>
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-teal-100 text-teal-800">
                    {activeReviewDoc.original_filename}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Patient: <strong className="text-slate-800">{patient.full_name}</strong> ({patient.token_number}) • Document ID: {activeReviewDoc.document_id}
                </p>
              </div>

              <button
                onClick={() => setActiveReviewDoc(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-xl hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-slate-200 px-6 bg-slate-50/30">
              <button
                type="button"
                onClick={() => setReviewTab("entities")}
                className={`py-3 px-4 text-xs sm:text-sm font-bold border-b-2 transition flex items-center space-x-2 ${
                  reviewTab === "entities"
                    ? "border-teal-600 text-teal-700 bg-white"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                <ClipboardList className="w-4 h-4" />
                <span>Extracted Medical Findings</span>
              </button>
              <button
                type="button"
                onClick={() => setReviewTab("raw_text")}
                className={`py-3 px-4 text-xs sm:text-sm font-bold border-b-2 transition flex items-center space-x-2 ${
                  reviewTab === "raw_text"
                    ? "border-teal-600 text-teal-700 bg-white"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                <FileSearch className="w-4 h-4" />
                <span>Raw OCR Output</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-slate-800">
              {reviewTab === "entities" ? (
                <div className="space-y-6">
                  {/* Physician Review Notice */}
                  <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start space-x-3 text-amber-900 text-xs">
                    <ShieldAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <p className="font-bold">Physician Verification Required</p>
                      <p className="text-amber-800">
                        Information is extracted directly from the uploaded record. It is tentative and must be verified by the attending physician before formal clinical use.
                      </p>
                    </div>
                  </div>

                  {/* Patient Info Card */}
                  {activeReviewDoc.extracted_data?.patient_info && (
                    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center space-x-1.5">
                        <User className="w-3.5 h-3.5" />
                        <span>Document Demographics</span>
                      </h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div>
                          <span className="text-slate-400 block">Stated Name:</span>
                          <strong className="text-slate-900">{activeReviewDoc.extracted_data.patient_info.name || "N/A"}</strong>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Age:</span>
                          <strong className="text-slate-900">{activeReviewDoc.extracted_data.patient_info.age || "N/A"}</strong>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Gender:</span>
                          <strong className="text-slate-900">{activeReviewDoc.extracted_data.patient_info.gender || "N/A"}</strong>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Document Date:</span>
                          <strong className="text-slate-900">{activeReviewDoc.extracted_data.patient_info.document_date || "N/A"}</strong>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Medications Table */}
                  {activeReviewDoc.extracted_data?.medications && activeReviewDoc.extracted_data.medications.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                        <Pill className="w-3.5 h-3.5 text-teal-600" />
                        <span>Prescription Medications ({activeReviewDoc.extracted_data.medications.length})</span>
                      </h4>
                      <div className="border border-slate-200 rounded-2xl overflow-hidden">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                            <tr>
                              <th className="p-3">Medicine</th>
                              <th className="p-3">Dosage</th>
                              <th className="p-3">Frequency</th>
                              <th className="p-3">Duration</th>
                              <th className="p-3">Confidence</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {activeReviewDoc.extracted_data.medications.map((m, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/70">
                                <td className="p-3 font-bold text-slate-900">{m.name}</td>
                                <td className="p-3 text-slate-700">{m.dosage || "-"}</td>
                                <td className="p-3 text-slate-700">{m.frequency || "-"}</td>
                                <td className="p-3 text-slate-700">{m.duration || "-"}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
                                    {Math.round((m.confidence || 0.8) * 100)}%
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Laboratory Investigations */}
                  {activeReviewDoc.extracted_data?.investigations && activeReviewDoc.extracted_data.investigations.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                        <Activity className="w-3.5 h-3.5 text-indigo-600" />
                        <span>Laboratory Investigations ({activeReviewDoc.extracted_data.investigations.length})</span>
                      </h4>
                      <div className="border border-slate-200 rounded-2xl overflow-hidden">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                            <tr>
                              <th className="p-3">Investigation / Test</th>
                              <th className="p-3">Observed Value</th>
                              <th className="p-3">Unit</th>
                              <th className="p-3">Reference Range</th>
                              <th className="p-3">Flag</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {activeReviewDoc.extracted_data.investigations.map((inv, idx) => (
                              <tr key={idx} className="hover:bg-slate-50/70">
                                <td className="p-3 font-bold text-slate-900">{inv.test_name}</td>
                                <td className="p-3 font-mono font-bold text-slate-900">{inv.result_value || "-"}</td>
                                <td className="p-3 text-slate-600">{inv.unit || "-"}</td>
                                <td className="p-3 text-slate-500">{inv.reference_range || "-"}</td>
                                <td className="p-3">
                                  {inv.is_abnormal ? (
                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                                      Abnormal
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                      Normal
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Diagnoses */}
                  {activeReviewDoc.extracted_data?.diagnoses && activeReviewDoc.extracted_data.diagnoses.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                        Documented Diagnoses & Conditions
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {activeReviewDoc.extracted_data.diagnoses.map((d, idx) => (
                          <div
                            key={idx}
                            className="bg-teal-50/60 border border-teal-200 rounded-xl px-3 py-2 text-xs text-teal-900 font-bold"
                          >
                            {d.diagnosis}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Procedures */}
                  {activeReviewDoc.extracted_data?.procedures && activeReviewDoc.extracted_data.procedures.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                        Procedures & Surgeries
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {activeReviewDoc.extracted_data.procedures.map((p, idx) => (
                          <div
                            key={idx}
                            className="bg-purple-50 border border-purple-200 rounded-xl px-3 py-2 text-xs text-purple-900 font-bold"
                          >
                            {p.procedure_name}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Allergies */}
                  {activeReviewDoc.extracted_data?.allergies && activeReviewDoc.extracted_data.allergies.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                        Documented Allergies
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {activeReviewDoc.extracted_data.allergies.map((a, idx) => (
                          <div
                            key={idx}
                            className="bg-rose-50 border border-rose-200 rounded-xl px-3 py-2 text-xs text-rose-900 font-bold"
                          >
                            {a.allergen}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Unclear Findings */}
                  {activeReviewDoc.extracted_data?.unclear_findings && activeReviewDoc.extracted_data.unclear_findings.length > 0 && (
                    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-1 text-xs">
                      <h4 className="font-bold text-slate-700 uppercase tracking-wider text-[11px]">
                        Ambiguous / Unclear Points for Attention
                      </h4>
                      <ul className="list-disc list-inside text-slate-600 space-y-0.5">
                        {activeReviewDoc.extracted_data.unclear_findings.map((uf, idx) => (
                          <li key={idx}>{uf}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                /* Raw OCR Text View */
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">
                      Engine: {activeReviewDoc.ocr_metadata?.engine || "Tesseract"} • Pages: {activeReviewDoc.ocr_metadata?.page_count || 1} • Duration: {activeReviewDoc.ocr_metadata?.processing_time_ms || 0} ms
                    </span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(activeReviewDoc.raw_ocr_text || "")}
                      className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition flex items-center space-x-1.5"
                    >
                      {copiedText ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Copy Raw Text</span>
                        </>
                      )}
                    </button>
                  </div>

                  <pre className="p-4 bg-slate-900 text-slate-100 font-mono text-xs rounded-2xl overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96">
                    {activeReviewDoc.raw_ocr_text || "No OCR text available."}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 sm:p-5 border-t border-slate-100 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3">
              <a
                href={`http://127.0.0.1:8000/api/patients/${encodeURIComponent(patient.patient_id)}/documents/${encodeURIComponent(
                  activeReviewDoc.document_id
                )}/file`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-xl text-xs font-bold transition flex items-center space-x-1.5"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Compare with Original File</span>
              </a>

              <div className="flex items-center space-x-3">
                {activeReviewDoc.verification_status !== "verified" ? (
                  <button
                    type="button"
                    onClick={() => handleVerifyDocument(activeReviewDoc.document_id)}
                    disabled={isVerifying}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center space-x-1.5"
                  >
                    {isVerifying ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Verifying...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Mark as Verified by Doctor</span>
                      </>
                    )}
                  </button>
                ) : (
                  <span className="px-4 py-2 bg-emerald-100 text-emerald-800 font-bold text-xs rounded-xl flex items-center space-x-1">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Verified</span>
                  </span>
                )}

                <button
                  type="button"
                  onClick={() => setActiveReviewDoc(null)}
                  className="px-4 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-100 transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-slate-500">Loading Documents Portal...</div>}>
      <DocumentsComponent />
    </Suspense>
  );
}
