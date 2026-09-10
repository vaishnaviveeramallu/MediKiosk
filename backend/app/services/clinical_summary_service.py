import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.database import (
    get_patients_collection,
    get_documents_collection,
    get_interview_sessions_collection,
    get_triage_alerts_collection,
)
from app.models.summary import (
    ClinicalSummarySection,
    ClinicalSummaryResponse,
)

logger = logging.getLogger("medikiosk.clinical_summary_service")

NOT_AVAILABLE_MSG = "Not available in the provided history/documents."


class ClinicalSummaryService:
    """
    Generates a structured, physician-ready draft clinical summary strictly from actual patient data
    retrieved from MongoDB (Registration, Interview Answers, Processed Documents, Triage Alerts).
    Adheres strictly to the 14 standard clinical sections.
    Guarantees zero hallucination / zero invention of medical entities.
    """

    async def generate_summary(
        self, patient_id: str, force_regenerate: bool = False
    ) -> ClinicalSummaryResponse:
        patients_col = get_patients_collection()
        docs_col = get_documents_collection()
        sessions_col = get_interview_sessions_collection()
        triage_col = get_triage_alerts_collection()

        # 1. Resolve patient document
        query_filter = None
        try:
            query_filter = {"_id": ObjectId(patient_id)}
        except InvalidId:
            query_filter = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(query_filter)
        if not patient_doc:
            raise ValueError(f"Patient '{patient_id}' not found in MongoDB.")

        canonical_pid = str(patient_doc["_id"])
        token_num = patient_doc.get("token_number", "")
        patient_name = patient_doc.get("full_name", "Patient")

        # 2. Check if a recent summary is cached and regeneration not forced
        if not force_regenerate and patient_doc.get("clinical_summary"):
            cached = patient_doc["clinical_summary"]
            if cached.get("sections"):
                try:
                    return ClinicalSummaryResponse(**cached)
                except Exception as e:
                    logger.warning(f"Could not parse cached summary, re-generating: {e}")

        # 3. Retrieve all authentic data
        # A. Interviews
        interview_cursor = sessions_col.find({"patient_id": canonical_pid}).sort("started_at", -1)
        interview_sessions = await interview_cursor.to_list(length=10)

        # B. Documents
        docs_cursor = docs_col.find({"patient_id": canonical_pid}).sort("uploaded_at", -1)
        documents = await docs_cursor.to_list(length=100)

        # C. Triage Alerts
        triage_cursor = triage_col.find({"patient_id": canonical_pid}).sort("detected_at", -1)
        triage_alerts = await triage_cursor.to_list(length=20)

        source_counts = {
            "interview_answers": sum(len(s.get("answers", [])) for s in interview_sessions),
            "documents": len(documents),
            "triage_alerts": len(triage_alerts),
        }

        # 4. Extract facts by section
        # Group interview answers by question_id/section
        interview_answers: Dict[str, List[Dict[str, Any]]] = {}
        for sess in interview_sessions:
            for ans in sess.get("answers", []):
                if ans.get("skipped"):
                    continue
                q_id = ans.get("question_id", "")
                sec = ans.get("section", "")
                ans_str = str(ans.get("patient_answer", "")).strip()
                if ans_str:
                    item = {
                        "text": ans_str,
                        "question": ans.get("question_text", ""),
                        "session_id": sess.get("session_id"),
                        "timestamp": ans.get("answered_at"),
                    }
                    interview_answers.setdefault(q_id, []).append(item)
                    if sec and sec != q_id:
                        interview_answers.setdefault(sec, []).append(item)

        sections: Dict[str, ClinicalSummarySection] = {}
        conflicts: List[str] = []
        unclear_items: List[str] = []

        # --- Section 1: Patient Information ---
        pat_lines = [
            f"Name: {patient_name}",
            f"OPD Token: {token_num}",
            f"Age: {patient_doc.get('age', 'N/A')}",
            f"Gender: {patient_doc.get('gender', 'N/A')}",
            f"Phone: {patient_doc.get('phone_number', 'N/A')}",
            f"Language: {str(patient_doc.get('preferred_language') or patient_doc.get('selected_language') or 'en').upper()}",
            f"Department: {patient_doc.get('department', 'General Medicine')}",
        ]
        sections["patient_info"] = ClinicalSummarySection(
            section_id="patient_info",
            section_number=1,
            title="Patient Information",
            content="\n".join(pat_lines),
            items=[{"label": l.split(":")[0], "value": l.split(":", 1)[1].strip()} for l in pat_lines],
            is_available=True,
            source_references=["Registration Intake"],
            requires_verification=False,
        )

        # --- Section 2: Chief Complaint ---
        cc_answers = interview_answers.get("chief_complaint", [])
        init_comp = patient_doc.get("initial_complaint")
        cc_text = ""
        cc_sources = []
        if cc_answers:
            cc_text = cc_answers[0]["text"]
            cc_sources.append("Clinical Intake Interview")
        elif init_comp:
            cc_text = init_comp
            cc_sources.append("Registration Intake")

        sections["chief_complaint"] = ClinicalSummarySection(
            section_id="chief_complaint",
            section_number=2,
            title="Chief Complaint",
            content=cc_text if cc_text else NOT_AVAILABLE_MSG,
            items=[{"complaint": cc_text}] if cc_text else [],
            is_available=bool(cc_text),
            source_references=cc_sources if cc_sources else ["None"],
            requires_verification=True,
        )

        # --- Section 3: History of Present Illness (HPI) ---
        hpi_items = []
        hpi_lines = []
        for q_key, ans_list in interview_answers.items():
            if q_key.startswith("hpi_") or q_key in ("hpi", "duration", "severity", "onset", "location"):
                for a in ans_list:
                    hpi_lines.append(f"- {a['question']}: {a['text']}")
                    hpi_items.append({"feature": a["question"], "details": a["text"]})

        hpi_avail = len(hpi_lines) > 0
        sections["hpi"] = ClinicalSummarySection(
            section_id="hpi",
            section_number=3,
            title="History of Present Illness (HPI)",
            content="\n".join(hpi_lines) if hpi_avail else NOT_AVAILABLE_MSG,
            items=hpi_items,
            is_available=hpi_avail,
            source_references=["Clinical Intake Interview"] if hpi_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 4: Relevant Past Medical History ---
        pmh_items = []
        pmh_sources = []
        # From interview
        pmh_answers = interview_answers.get("pmh_conditions", []) or interview_answers.get("past_medical", [])
        for a in pmh_answers:
            if "no" not in a["text"].lower() and "none" not in a["text"].lower():
                pmh_items.append({"condition": a["text"], "source": "Patient Interview"})
                pmh_sources.append("Patient Interview")

        # From documents
        for d in documents:
            for diag in d.get("extracted_data", {}).get("diagnoses", []):
                pmh_items.append({
                    "condition": diag.get("diagnosis"),
                    "source": f"Document ({d.get('original_filename', 'Doc')})"
                })
                pmh_sources.append(f"Doc {d.get('document_id')}")

        pmh_avail = len(pmh_items) > 0
        sections["past_medical_history"] = ClinicalSummarySection(
            section_id="past_medical_history",
            section_number=4,
            title="Relevant Past Medical History",
            content="\n".join(f"- {p['condition']} [{p['source']}]" for p in pmh_items) if pmh_avail else NOT_AVAILABLE_MSG,
            items=pmh_items,
            is_available=pmh_avail,
            source_references=list(set(pmh_sources)) if pmh_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 5: Past Surgical History ---
        surg_items = []
        surg_sources = []
        surg_answers = interview_answers.get("pmh_surgeries", []) or interview_answers.get("past_surgical", [])
        for a in surg_answers:
            if "no" not in a["text"].lower() and "none" not in a["text"].lower():
                surg_items.append({"procedure": a["text"], "source": "Patient Interview"})
                surg_sources.append("Patient Interview")

        for d in documents:
            for proc in d.get("extracted_data", {}).get("procedures", []):
                surg_items.append({
                    "procedure": proc.get("procedure_name"),
                    "date": proc.get("procedure_date"),
                    "source": f"Document ({d.get('original_filename', 'Doc')})"
                })
                surg_sources.append(f"Doc {d.get('document_id')}")

        surg_avail = len(surg_items) > 0
        sections["past_surgical_history"] = ClinicalSummarySection(
            section_id="past_surgical_history",
            section_number=5,
            title="Past Surgical History",
            content="\n".join(f"- {s['procedure']} [{s['source']}]" for s in surg_items) if surg_avail else NOT_AVAILABLE_MSG,
            items=surg_items,
            is_available=surg_avail,
            source_references=list(set(surg_sources)) if surg_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 6: Current / Previously Documented Medications ---
        med_items = []
        med_sources = []
        med_answers = interview_answers.get("medications_current", []) or interview_answers.get("medications", [])
        for a in med_answers:
            if "no" not in a["text"].lower() and "none" not in a["text"].lower():
                med_items.append({"name": a["text"], "details": "Reported by patient", "source": "Patient Interview"})
                med_sources.append("Patient Interview")

        for d in documents:
            for m in d.get("extracted_data", {}).get("medications", []):
                details_parts = [m.get("dosage"), m.get("frequency"), m.get("duration")]
                d_str = " ".join(p for p in details_parts if p)
                med_items.append({
                    "name": m.get("name"),
                    "dosage": m.get("dosage"),
                    "frequency": m.get("frequency"),
                    "duration": m.get("duration"),
                    "details": d_str,
                    "confidence": m.get("confidence"),
                    "source": f"Document ({d.get('original_filename', 'Doc')})"
                })
                med_sources.append(f"Doc {d.get('document_id')}")

        med_avail = len(med_items) > 0
        sections["medications"] = ClinicalSummarySection(
            section_id="medications",
            section_number=6,
            title="Current / Previously Documented Medications",
            content="\n".join(f"- {m['name']} ({m.get('details', '')}) [{m['source']}]" for m in med_items) if med_avail else NOT_AVAILABLE_MSG,
            items=med_items,
            is_available=med_avail,
            source_references=list(set(med_sources)) if med_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 7: Allergies ---
        allg_items = []
        allg_sources = []
        allg_answers = interview_answers.get("allergies_known", []) or interview_answers.get("allergies", [])
        interview_denies_allergy = False

        for a in allg_answers:
            allg_items.append({"allergen": a["text"], "source": "Patient Interview"})
            allg_sources.append("Patient Interview")
            if any(neg in a["text"].lower() for neg in ["no", "none", "nil", "nkda", "denies"]):
                interview_denies_allergy = True

        for d in documents:
            for allg in d.get("extracted_data", {}).get("allergies", []):
                allg_name = allg.get("allergen")
                allg_items.append({
                    "allergen": allg_name,
                    "severity": allg.get("severity"),
                    "source": f"Document ({d.get('original_filename', 'Doc')})"
                })
                allg_sources.append(f"Doc {d.get('document_id')}")

                # Detect conflict: Interview says no allergies but document lists penicillin/etc.
                if interview_denies_allergy and "nkda" not in allg_name.lower() and "none" not in allg_name.lower():
                    conf_msg = (
                        f"Conflicting allergy record: Patient reported '{allg_answers[0]['text']}' in interview, "
                        f"but medical document ({d.get('original_filename')}) states '{allg_name}' — physician verification required."
                    )
                    conflicts.append(conf_msg)

        allg_avail = len(allg_items) > 0
        sections["allergies"] = ClinicalSummarySection(
            section_id="allergies",
            section_number=7,
            title="Allergies",
            content="\n".join(f"- {a['allergen']} [{a['source']}]" for a in allg_items) if allg_avail else NOT_AVAILABLE_MSG,
            items=allg_items,
            is_available=allg_avail,
            source_references=list(set(allg_sources)) if allg_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 8: Family History ---
        fam_answers = interview_answers.get("family_history", [])
        fam_avail = len(fam_answers) > 0 and not any(neg in fam_answers[0]["text"].lower() for neg in ["not known", "no specific"])
        sections["family_history"] = ClinicalSummarySection(
            section_id="family_history",
            section_number=8,
            title="Family History",
            content="\n".join(f"- {a['text']}" for a in fam_answers) if fam_answers else NOT_AVAILABLE_MSG,
            items=[{"history": a["text"]} for a in fam_answers],
            is_available=bool(fam_answers),
            source_references=["Clinical Intake Interview"] if fam_answers else ["None"],
            requires_verification=True,
        )

        # --- Section 9: Social / Lifestyle History ---
        soc_answers = interview_answers.get("social_habits", []) or interview_answers.get("social_history", [])
        soc_avail = len(soc_answers) > 0
        sections["social_history"] = ClinicalSummarySection(
            section_id="social_history",
            section_number=9,
            title="Social / Lifestyle History",
            content="\n".join(f"- {a['text']}" for a in soc_answers) if soc_avail else NOT_AVAILABLE_MSG,
            items=[{"habit": a["text"]} for a in soc_answers],
            is_available=soc_avail,
            source_references=["Clinical Intake Interview"] if soc_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 10: Investigations and Results ---
        lab_items = []
        lab_sources = []
        for d in documents:
            for inv in d.get("extracted_data", {}).get("investigations", []):
                lab_items.append({
                    "test_name": inv.get("test_name"),
                    "result_value": inv.get("result_value"),
                    "unit": inv.get("unit"),
                    "reference_range": inv.get("reference_range"),
                    "is_abnormal": inv.get("is_abnormal"),
                    "source": f"Lab Report ({d.get('original_filename', 'Doc')})"
                })
                lab_sources.append(f"Doc {d.get('document_id')}")

        lab_avail = len(lab_items) > 0
        sections["investigations"] = ClinicalSummarySection(
            section_id="investigations",
            section_number=10,
            title="Investigations and Results",
            content="\n".join(
                f"- {l['test_name']}: {l['result_value'] or ''} {l['unit'] or ''} (Ref: {l['reference_range'] or 'N/A'})"
                f"{' [ABNORMAL]' if l['is_abnormal'] else ''} [{l['source']}]"
                for l in lab_items
            ) if lab_avail else NOT_AVAILABLE_MSG,
            items=lab_items,
            is_available=lab_avail,
            source_references=list(set(lab_sources)) if lab_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 11: Procedures / Hospitalizations ---
        proc_items = [p for p in surg_items if "Procedure" in p.get("source", "") or "Doc" in p.get("source", "")]
        proc_avail = len(proc_items) > 0
        sections["procedures_hospitalizations"] = ClinicalSummarySection(
            section_id="procedures_hospitalizations",
            section_number=11,
            title="Procedures / Hospitalizations",
            content="\n".join(f"- {p['procedure']} [{p['source']}]" for p in proc_items) if proc_avail else NOT_AVAILABLE_MSG,
            items=proc_items,
            is_available=proc_avail,
            source_references=list(set(p["source"] for p in proc_items)) if proc_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 12: Red Flags / Triage Alerts ---
        triage_items = []
        for alert in triage_alerts:
            triage_items.append({
                "alert_id": alert.get("alert_id"),
                "category": alert.get("detected_category"),
                "priority": alert.get("priority"),
                "trigger": alert.get("triggering_answer"),
                "status": alert.get("status"),
                "detected_at": str(alert.get("detected_at")),
            })

        triage_avail = len(triage_items) > 0
        sections["red_flags_triage"] = ClinicalSummarySection(
            section_id="red_flags_triage",
            section_number=12,
            title="Red Flags / Triage Alerts",
            content="\n".join(
                f"- [{t['priority']}] {t['category'].replace('_', ' ').title()}: '{t['trigger']}' (Status: {t['status']})"
                for t in triage_items
            ) if triage_avail else "No red-flag danger signs detected during intake.",
            items=triage_items,
            is_available=triage_avail,
            source_references=["Automated Red-Flag Detector"] if triage_avail else ["None"],
            requires_verification=False,
        )

        # --- Section 13: Important Document Findings ---
        doc_findings = []
        for d in documents:
            ext = d.get("extracted_data") or {}
            if ext.get("hospital_clinic_info"):
                doc_findings.append(f"- Healthcare facility: {ext['hospital_clinic_info']} (Doc ID: {d.get('document_id')})")
            if ext.get("doctor_info"):
                doc_findings.append(f"- Prescribing doctor: {ext['doctor_info']} (Doc ID: {d.get('document_id')})")
            if d.get("notes"):
                doc_findings.append(f"- Document note: {d['notes']}")

        doc_avail = len(doc_findings) > 0
        sections["document_findings"] = ClinicalSummarySection(
            section_id="document_findings",
            section_number=13,
            title="Important Document Findings",
            content="\n".join(doc_findings) if doc_avail else NOT_AVAILABLE_MSG,
            items=[{"finding": f} for f in doc_findings],
            is_available=doc_avail,
            source_references=[f"Doc {d.get('document_id')}" for d in documents] if doc_avail else ["None"],
            requires_verification=True,
        )

        # --- Section 14: Information Requiring Verification ---
        for d in documents:
            ext = d.get("extracted_data") or {}
            for uf in ext.get("unclear_findings", []):
                unclear_items.append(f"Document {d.get('document_id')}: {uf}")
            if d.get("ocr_metadata", {}).get("handwritten_detected"):
                unclear_items.append(f"Document {d.get('document_id')} contains handwritten text: physician verification required.")

        for c in conflicts:
            unclear_items.append(f"[CONFLICT] {c}")

        unclear_avail = len(unclear_items) > 0
        sections["requires_verification"] = ClinicalSummarySection(
            section_id="requires_verification",
            section_number=14,
            title="Information Requiring Verification",
            content="\n".join(f"- {u}" for u in unclear_items) if unclear_avail else "All extracted findings appear clear and consistent. Standard physician sign-off required.",
            items=[{"item": u} for u in unclear_items],
            is_available=unclear_avail,
            source_references=["Clinical Extraction Engine"],
            requires_verification=True,
        )

        # 5. Build Full Narrative Clinical Summary Draft
        summary_lines = [
            "================================================================================",
            f"MEDIKIOSK AI CLINICAL SUMMARY DRAFT — PHYSICIAN VERIFICATION REQUIRED",
            "================================================================================",
            f"Patient: {patient_name}  |  OPD Token: {token_num}  |  Age: {patient_doc.get('age', 'N/A')}  |  Gender: {patient_doc.get('gender', 'N/A')}",
            f"Date Generated: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}",
            "Status: AI-Generated Draft — Pending Physician Verification",
            "--------------------------------------------------------------------------------",
            "",
            "1. PATIENT INFORMATION",
            sections["patient_info"].content,
            "",
            "2. CHIEF COMPLAINT",
            sections["chief_complaint"].content,
            "",
            "3. HISTORY OF PRESENT ILLNESS (HPI)",
            sections["hpi"].content,
            "",
            "4. RELEVANT PAST MEDICAL HISTORY",
            sections["past_medical_history"].content,
            "",
            "5. PAST SURGICAL HISTORY",
            sections["past_surgical_history"].content,
            "",
            "6. MEDICATIONS (CURRENT / PREVIOUSLY DOCUMENTED)",
            sections["medications"].content,
            "",
            "7. ALLERGIES",
            sections["allergies"].content,
            "",
            "8. FAMILY HISTORY",
            sections["family_history"].content,
            "",
            "9. SOCIAL / LIFESTYLE HISTORY",
            sections["social_history"].content,
            "",
            "10. INVESTIGATIONS AND RESULTS",
            sections["investigations"].content,
            "",
            "11. PROCEDURES / HOSPITALIZATIONS",
            sections["procedures_hospitalizations"].content,
            "",
            "12. RED FLAGS / TRIAGE ALERTS",
            sections["red_flags_triage"].content,
            "",
            "13. IMPORTANT DOCUMENT FINDINGS",
            sections["document_findings"].content,
            "",
            "14. INFORMATION REQUIRING PHYSICIAN VERIFICATION",
            sections["requires_verification"].content,
            "",
            "================================================================================",
            "CLINICAL GOVERNANCE NOTICE:",
            "This summary is an automated organizational draft prepared for the attending physician.",
            "It does NOT constitute an autonomous diagnosis or treatment plan.",
            "================================================================================",
        ]

        full_draft = "\n".join(summary_lines)

        response = ClinicalSummaryResponse(
            patient_id=canonical_pid,
            token_number=token_num,
            patient_name=patient_name,
            summary_draft=full_draft,
            sections=sections,
            disclaimer="AI-generated draft — physician verification required. Not a medical diagnosis.",
            verification_status="needs_review",
            generated_at=datetime.now(timezone.utc),
            source_counts=source_counts,
            conflicting_findings=conflicts,
        )

        # 6. Persist summary inside patient record in MongoDB
        try:
            summary_dict = response.model_dump()
            # Convert datetime objects to string/iso for MongoDB driver if needed
            await patients_col.update_one(
                {"_id": patient_doc["_id"]},
                {"$set": {"clinical_summary": summary_dict}}
            )
        except Exception as e:
            logger.warning(f"Could not persist clinical_summary to MongoDB: {e}")

        return response


# Singleton instance
clinical_summary_service = ClinicalSummaryService()
