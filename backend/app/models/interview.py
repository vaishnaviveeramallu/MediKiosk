from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AdaptiveQuestionItem(BaseModel):
    question_id: str = Field(..., description="Unique slug for the question (e.g. chief_complaint, hpi_radiation)")
    section: str = Field(..., description="Clinical history section (e.g. chief_complaint, hpi, past_medical, medications, allergies, family_history, social_history, review_of_systems)")
    stage_number: int = Field(1, description="Clinical intake stage (1-6)")
    stage_title_en: str = Field("Chief Complaint", description="English stage title")
    stage_title_hi: str = Field("मुख्य समस्या", description="Hindi stage title")
    section_title_en: str = Field(..., description="English section title")
    section_title_hi: str = Field(..., description="Hindi section title")
    text_en: str = Field(..., description="English question prompt")
    text_hi: str = Field(..., description="Hindi question prompt")
    hint_en: Optional[str] = Field(None, description="English guidance hint")
    hint_hi: Optional[str] = Field(None, description="Hindi guidance hint")
    options_en: Optional[List[str]] = Field(None, description="Quick-touch options in English")
    options_hi: Optional[List[str]] = Field(None, description="Quick-touch options in Hindi")
    input_type: str = Field("text", description="Input widget: 'text', 'scale', 'chips'")
    is_terminal: bool = Field(False, description="True if interview is concluded")


# Compatibility alias
QuestionItem = AdaptiveQuestionItem


class AnswerSubmission(BaseModel):
    question_id: str = Field(..., description="Unique ID of the question")
    question_text: str = Field(..., description="Question prompt displayed to the patient")
    section: str = Field(..., description="Clinical history section")
    stage_number: Optional[int] = Field(1, description="Clinical intake stage (1-6)")
    patient_answer: str = Field(..., min_length=1, max_length=1000, description="Patient's response")
    skipped: bool = Field(False, description="Whether question was skipped or answered 'Prefer not to answer'")
    question_order: Optional[int] = Field(None, description="Sequential order in conversation")
    input_method: Optional[str] = Field("text", description="Input method used: 'voice' or 'text'")
    language: Optional[str] = Field(None, description="Language used: 'en' or 'hi'")


class AnswerRecord(BaseModel):
    question_id: str
    question_text: str
    section: str
    stage_number: Optional[int] = 1
    patient_answer: str
    skipped: bool
    answered_at: datetime
    question_order: int = 1
    input_method: str = "text"
    language: Optional[str] = None


class InterviewSessionResponse(BaseModel):
    session_id: str
    patient_id: str
    token_number: str
    full_name: str
    selected_language: str
    status: str  # "in_progress" or "completed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    answers: List[AnswerRecord] = []
    current_question: Optional[AdaptiveQuestionItem] = None
    answered_count: int = 0
    total_questions: int = 0
    current_question_index: int = 0
    current_stage_number: int = 1
    current_stage_title_en: str = "Chief Complaint"
    current_stage_title_hi: str = "मुख्य समस्या"
    is_complete: bool = False
    has_triage_alert: bool = False
    triage_alert: Optional[Dict[str, Any]] = None
    questions: List[AdaptiveQuestionItem] = []


# Standard Initial Question: Chief Complaint
INITIAL_CHIEF_COMPLAINT_QUESTION = AdaptiveQuestionItem(
    question_id="chief_complaint",
    section="chief_complaint",
    stage_number=1,
    stage_title_en="Stage 1: Chief Complaint",
    stage_title_hi="चरण 1: मुख्य समस्या",
    section_title_en="Primary Complaint",
    section_title_hi="मुख्य समस्या",
    text_en="What is your primary health problem or reason for visiting the OPD today?",
    text_hi="आज अस्पताल आने का आपका मुख्य कारण या प्राथमिक स्वास्थ्य समस्या क्या है?",
    hint_en="Please state your main symptom in your own words (e.g. chest discomfort, high fever, knee pain).",
    hint_hi="कृपया अपनी मुख्य परेशानी अपने शब्दों में बताएं (जैसे सीने में बेचैनी, तेज बुखार, घुटने में दर्द)।",
    options_en=[
        "Chest pain",
        "Fever with chills",
        "Severe headache",
        "Stomach pain",
        "Difficulty breathing",
        "Joint / Knee pain",
    ],
    options_hi=[
        "सीने में दर्द",
        "ठंड लगकर बुखार",
        "तेज सिरदर्द",
        "पेट में दर्द",
        "सांस लेने में तकलीफ",
        "जोड़ों / घुटने में दर्द",
    ],
    input_type="text",
    is_terminal=False,
)
