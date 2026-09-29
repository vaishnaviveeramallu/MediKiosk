import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
import uuid

from app.config import Settings
from app.database import (
    get_patients_collection,
    get_interview_sessions_collection,
    get_documents_collection,
)
from app.models.integration import IntegrationStatusEnum, IntegrationComponentStatus
from app.services.audit_service import audit_service

logger = logging.getLogger("medikiosk.fhir_service")
settings = Settings()


class FHIRService:
    """
    HL7 FHIR Release 4 (R4) conversion and interoperability engine.
    Converts real MongoDB patient records, clinical interview transcripts,
    AYUSH history, and verified summaries into standard FHIR R4 resources.
    
    Zero Mock Data: Operates strictly against authentic patient records.
    Truthful Status: If remote FHIR server is unconfigured, reports LOCAL_ONLY.
    """

    def is_server_configured(self) -> bool:
        return bool(settings.FHIR_SERVER_URL)

    def get_status(self) -> IntegrationComponentStatus:
        if not self.is_server_configured():
            return IntegrationComponentStatus(
                name="fhir_r4",
                status=IntegrationStatusEnum.LOCAL_ONLY,
                configured=False,
                message="Remote FHIR server endpoint is not configured. Standard HL7 FHIR R4 Bundle export is fully functional locally.",
                endpoint_url=settings.FHIR_SERVER_URL,
                details={
                    "fhir_version": "R4",
                    "export_available": True,
                    "remote_sync_active": False,
                    "supported_resources": [
                        "Patient", "Encounter", "Observation", "Composition", "DocumentReference", "Bundle"
                    ],
                },
            )

        return IntegrationComponentStatus(
            name="fhir_r4",
            status=IntegrationStatusEnum.CONFIGURED,
            configured=True,
            message="Remote FHIR server configured.",
            endpoint_url=settings.FHIR_SERVER_URL,
            details={
                "fhir_version": settings.FHIR_VERSION or "R4",
                "export_available": True,
                "remote_sync_active": True,
            },
        )

    def patient_to_fhir(self, patient_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a MongoDB patient document into an HL7 FHIR R4 Patient resource.
        """
        pid = str(patient_doc.get("_id", ""))
        gender_raw = str(patient_doc.get("gender", "unknown")).lower()
        fhir_gender = "other"
        if "female" in gender_raw:
            fhir_gender = "female"
        elif "male" in gender_raw:
            fhir_gender = "male"

        identifiers = []
        if patient_doc.get("token_number"):
            identifiers.append({
                "use": "usual",
                "system": "http://medikiosk.hospital.local/identifiers/opd-token",
                "value": patient_doc.get("token_number"),
            })
        if patient_doc.get("government_id_number"):
            identifiers.append({
                "use": "official",
                "system": f"http://medikiosk.hospital.local/identifiers/{patient_doc.get('government_id_type', 'govt_id')}",
                "value": patient_doc.get("government_id_number"),
            })
        if patient_doc.get("abha_number"):
            identifiers.append({
                "use": "official",
                "system": "https://healthid.abdm.gov.in",
                "value": patient_doc.get("abha_number"),
            })

        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": pid,
            "identifier": identifiers,
            "active": True,
            "name": [{
                "use": "official",
                "text": patient_doc.get("full_name", "Unknown"),
            }],
            "gender": fhir_gender,
        }

        if patient_doc.get("phone_number"):
            resource["telecom"] = [{
                "system": "phone",
                "value": patient_doc.get("phone_number"),
                "use": "mobile",
            }]

        if patient_doc.get("address_city") or patient_doc.get("address_state"):
            resource["address"] = [{
                "use": "home",
                "city": patient_doc.get("address_city"),
                "state": patient_doc.get("address_state"),
                "country": "India",
            }]

        return resource

    def session_to_fhir_encounter(self, patient_id: str, session_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Converts an interview session into an HL7 FHIR R4 Encounter resource.
        """
        if not session_doc:
            return None

        sid = session_doc.get("session_id", str(session_doc.get("_id", uuid.uuid4().hex[:8])))
        is_complete = session_doc.get("status") == "completed"

        return {
            "resourceType": "Encounter",
            "id": sid,
            "status": "finished" if is_complete else "in-progress",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "ambulatory",
            },
            "subject": {
                "reference": f"Patient/{patient_id}",
            },
            "period": {
                "start": session_doc.get("started_at", datetime.now(timezone.utc)).isoformat()
                if isinstance(session_doc.get("started_at"), datetime)
                else str(session_doc.get("started_at", "")),
            },
        }

    def answers_to_fhir_observations(
        self, patient_id: str, encounter_id: Optional[str], session_doc: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Converts answered clinical questions and AYUSH items into FHIR Observations.
        """
        if not session_doc:
            return []

        observations: List[Dict[str, Any]] = []
        answers = session_doc.get("answers", [])

        for idx, ans in enumerate(answers):
            q_text = ans.get("question_text") or ans.get("question_id", f"question_{idx}")
            ans_text = str(ans.get("answer_text", ""))
            obs_id = f"obs-{session_doc.get('session_id', 'ses')}-{idx+1}"

            obs: Dict[str, Any] = {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    }]
                }],
                "code": {
                    "text": q_text,
                },
                "subject": {
                    "reference": f"Patient/{patient_id}",
                },
                "valueString": ans_text,
            }
            if encounter_id:
                obs["encounter"] = {"reference": f"Encounter/{encounter_id}"}

            observations.append(obs)

        return observations

    def summary_to_fhir_composition(
        self, patient_id: str, summary_doc: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Converts AI clinical summary / physician review into a FHIR Composition.
        """
        if not summary_doc:
            return None

        cid = f"comp-{patient_id}"
        sections = []

        # Convert summary sections into FHIR sections
        for key in [
            "chief_complaint", "history_of_present_illness", "past_medical_history",
            "current_medications", "allergies", "review_of_systems", "ayush_findings",
            "triage_assessment", "red_flags", "physician_notes"
        ]:
            val = summary_doc.get(key)
            if val:
                sections.append({
                    "title": key.replace("_", " ").title(),
                    "text": {
                        "status": "generated",
                        "div": f"<div>{str(val)}</div>",
                    },
                })

        return {
            "resourceType": "Composition",
            "id": cid,
            "status": "final" if summary_doc.get("status") == "confirmed" else "preliminary",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "11503-0",
                    "display": "Medical Records",
                }]
            },
            "subject": {
                "reference": f"Patient/{patient_id}",
            },
            "date": datetime.now(timezone.utc).isoformat(),
            "author": [{
                "display": "MediKiosk Clinical Intake System",
            }],
            "title": "Outpatient Clinical Intake Summary",
            "section": sections,
        }

    async def build_patient_fhir_bundle(self, patient_id: str) -> Dict[str, Any]:
        """
        Builds a comprehensive FHIR R4 Bundle containing the Patient, Encounter,
        Observations, and Clinical Summary for authorized clinical exchange.
        """
        patients_col = get_patients_collection()
        try:
            q = {"_id": ObjectId(patient_id)}
        except InvalidId:
            q = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(q)
        if not patient_doc:
            raise ValueError(f"Patient '{patient_id}' not found.")

        resolved_pid = str(patient_doc["_id"])

        # Fetch session
        sessions_col = get_interview_sessions_collection()
        session_doc = await sessions_col.find_one(
            {"patient_id": resolved_pid},
            sort=[("started_at", -1)],
        )

        # Fetch documents
        docs_col = get_documents_collection()
        doc_cursor = docs_col.find({"patient_id": resolved_pid})
        doc_list = await doc_cursor.to_list(length=20)

        # Build resources
        resources: List[Dict[str, Any]] = []

        patient_res = self.patient_to_fhir(patient_doc)
        resources.append(patient_res)

        encounter_res = self.session_to_fhir_encounter(resolved_pid, session_doc)
        encounter_id = None
        if encounter_res:
            resources.append(encounter_res)
            encounter_id = encounter_res.get("id")

        obs_list = self.answers_to_fhir_observations(resolved_pid, encounter_id, session_doc)
        resources.extend(obs_list)

        for d in doc_list:
            d_id = str(d.get("_id", uuid.uuid4().hex[:8]))
            doc_ref = {
                "resourceType": "DocumentReference",
                "id": d_id,
                "status": "current",
                "subject": {"reference": f"Patient/{resolved_pid}"},
                "description": d.get("filename", "Uploaded medical document"),
                "content": [{
                    "attachment": {
                        "contentType": d.get("mime_type", "application/pdf"),
                        "title": d.get("filename"),
                    }
                }],
            }
            resources.append(doc_ref)

        summary_data = patient_doc.get("clinical_summary")
        if summary_data and isinstance(summary_data, dict):
            comp_res = self.summary_to_fhir_composition(resolved_pid, summary_data)
            if comp_res:
                resources.append(comp_res)

        bundle_id = f"bundle-{resolved_pid}-{uuid.uuid4().hex[:8]}"
        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "collection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(resources),
            "entry": [
                {
                    "fullUrl": f"urn:uuid:{r.get('id', uuid.uuid4().hex[:8])}",
                    "resource": r,
                }
                for r in resources
            ],
        }

        return bundle


fhir_service = FHIRService()
