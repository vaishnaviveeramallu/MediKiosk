from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Query
from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel
import uuid

from app.database import get_database
from app.models.interview import (
    AdaptiveQuestionItem,
    AnswerSubmission,
    AnswerRecord,
    InterviewSessionResponse,
    INITIAL_CHIEF_COMPLAINT_QUESTION,
)
from app.services.ai_service import ai_service

router = APIRouter(prefix="/api/interview", tags=["clinical-interview"])


def serialize_session(doc: dict) -> InterviewSessionResponse:
    """Helper to convert MongoDB session document to InterviewSessionResponse."""
    answers = [AnswerRecord(**a) for a in doc.get("answers", [])]
    
    current_q_data = doc.get("current_question")
    current_q = AdaptiveQuestionItem(**current_q_data) if current_q_data else None

    stage_num = current_q.stage_number if current_q else 1
    stage_en = current_q.stage_title_en if current_q else "Chief Complaint"
    stage_hi = current_q.stage_title_hi if current_q else "मुख्य समस्या"
    is_comp = doc.get("status") == "completed" or (current_q.is_terminal if current_q else False)

    # Compile questions list for compatibility
    questions_list = []
    for a in answers:
        questions_list.append(
            AdaptiveQuestionItem(
                question_id=a.question_id,
                section=a.section,
                stage_number=a.stage_number or 1,
                stage_title_en=stage_en,
                stage_title_hi=stage_hi,
                section_title_en=a.section.replace("_", " ").title(),
                section_title_hi=a.section,
                text_en=a.question_text,
                text_hi=a.question_text,
                input_type="text",
                is_terminal=False,
            )
        )
    if current_q and not any(q.question_id == current_q.question_id for q in questions_list):
        questions_list.append(current_q)

    triage_alert_data = doc.get("triage_alert")
    has_triage = bool(triage_alert_data) or doc.get("status") == "triage_alert"

    return InterviewSessionResponse(
        session_id=doc["session_id"],
        patient_id=str(doc["patient_id"]),
        token_number=doc["token_number"],
        full_name=doc["full_name"],
        selected_language=doc.get("selected_language", "en"),
        status=doc["status"],
        started_at=doc["started_at"],
        completed_at=doc.get("completed_at"),
        answers=answers,
        current_question=current_q,
        answered_count=len(answers),
        total_questions=max(len(answers) + (0 if is_comp else 1), 6),
        current_question_index=len(answers),
        current_stage_number=stage_num,
        current_stage_title_en=stage_en,
        current_stage_title_hi=stage_hi,
        is_complete=is_comp,
        has_triage_alert=has_triage,
        triage_alert=triage_alert_data,
        questions=questions_list,
    )


@router.post(
    "/start",
    response_model=InterviewSessionResponse,
    summary="Start or resume a clinical interview session",
    description="Validates patient consent, initializes or resumes an adaptive interview session in MongoDB.",
)
async def start_interview(patient_id: str = Query(..., description="MongoDB ID or OPD token")):
    db = get_database()
    patients_col = db["patients"]
    sessions_col = db["interview_sessions"]

    # 1. Lookup patient
    query_filter = None
    try:
        query_filter = {"_id": ObjectId(patient_id)}
    except InvalidId:
        query_filter = {"token_number": patient_id.upper()}

    patient = await patients_col.find_one(query_filter)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with identifier '{patient_id}' not found",
        )

    # 2. Strict Consent Guard
    consent_given = patient.get("consent_given")
    consent_status = patient.get("consent_status")

    if not consent_given or consent_status != "granted":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cannot start clinical interview. Patient consent status is '{consent_status or 'pending'}'. "
                "Explicit consent must be granted before clinical intake can begin."
            ),
        )

    # 3. Check for existing in-progress session (Resume Safety)
    existing_session = await sessions_col.find_one({
        "patient_id": str(patient["_id"]),
        "status": "in_progress",
    })

    if existing_session:
        # If existing session didn't have current_question saved, regenerate appropriately
        if not existing_session.get("current_question"):
            lang = existing_session.get("selected_language", "en")
            answers = existing_session.get("answers", [])
            patient_info = {
                "age": patient.get("age"),
                "gender": patient.get("gender"),
                "token_number": patient.get("token_number"),
            }
            if not answers:
                initial_q = ai_service.get_initial_question(lang)
            else:
                initial_q = await ai_service.generate_next_question(patient_info, answers, lang)
            
            await sessions_col.update_one(
                {"_id": existing_session["_id"]},
                {"$set": {"current_question": initial_q.model_dump()}},
            )
            existing_session["current_question"] = initial_q.model_dump()
        return serialize_session(existing_session)

    # 4. Create new adaptive interview session
    now = datetime.now(timezone.utc)
    session_id = f"int_{uuid.uuid4().hex[:12]}"
    lang = patient.get("selected_language", "en")
    initial_question = ai_service.get_initial_question(lang)

    session_doc = {
        "session_id": session_id,
        "patient_id": str(patient["_id"]),
        "token_number": patient["token_number"],
        "full_name": patient["full_name"],
        "selected_language": lang,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "answers": [],
        "current_question": initial_question.model_dump(),
        "created_at": now,
    }

    await sessions_col.insert_one(session_doc)

    # Update patient record status
    await patients_col.update_one(
        {"_id": patient["_id"]},
        {
            "$set": {
                "registration_status": "interview_in_progress",
                "interview_session_id": session_id,
            }
        },
    )

    return serialize_session(session_doc)


