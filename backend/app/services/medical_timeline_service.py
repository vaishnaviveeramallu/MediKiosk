import re
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.database import (
    get_database,
    get_patients_collection,
    get_documents_collection,
    get_interview_sessions_collection,
    get_triage_alerts_collection,
)
from app.models.summary import (
    TimelineEvent,
    TimelineEventType,
    MedicalTimelineResponse,
)

logger = logging.getLogger("medikiosk.medical_timeline_service")


class MedicalTimelineService:
    """
    Constructs an authentic, chronological medical timeline by aggregating real patient
    interview responses, OCR-extracted medical document findings, and triage alerts from MongoDB.
    Strictly preserves source provenance and never fabricates dates or clinical events.
    """

    def _parse_date_string(self, date_str: Optional[str]) -> Tuple[Optional[str], str]:
        """
        Safely parse various date formats into an ISO string (YYYY-MM-DD) and a display label.
        Returns (iso_date_or_None, display_label).
        Never guesses or interpolates missing dates.
        """
        if not date_str or not str(date_str).strip():
            return None, "Date not specified"

        clean_str = str(date_str).strip()

        # Handle datetime objects
        if isinstance(date_str, datetime):
            iso_val = date_str.strftime("%Y-%m-%d")
            return iso_val, date_str.strftime("%d %b %Y")

        # ISO format: YYYY-MM-DD
        m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", clean_str)
        if m_iso:
            y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
            try:
                dt = datetime(y, m, d)
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %b %Y")
            except ValueError:
                pass

        # DD/MM/YYYY or DD-MM-YYYY
        m_dmy = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})", clean_str)
        if m_dmy:
            day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            if year < 100:
                year += 2000
            try:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %b %Y")
            except ValueError:
                pass

        # Month name formats: 10 Sep 2026, September 10 2026
        for fmt in ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y"):
            try:
                dt = datetime.strptime(clean_str, fmt)
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %b %Y")
            except ValueError:
                continue

        # If date string cannot be strictly parsed into a valid calendar date
        return None, clean_str

    async def build_timeline(self, patient_id: str) -> MedicalTimelineResponse:
        """
        Build and persist a chronological medical timeline for a verified patient.
        """
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

        all_events: List[TimelineEvent] = []

        # 2. Extract events from Registration
        reg_created = patient_doc.get("created_at")
        iso_reg, disp_reg = self._parse_date_string(reg_created)
        init_complaint = patient_doc.get("initial_complaint")
        if init_complaint:
            all_events.append(TimelineEvent(
                event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                event_date=iso_reg,
                display_date=disp_reg,
                event_type=TimelineEventType.SYMPTOM_REPORTED,
                title=f"Initial OPD Complaint: {init_complaint}",
                details={"complaint": init_complaint, "department": patient_doc.get("department")},
                source="patient_interview",
                source_label="Registration Intake",
                source_document_id=None,
                source_session_id=None,
                verification_status="verified",
            ))

        # 3. Extract events from Interview Sessions
        interview_cursor = sessions_col.find({"patient_id": canonical_pid})
        interview_sessions = await interview_cursor.to_list(length=10)

        interview_allergies = []
        interview_medications = []

        for sess in interview_sessions:
            sess_id = sess.get("session_id", "")
            answers = sess.get("answers", [])
            for ans in answers:
                if ans.get("skipped"):
                    continue

                q_id = ans.get("question_id", "")
                section = ans.get("section", "")
                ans_text = str(ans.get("patient_answer", "")).strip()
                if not ans_text:
                    continue

                ans_time = ans.get("answered_at") or sess.get("started_at")
                iso_ans, disp_ans = self._parse_date_string(ans_time)

                if q_id == "chief_complaint" or section == "chief_complaint":
                    all_events.append(TimelineEvent(
                        event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                        event_date=iso_ans,
                        display_date=disp_ans,
                        event_type=TimelineEventType.SYMPTOM_REPORTED,
                        title=f"Chief Complaint: {ans_text}",
                        details={"answer": ans_text, "question": ans.get("question_text")},
                        source="patient_interview",
                        source_label="Clinical Intake Interview",
                        source_document_id=None,
                        source_session_id=sess_id,
                        verification_status="needs_review",
                    ))

                elif section in ("past_medical", "pmh") or q_id == "pmh_conditions":
                    if "no" not in ans_text.lower() and "none" not in ans_text.lower():
                        all_events.append(TimelineEvent(
                            event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                            event_date=None,
                            display_date="Date not specified",
                            event_type=TimelineEventType.DIAGNOSIS_DOCUMENTED,
                            title=f"Past Medical History: {ans_text}",
                            details={"condition": ans_text, "source_interview": True},
                            source="patient_interview",
                            source_label="Clinical Intake Interview",
                            source_document_id=None,
                            source_session_id=sess_id,
                            verification_status="needs_review",
                        ))

                elif section in ("past_surgical",) or q_id == "pmh_surgeries":
                    if "no" not in ans_text.lower() and "none" not in ans_text.lower():
                        all_events.append(TimelineEvent(
                            event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                            event_date=None,
                            display_date="Date not specified",
                            event_type=TimelineEventType.PROCEDURE_PERFORMED,
                            title=f"Past Surgical History: {ans_text}",
                            details={"procedure": ans_text, "source_interview": True},
                            source="patient_interview",
                            source_label="Clinical Intake Interview",
                            source_document_id=None,
                            source_session_id=sess_id,
                            verification_status="needs_review",
                        ))

                elif section in ("medications",) or q_id == "medications_current":
                    interview_medications.append(ans_text)
                    if "no" not in ans_text.lower() and "none" not in ans_text.lower():
                        all_events.append(TimelineEvent(
                            event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                            event_date=None,
                            display_date="Date not specified",
                            event_type=TimelineEventType.MEDICATION_PRESCRIBED,
                            title=f"Reported Medication: {ans_text}",
                            details={"medication": ans_text, "source_interview": True},
                            source="patient_interview",
                            source_label="Clinical Intake Interview",
                            source_document_id=None,
                            source_session_id=sess_id,
                            verification_status="needs_review",
                        ))

                elif section in ("allergies",) or q_id == "allergies_known":
                    interview_allergies.append(ans_text)
                    all_events.append(TimelineEvent(
                        event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                        event_date=None,
                        display_date="Date not specified",
                        event_type=TimelineEventType.ALLERGY_DOCUMENTED,
                        title=f"Reported Allergy Status: {ans_text}",
                        details={"allergy": ans_text, "source_interview": True},
                        source="patient_interview",
                        source_label="Clinical Intake Interview",
                        source_document_id=None,
                        source_session_id=sess_id,
                        verification_status="needs_review",
                    ))

        # 4. Extract events from Medical Documents
        docs_cursor = docs_col.find({"patient_id": canonical_pid})
        documents = await docs_cursor.to_list(length=100)

        document_allergies = []
        document_medications = []

        for d in documents:
            doc_id = d.get("document_id", "")
            ext_data = d.get("extracted_data") or {}
            doc_type = d.get("document_type", "document")
            doc_filename = d.get("original_filename", "Uploaded File")
            doc_status = d.get("verification_status", "needs_review")

            # Document Date - zero date guessing policy
            doc_date_raw = ext_data.get("patient_info", {}).get("document_date") if ext_data.get("patient_info") else None
            iso_doc, disp_doc = self._parse_date_string(doc_date_raw)

            # Diagnoses
            for diag in ext_data.get("diagnoses", []):
                all_events.append(TimelineEvent(
                    event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                    event_date=iso_doc,
                    display_date=disp_doc,
                    event_type=TimelineEventType.DIAGNOSIS_DOCUMENTED,
                    title=f"Documented Diagnosis: {diag.get('diagnosis')}",
                    details={"diagnosis": diag.get("diagnosis"), "filename": doc_filename},
                    source="medical_document",
                    source_label=f"Medical Document [{doc_id}] ({doc_filename})",
                    source_document_id=doc_id,
                    source_session_id=None,
                    verification_status=doc_status,
                ))

            # Medications
            for med in ext_data.get("medications", []):
                med_name = med.get("name", "")
                document_medications.append(med_name)
                m_title = f"Prescribed: {med_name}"
                if med.get("dosage"):
                    m_title += f" {med.get('dosage')}"
                if med.get("frequency"):
                    m_title += f" ({med.get('frequency')})"
                if med.get("duration"):
                    m_title += f" for {med.get('duration')}"

                all_events.append(TimelineEvent(
                    event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                    event_date=iso_doc,
                    display_date=disp_doc,
                    event_type=TimelineEventType.MEDICATION_PRESCRIBED,
                    title=m_title,
                    details=med,
                    source="medical_document",
                    source_label=f"Prescription / Document [{doc_id}] ({doc_filename})",
                    source_document_id=doc_id,
                    source_session_id=None,
                    verification_status=doc_status,
                ))

            # Investigations
            for inv in ext_data.get("investigations", []):
                i_title = f"Lab Result: {inv.get('test_name')} {inv.get('result_value') or ''} {inv.get('unit') or ''}".strip()
                if inv.get("is_abnormal"):
                    i_title += " [ABNORMAL]"

                all_events.append(TimelineEvent(
                    event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                    event_date=iso_doc,
                    display_date=disp_doc,
                    event_type=TimelineEventType.INVESTIGATION_RESULT,
                    title=i_title,
                    details=inv,
                    source="medical_document",
                    source_label=f"Lab Report [{doc_id}] ({doc_filename})",
                    source_document_id=doc_id,
                    source_session_id=None,
                    verification_status=doc_status,
                ))

            # Procedures
            for proc in ext_data.get("procedures", []):
                all_events.append(TimelineEvent(
                    event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                    event_date=iso_doc,
                    display_date=disp_doc,
                    event_type=TimelineEventType.PROCEDURE_PERFORMED,
                    title=f"Procedure: {proc.get('procedure_name')}",
                    details=proc,
                    source="medical_document",
                    source_label=f"Discharge / Procedure Report [{doc_id}] ({doc_filename})",
                    source_document_id=doc_id,
                    source_session_id=None,
                    verification_status=doc_status,
                ))

            # Allergies
            for allg in ext_data.get("allergies", []):
                allg_name = allg.get("allergen", "")
                document_allergies.append(allg_name)
                all_events.append(TimelineEvent(
                    event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                    event_date=iso_doc,
                    display_date=disp_doc,
                    event_type=TimelineEventType.ALLERGY_DOCUMENTED,
                    title=f"Documented Allergy: {allg_name}",
                    details=allg,
                    source="medical_document",
                    source_label=f"Medical Record [{doc_id}] ({doc_filename})",
                    source_document_id=doc_id,
                    source_session_id=None,
                    verification_status=doc_status,
                ))

        # 5. Extract events from Triage Alerts
        triage_cursor = triage_col.find({"patient_id": canonical_pid})
        triage_alerts = await triage_cursor.to_list(length=20)

        for alert in triage_alerts:
            iso_triage, disp_triage = self._parse_date_string(alert.get("detected_at"))
            all_events.append(TimelineEvent(
                event_id=f"TLE-{uuid.uuid4().hex[:8].upper()}",
                event_date=iso_triage,
                display_date=disp_triage,
                event_type=TimelineEventType.TRIAGE_ALERT,
                title=f"Red-Flag Triage Alert: {alert.get('detected_category', 'Warning').replace('_', ' ').title()} ({alert.get('priority', 'HIGH')})",
                details={
                    "alert_id": alert.get("alert_id"),
                    "category": alert.get("detected_category"),
                    "priority": alert.get("priority"),
                    "matched_keywords": alert.get("matched_keywords", []),
                    "status": alert.get("status"),
                },
                source="triage",
                source_label="Automated Red-Flag Detector",
                source_document_id=None,
                source_session_id=alert.get("session_id"),
                verification_status="verified",
            ))

        # 6. Deduplication of identical clinical events
        deduped_events: List[TimelineEvent] = []
        seen_event_signatures = set()

        for ev in all_events:
            sig = (
                ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type),
                ev.event_date or "UNDATED",
                re.sub(r"\s+", " ", ev.title.lower().strip()),
            )
            if sig in seen_event_signatures:
                continue
            seen_event_signatures.add(sig)
            deduped_events.append(ev)

        all_events = deduped_events

        # 7. Conflict Detection (Interview vs Documents)
        # Check allergy contradictions: e.g. interview says "no allergies" or "none", but document lists an active allergy
        has_conflicts = False
        conflict_count = 0

        interview_allergy_str = " ".join(interview_allergies).lower()
        has_interview_negative_allergy = any(kw in interview_allergy_str for kw in ["no", "none", "nil", "nkda", "denies"])

        for ev in all_events:
            if ev.event_type == TimelineEventType.ALLERGY_DOCUMENTED and ev.source == "medical_document":
                allergen_name = ev.details.get("allergen", "").lower()
                if "nkda" not in allergen_name and "none" not in allergen_name and has_interview_negative_allergy:
                    ev.is_conflict = True
                    ev.conflict_notes = (
                        f"Conflicting information — physician verification required: "
                        f"Patient reported no known allergies during interview, but medical document lists allergy to '{ev.details.get('allergen')}'."
                    )
                    has_conflicts = True
                    conflict_count += 1

        # 7. Chronological Segregation
        dated_events: List[TimelineEvent] = []
        undated_events: List[TimelineEvent] = []

        for ev in all_events:
            if ev.event_date:
                dated_events.append(ev)
            else:
                undated_events.append(ev)

        # Sort dated events chronologically descending (newest first)
        dated_events.sort(key=lambda x: x.event_date or "", reverse=True)

        response = MedicalTimelineResponse(
            patient_id=canonical_pid,
            token_number=token_num,
            patient_name=patient_name,
            total_events=len(all_events),
            dated_events=dated_events,
            undated_events=undated_events,
            has_conflicts=has_conflicts,
            conflict_count=conflict_count,
            generated_at=datetime.now(timezone.utc),
        )

        # 8. Persist timeline inside patient record in MongoDB
        try:
            timeline_dict = response.model_dump()
            await patients_col.update_one(
                {"_id": patient_doc["_id"]},
                {"$set": {"medical_timeline": timeline_dict}}
            )
        except Exception as e:
            logger.warning(f"Could not persist medical_timeline to MongoDB: {e}")

        return response


# Singleton instance
medical_timeline_service = MedicalTimelineService()
