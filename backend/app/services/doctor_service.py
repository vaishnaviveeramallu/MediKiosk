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
from app.models.doctor import (
    DoctorReviewStatus,
    DoctorQueuePatient,
    DoctorQueueResponse,
    SummaryVersionRecord,
    SummaryEditRequest,
    SummaryConfirmRequest,
    ReviewStatusUpdateRequest,
    PatientClinicalDetailResponse,
)
from app.services.medical_timeline_service import medical_timeline_service
from app.services.clinical_summary_service import clinical_summary_service

logger = logging.getLogger("medikiosk.doctor_service")


class DoctorService:
    """
    Core business logic for the Physician / Doctor Dashboard:
    - Queue aggregation with real-time clinical and review status
    - 8-section clinical dossier retrieval for patient review
    - Physician draft summary editing with version history tracking
    - Formal physician verification & confirmation
    - Zero mock data guarantee: strictly uses authentic MongoDB collections
    """

    async def _resolve_patient(self, patient_id: str) -> dict:
        patients_col = get_patients_collection()
        query_filter = None
        try:
            query_filter = {"_id": ObjectId(patient_id)}
        except InvalidId:
            query_filter = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(query_filter)
        if not patient_doc:
            raise ValueError(f"Patient with identifier '{patient_id}' not found in MongoDB.")
        return patient_doc

    async def get_doctor_queue(
        self,
        search: Optional[str] = None,
        triage_filter: Optional[str] = None,
        review_status_filter: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> DoctorQueueResponse:
        """
        Retrieves live patients from MongoDB and dynamically aggregates their clinical
        intake, triage, document, timeline, and review states. Zero mock data.
        """
        patients_col = get_patients_collection()
        sessions_col = get_interview_sessions_collection()
        docs_col = get_documents_collection()
        triage_col = get_triage_alerts_collection()

        # Build initial query filter
        query: Dict[str, Any] = {}
        if search and search.strip():
            term = search.strip()
            query["$or"] = [
                {"full_name": {"$regex": term, "$options": "i"}},
                {"token_number": {"$regex": term, "$options": "i"}},
                {"phone_number": {"$regex": term, "$options": "i"}},
            ]
            try:
                query["$or"].append({"_id": ObjectId(term)})
            except Exception:
                pass

        cursor = patients_col.find(query).sort("created_at", -1)
        raw_patients = await cursor.to_list(length=300)

        queue_items: List[DoctorQueuePatient] = []
        pending_count = 0
        in_review_count = 0
        needs_verif_count = 0
        confirmed_count = 0
        high_triage_count = 0

        for p in raw_patients:
            canonical_pid = str(p["_id"])
            token_num = p.get("token_number", "MK-OPD")

            # 1. Triage status
            triage_cursor = triage_col.find({"patient_id": canonical_pid, "status": "active"})
            active_alerts = await triage_cursor.to_list(length=20)
            alert_count = len(active_alerts)
            highest_priority = None
            t_status = "normal"

            if alert_count > 0:
                high_triage_count += 1
                has_crit = any(a.get("priority") == "CRITICAL" for a in active_alerts)
                t_status = "critical" if has_crit else "high_alert"
                highest_priority = "CRITICAL" if has_crit else "HIGH"

            # 2. Interview status
            sess = await sessions_col.find_one({"patient_id": canonical_pid}, sort=[("started_at", -1)])
            int_status = "not_started"
            ans_count = 0
            if sess:
                int_status = sess.get("status", "in_progress")
                ans_count = len(sess.get("answers", []))
            elif p.get("registration_status") == "interview_completed":
                int_status = "completed"

            # 3. Documents count
            doc_count = await docs_col.count_documents({"patient_id": canonical_pid})
            proc_doc_count = await docs_col.count_documents({
                "patient_id": canonical_pid,
                "processing_status": {"$in": ["processed", "completed"]}
            })

            # 4. Summary & Review status
            summary_obj = p.get("clinical_summary") or {}
            has_summary = bool(summary_obj.get("sections") or summary_obj.get("summary_draft"))

            # Determine review status
            rev_status = p.get("doctor_review_status")
            if not rev_status:
                if p.get("physician_confirmed"):
                    rev_status = "physician_confirmed"
                elif p.get("physician_reviewed"):
                    rev_status = "in_review"
                else:
                    rev_status = "pending_review"

            # Check conflicts
            timeline_obj = p.get("medical_timeline") or {}
            has_conflicts = bool(timeline_obj.get("has_conflicts") or summary_obj.get("conflicting_findings"))
            conflict_count = int(timeline_obj.get("conflict_count", len(summary_obj.get("conflicting_findings", []))))

            if has_conflicts and rev_status == "pending_review":
                rev_status = "needs_verification"

            # Determine summary progression status
            if p.get("physician_confirmed") or summary_obj.get("verification_status") == "physician_confirmed":
                sum_status = "physician_confirmed"
            elif p.get("physician_reviewed") or summary_obj.get("verification_status") == "physician_reviewed":
                sum_status = "physician_reviewed"
            elif has_summary:
                sum_status = "ai_generated"
            else:
                sum_status = "not_generated"

            # Update metrics
            if rev_status == "physician_confirmed":
                confirmed_count += 1
            elif rev_status == "in_review":
                in_review_count += 1
            elif rev_status == "needs_verification":
                needs_verif_count += 1
            else:
                pending_count += 1

            # Check triage & review filters
            if triage_filter and triage_filter.lower() != "all":
                if triage_filter.lower() == "high_alert" and t_status not in ["high_alert", "critical"]:
                    continue
                elif triage_filter.lower() == "normal" and t_status != "normal":
                    continue

            if review_status_filter and review_status_filter.lower() != "all":
                if rev_status.lower() != review_status_filter.lower():
                    continue

            last_act = p.get("created_at")
            if sess and sess.get("last_updated_at"):
                last_act = sess["last_updated_at"]
            elif p.get("physician_confirmed_at"):
                last_act = p["physician_confirmed_at"]

            queue_items.append(
                DoctorQueuePatient(
                    patient_id=canonical_pid,
                    token_number=token_num,
                    full_name=p.get("full_name", "Patient"),
                    age=p.get("age", 0),
                    gender=p.get("gender", "Unknown"),
                    phone_number=p.get("phone_number", "N/A"),
                    address_city=p.get("address_city"),
                    registration_date=p.get("created_at", datetime.now(timezone.utc)),
                    preferred_language=p.get("selected_language") or p.get("preferred_language") or "en",
                    initial_complaint=p.get("initial_complaint"),
                    triage_status=t_status,
                    active_triage_alerts=alert_count,
                    highest_triage_priority=highest_priority,
                    interview_status=int_status,
                    interview_answers_count=ans_count,
                    document_count=doc_count,
                    processed_document_count=proc_doc_count,
                    has_summary=has_summary,
                    summary_status=sum_status,
                    doctor_review_status=rev_status,
                    has_conflicts=has_conflicts,
                    conflict_count=conflict_count,
                    last_activity=last_act,
                )
            )

        # Pagination slice
        paginated_patients = queue_items[skip : skip + limit]

        return DoctorQueueResponse(
            total_patients=len(queue_items),
            pending_review_count=pending_count,
            in_review_count=in_review_count,
            needs_verification_count=needs_verif_count,
            confirmed_count=confirmed_count,
            high_triage_count=high_triage_count,
            patients=paginated_patients,
        )

    async def get_patient_clinical_detail(self, patient_id: str) -> PatientClinicalDetailResponse:
        """
        Gathers the complete 8-section clinical dossier for an authentic patient from MongoDB:
        1. Patient Profile
        2. Clinical Interview (Verbatim Q&A pairs)
        3. Red Flags / Triage Alerts
        4. Medical Documents
        5. OCR Extracted Information
        6. Medical Timeline
        7. Cross-Source Conflicts
        8. AI Clinical Summary & Physician Review
        """
        patient_doc = await self._resolve_patient(patient_id)
        canonical_pid = str(patient_doc["_id"])

        sessions_col = get_interview_sessions_collection()
        docs_col = get_documents_collection()
        triage_col = get_triage_alerts_collection()

        # 1. Patient Profile
        patient_data = {
            "patient_id": canonical_pid,
            "token_number": patient_doc.get("token_number", ""),
            "full_name": patient_doc.get("full_name", ""),
            "age": patient_doc.get("age"),
            "gender": patient_doc.get("gender"),
            "phone_number": patient_doc.get("phone_number"),
            "address_city": patient_doc.get("address_city"),
            "address_state": patient_doc.get("address_state"),
            "government_id_type": patient_doc.get("government_id_type"),
            "government_id_number": patient_doc.get("government_id_number"),
            "initial_complaint": patient_doc.get("initial_complaint"),
            "registration_status": patient_doc.get("registration_status"),
            "selected_language": patient_doc.get("selected_language") or patient_doc.get("preferred_language") or "en",
            "consent_status": patient_doc.get("consent_status", "pending"),
            "created_at": str(patient_doc.get("created_at")),
        }

        # 2. Clinical Interview Q&A
        sess = await sessions_col.find_one({"patient_id": canonical_pid}, sort=[("started_at", -1)])
        interview_data: Dict[str, Any] = {
            "session_id": sess.get("session_id") if sess else None,
            "status": sess.get("status", "not_started") if sess else "not_started",
            "started_at": str(sess.get("started_at")) if sess else None,
            "completed_at": str(sess.get("completed_at")) if sess else None,
            "answered_count": len(sess.get("answers", [])) if sess else 0,
            "answers": [],
        }
        if sess:
            for ans in sess.get("answers", []):
                interview_data["answers"].append({
                    "question_id": ans.get("question_id"),
                    "question_text": ans.get("question_text", "Intake Question"),
                    "patient_answer": ans.get("patient_answer", ""),
                    "section": ans.get("section", ""),
                    "answered_at": str(ans.get("answered_at")),
                    "input_method": ans.get("input_method", "text"),
                    "skipped": ans.get("skipped", False),
                })

        # 3. Red Flags / Triage Alerts
        triage_cursor = triage_col.find({"patient_id": canonical_pid}).sort("detected_at", -1)
        raw_alerts = await triage_cursor.to_list(length=50)
        triage_alerts = []
        for a in raw_alerts:
            triage_alerts.append({
                "alert_id": a.get("alert_id"),
                "category": a.get("detected_category", ""),
                "priority": a.get("priority", "HIGH"),
                "triggering_answer": a.get("triggering_answer", ""),
                "detected_at": str(a.get("detected_at")),
                "status": a.get("status", "active"),
                "staff_acknowledged": a.get("staff_acknowledged", False),
            })

        # 4. Medical Documents
        docs_cursor = docs_col.find({"patient_id": canonical_pid}).sort("uploaded_at", -1)
        raw_docs = await docs_cursor.to_list(length=50)
        documents = []
        extracted_diagnoses = []
        extracted_meds = []
        extracted_labs = []
        extracted_procs = []
        extracted_allgs = []
        unclear_findings = []

        for d in raw_docs:
            d_id = d.get("document_id")
            fname = d.get("original_filename", "Document")
            documents.append({
                "document_id": d_id,
                "original_filename": fname,
                "document_type": d.get("document_type", "other"),
                "file_size": d.get("file_size", 0),
                "uploaded_at": str(d.get("uploaded_at")),
                "processing_status": d.get("processing_status", "uploaded"),
                "ocr_status": d.get("ocr_status"),
                "verification_status": d.get("verification_status", "unverified"),
                "has_ocr": bool(d.get("raw_ocr_text")),
                "notes": d.get("notes"),
            })

            ext = d.get("extracted_data") or {}
            for diag in ext.get("diagnoses", []):
                extracted_diagnoses.append({**diag, "source_document": fname, "document_id": d_id})
            for med in ext.get("medications", []):
                extracted_meds.append({**med, "source_document": fname, "document_id": d_id})
            for lab in ext.get("investigations", []):
                extracted_labs.append({**lab, "source_document": fname, "document_id": d_id})
            for proc in ext.get("procedures", []):
                extracted_procs.append({**proc, "source_document": fname, "document_id": d_id})
            for allg in ext.get("allergies", []):
                extracted_allgs.append({**allg, "source_document": fname, "document_id": d_id})
            for unc in ext.get("unclear_findings", []):
                unclear_findings.append({
                    "finding": unc,
                    "source_document": fname,
                    "document_id": d_id,
                    "status": "needs_verification",
                })

        # 5. OCR Extracted Information Map
        ocr_extracted = {
            "diagnoses": extracted_diagnoses,
            "medications": extracted_meds,
            "investigations": extracted_labs,
            "procedures": extracted_procs,
            "allergies": extracted_allgs,
            "unclear_findings": unclear_findings,
        }

        # 6. Medical Timeline
        timeline_res = await medical_timeline_service.build_timeline(canonical_pid)
        timeline_data = timeline_res.model_dump()

        # 7. Cross-Source Conflicts
        conflicts = []
        for ev in timeline_res.dated_events + timeline_res.undated_events:
            if ev.is_conflict:
                conflicts.append({
                    "event_id": ev.event_id,
                    "title": ev.title,
                    "notes": ev.conflict_notes,
                    "source": ev.source_label,
                    "requires_physician_verification": True,
                })

        # 8. AI Clinical Summary & Review info
        summary_res = await clinical_summary_service.generate_summary(canonical_pid, force_regenerate=False)
        summary_data = summary_res.model_dump()

        # Review info
        current_rev_status = patient_doc.get("doctor_review_status")
        if not current_rev_status:
            current_rev_status = "physician_confirmed" if patient_doc.get("physician_confirmed") else "pending_review"

        review_info = {
            "doctor_review_status": current_rev_status,
            "physician_reviewed": patient_doc.get("physician_reviewed", False),
            "physician_reviewed_at": str(patient_doc.get("physician_reviewed_at")) if patient_doc.get("physician_reviewed_at") else None,
            "physician_confirmed": patient_doc.get("physician_confirmed", False),
            "physician_confirmed_at": str(patient_doc.get("physician_confirmed_at")) if patient_doc.get("physician_confirmed_at") else None,
            "confirmed_by": summary_data.get("confirmed_by") or patient_doc.get("confirmed_by"),
            "physician_notes": patient_doc.get("physician_notes"),
            "version_history": (patient_doc.get("clinical_summary") or {}).get("version_history", []),
            "original_ai_draft": (patient_doc.get("clinical_summary") or {}).get("original_ai_draft"),
        }

        return PatientClinicalDetailResponse(
            patient=patient_data,
            interview=interview_data,
            triage_alerts=triage_alerts,
            documents=documents,
            ocr_extracted=ocr_extracted,
            timeline=timeline_data,
            summary=summary_data,
            conflicts=conflicts,
            review_info=review_info,
        )

    async def save_summary_draft(
        self, patient_id: str, edit_payload: SummaryEditRequest
    ) -> Dict[str, Any]:
        """
        Saves physician modifications to the clinical summary in MongoDB.
        Preserves past draft versions in `version_history` to guarantee full auditability.
        """
        patients_col = get_patients_collection()
        patient_doc = await self._resolve_patient(patient_id)
        canonical_pid = str(patient_doc["_id"])

        now = datetime.now(timezone.utc)
        current_sum = patient_doc.get("clinical_summary")
        if not current_sum:
            gen_res = await clinical_summary_service.generate_summary(canonical_pid, force_regenerate=True)
            current_sum = gen_res.model_dump()

        # Archive version history
        history = current_sum.get("version_history", [])
        original_draft = current_sum.get("original_ai_draft") or current_sum.get("summary_draft")

        archived_version = {
            "version": len(history) + 1,
            "summary_draft": current_sum.get("summary_draft"),
            "modified_at": now.isoformat(),
            "modified_by": edit_payload.doctor_name or "Attending Physician",
            "reason": edit_payload.physician_notes or "Physician draft edit",
        }
        history.append(archived_version)

        # Update draft text if provided
        updated_draft = edit_payload.summary_draft or current_sum.get("summary_draft")
        current_sum["summary_draft"] = updated_draft
        current_sum["original_ai_draft"] = original_draft
        current_sum["version_history"] = history
        current_sum["verification_status"] = "physician_reviewed"
        current_sum["last_modified_at"] = now.isoformat()
        current_sum["modified_by"] = edit_payload.doctor_name

        # Update sections if modified
        if edit_payload.sections and isinstance(current_sum.get("sections"), dict):
            for sec_key, sec_mod in edit_payload.sections.items():
                if sec_key in current_sum["sections"] and isinstance(sec_mod, dict):
                    if "content" in sec_mod:
                        current_sum["sections"][sec_key]["content"] = sec_mod["content"]

        # Persist in MongoDB
        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {
                "$set": {
                    "clinical_summary": current_sum,
                    "doctor_review_status": "in_review",
                    "physician_reviewed": True,
                    "physician_reviewed_at": now,
                    "physician_notes": edit_payload.physician_notes or patient_doc.get("physician_notes"),
                }
            }
        )

        logger.info(f"Physician draft saved for patient {canonical_pid} (Version {len(history)})")
        return current_sum

    async def confirm_summary(
        self, patient_id: str, confirm_payload: Optional[SummaryConfirmRequest] = None
    ) -> Dict[str, Any]:
        """
        Transitions summary state to PHYSICIAN CONFIRMED.
        Idempotent: prevents duplicate confirmation errors.
        """
        patients_col = get_patients_collection()
        patient_doc = await self._resolve_patient(patient_id)
        canonical_pid = str(patient_doc["_id"])

        now = datetime.now(timezone.utc)
        doctor_name = (confirm_payload.confirmed_by if confirm_payload else None) or "Attending Physician"
        notes = (confirm_payload.doctor_notes if confirm_payload else None) or "Clinical summary verified and confirmed."

        current_sum = patient_doc.get("clinical_summary")
        if not current_sum:
            gen_res = await clinical_summary_service.generate_summary(canonical_pid, force_regenerate=True)
            current_sum = gen_res.model_dump()

        # Update summary confirmation fields
        current_sum["verification_status"] = "physician_confirmed"
        current_sum["confirmed_by"] = doctor_name
        current_sum["confirmed_at"] = now.isoformat()
        current_sum["physician_notes"] = notes

        # Update patient document
        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {
                "$set": {
                    "clinical_summary": current_sum,
                    "doctor_review_status": "physician_confirmed",
                    "physician_confirmed": True,
                    "physician_confirmed_at": now,
                    "confirmed_by": doctor_name,
                    "physician_notes": notes,
                },
                "$push": {
                    "audit_trail": {
                        "action": "physician_confirmed",
                        "timestamp": now,
                        "actor": doctor_name,
                        "notes": notes,
                    }
                }
            }
        )

        logger.info(f"Clinical summary confirmed by {doctor_name} for patient {canonical_pid}")
        return current_sum

    async def update_review_status(
        self, patient_id: str, status_payload: ReviewStatusUpdateRequest
    ) -> Dict[str, Any]:
        """
        Allows physician to update the patient review state (e.g. 'in_review', 'needs_verification').
        """
        patients_col = get_patients_collection()
        patient_doc = await self._resolve_patient(patient_id)
        canonical_pid = str(patient_doc["_id"])

        valid_statuses = [
            DoctorReviewStatus.PENDING_REVIEW.value,
            DoctorReviewStatus.IN_REVIEW.value,
            DoctorReviewStatus.NEEDS_VERIFICATION.value,
            DoctorReviewStatus.PHYSICIAN_CONFIRMED.value,
        ]
        val = status_payload.review_status.strip().lower()
        if val not in valid_statuses:
            raise ValueError(f"Invalid review status '{status_payload.review_status}'. Must be one of: {valid_statuses}")

        now = datetime.now(timezone.utc)
        update_doc: Dict[str, Any] = {
            "doctor_review_status": val,
            "last_status_update": now,
        }
        if status_payload.notes:
            update_doc["physician_notes"] = status_payload.notes

        if val == "physician_confirmed":
            update_doc["physician_confirmed"] = True
            update_doc["physician_confirmed_at"] = now
        elif val == "in_review":
            update_doc["physician_reviewed"] = True
            update_doc["physician_reviewed_at"] = now

        await patients_col.update_one({"_id": patient_doc["_id"]}, {"$set": update_doc})

        return {
            "patient_id": canonical_pid,
            "doctor_review_status": val,
            "updated_at": now.isoformat(),
            "notes": status_payload.notes,
        }


doctor_service = DoctorService()