@router.post(
    "/{session_id}/answer",
    response_model=InterviewSessionResponse,
    summary="Submit patient answer and dynamically generate next question",
    description="Persists answer in MongoDB, updates clinical history, and generates next adaptive question.",
)
async def submit_answer(session_id: str, payload: AnswerSubmission):
    db = get_database()
    sessions_col = db["interview_sessions"]
    patients_col = db["patients"]

    session = await sessions_col.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found",
        )

    if session["status"] == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit answers to an already completed interview session",
        )

    now = datetime.now(timezone.utc)
    existing_answers = session.get("answers", [])
    question_order = len(existing_answers) + 1

    answer_lang = payload.language or session.get("selected_language", "en")
    answer_input_method = (payload.input_method or "text").lower()

    answer_dict = {
        "question_id": payload.question_id,
        "question_text": payload.question_text,
        "section": payload.section,
        "stage_number": payload.stage_number or 1,
        "patient_answer": payload.patient_answer.strip(),
        "skipped": payload.skipped,
        "answered_at": now,
        "question_order": question_order,
        "input_method": answer_input_method,
        "language": answer_lang,
    }

    # Upsert answer into the answers list for this session
    updated_answers = [a for a in existing_answers if a["question_id"] != payload.question_id]
    updated_answers.append(answer_dict)

    # Mirror answer into the patient's clinical_history field
    patient_doc = None
    try:
        patient_oid = ObjectId(session["patient_id"])
        patient_doc = await patients_col.find_one({"_id": patient_oid})
        if patient_doc:
            hist = patient_doc.get("clinical_history")
            if not isinstance(hist, dict):
                hist = {}
            hist[payload.question_id] = {
                "question": payload.question_text,
                "answer": payload.patient_answer.strip(),
                "section": payload.section,
                "stage_number": payload.stage_number or 1,
                "timestamp": now,
                "question_order": question_order,
                "input_method": answer_input_method,
                "language": answer_lang,
            }
            await patients_col.update_one(
                {"_id": patient_oid},
                {"$set": {"clinical_history": hist}},
            )
    except Exception as e:
        print(f"Error mirroring to patient clinical_history: {e}")

    # Fetch patient demographic context
    patient_info = {
        "age": patient_doc.get("age") if patient_doc else 30,
        "gender": patient_doc.get("gender") if patient_doc else "Other",
        "token_number": session.get("token_number"),
    }
    lang = session.get("selected_language", "en")

    # Generate next adaptive question using AI Service / Heuristic Engine
    next_question = await ai_service.generate_next_question(patient_info, updated_answers, lang)

    # Run clinical red-flag & triage detection
    from app.services.triage_detector import triage_detector
    triage_result = triage_detector.detect(payload.patient_answer, answer_lang)

    if triage_result.has_red_flag:
        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        patient_name = session.get("full_name", "")
        token_num = session.get("token_number", "")

        triage_alert_doc = {
            "alert_id": alert_id,
            "patient_id": str(session["patient_id"]),
            "token_number": token_num,
            "patient_name": patient_name,
            "session_id": session_id,
            "question_id": payload.question_id,
            "question_text": payload.question_text,
            "triggering_answer": payload.patient_answer.strip(),
            "detected_category": triage_result.category,
            "priority": triage_result.priority.value if triage_result.priority else "URGENT",
            "rule_description": triage_result.rule_description or "Clinical red-flag symptom detected",
            "matched_keywords": triage_result.matched_keywords,
            "detected_at": now,
            "status": "active",
            "acknowledged_at": None,
            "acknowledged_by": None,
            "handled_at": None,
            "handled_by": None,
            "staff_notes": None,
            "patient_instruction_en": triage_result.patient_instruction_en,
            "patient_instruction_hi": triage_result.patient_instruction_hi,
        }

        # Store alert into real MongoDB triage_alerts collection
        await db["triage_alerts"].insert_one(dict(triage_alert_doc))
        triage_alert_clean = {k: v for k, v in triage_alert_doc.items() if k != "_id"}

        # Update session status to triage_alert, saving next_question as current_question
        await sessions_col.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "answers": updated_answers,
                    "current_question": next_question.model_dump(),
                    "triage_alert": triage_alert_clean,
                    "selected_language": answer_lang,
                    "status": "triage_alert",
                    "last_updated_at": now,
                }
            },
        )

        if patient_doc:
            await patients_col.update_one(
                {"_id": patient_doc["_id"]},
                {"$set": {"registration_status": "triage_alert"}},
            )

        updated_doc = await sessions_col.find_one({"session_id": session_id})
        return serialize_session(updated_doc)

    # Determine status update
    session_status = "completed" if next_question.is_terminal else "in_progress"
    completed_at = now if next_question.is_terminal else None

    # Persist updated session state
    await sessions_col.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "answers": updated_answers,
                "current_question": next_question.model_dump(),
                "selected_language": answer_lang,
                "status": session_status,
                "completed_at": completed_at,
                "last_updated_at": now,
            }
        },
    )

    if next_question.is_terminal and patient_doc:
        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {"$set": {"registration_status": "interview_completed"}},
        )

    updated_doc = await sessions_col.find_one({"session_id": session_id})
    return serialize_session(updated_doc)


@router.get(
    "/{session_id}",
    response_model=InterviewSessionResponse,
    summary="Retrieve active adaptive interview session (Resume safety)",
    description="Fetches full session state, current question, and all persisted answers from MongoDB.",
)
async def get_interview_session(session_id: str):
    db = get_database()
    sessions_col = db["interview_sessions"]

    session = await sessions_col.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found",
        )

    return serialize_session(session)


class UpdateSessionLanguageRequest(BaseModel):
    language: str


@router.patch(
    "/{session_id}/language",
    response_model=InterviewSessionResponse,
    summary="Update interview session language",
    description="Updates the active language for the session in MongoDB.",
)
async def update_session_language(session_id: str, payload: UpdateSessionLanguageRequest):
    lang_code = payload.language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{payload.language}'. Supported: 'en', 'hi'.",
        )

    db = get_database()
    sessions_col = db["interview_sessions"]

    res = await sessions_col.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "selected_language": lang_code,
                "last_updated_at": datetime.now(timezone.utc),
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found",
        )

    updated_doc = await sessions_col.find_one({"session_id": session_id})
    return serialize_session(updated_doc)


@router.post(
    "/{session_id}/complete",
    response_model=InterviewSessionResponse,
    summary="Mark clinical interview as completed",
    description="Finalizes the interview session, records completion timestamp, and updates patient status.",
)
async def complete_interview(session_id: str):
    db = get_database()
    sessions_col = db["interview_sessions"]
    patients_col = db["patients"]

    session = await sessions_col.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found",
        )

    now = datetime.now(timezone.utc)
    await sessions_col.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": now,
                "last_updated_at": now,
            }
        },
    )

    # Update patient status
    try:
        patient_oid = ObjectId(session["patient_id"])
        await patients_col.update_one(
            {"_id": patient_oid},
            {"$set": {"registration_status": "interview_completed"}},
        )
    except Exception:
        pass

    updated_doc = await sessions_col.find_one({"session_id": session_id})
    return serialize_session(updated_doc)
