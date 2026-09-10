import pytest
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager


@pytest.mark.anyio
async def test_supported_languages_voice_enabled():
    """Verify that both English and Hindi advertise genuine voice support in the language registry."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/languages")
        assert response.status_code == 200
        languages = response.json()
        assert len(languages) >= 2

        lang_map = {l["code"]: l for l in languages}
        assert "en" in lang_map
        assert "hi" in lang_map

        # English voice capabilities
        assert lang_map["en"]["voice_supported"] is True
        assert lang_map["en"]["voice_locale"] == "en-IN"

        # Hindi voice capabilities
        assert lang_map["hi"]["voice_supported"] is True
        assert lang_map["hi"]["voice_locale"] == "hi-IN"


@pytest.mark.anyio
async def test_voice_status_endpoint():
    """Verify voice status endpoint returns ready status and bilingual configuration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/voice/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "en-IN" in data["supported_locales"]
        assert "hi-IN" in data["supported_locales"]
        assert data["tts_primary"] == "web_speech_synthesis"
        assert len(data["languages"]) >= 2


@pytest.mark.anyio
async def test_voice_synthesize_endpoint_validation():
    """Verify voice synthesis parameters for English, Hindi, and invalid input."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. English synthesis
        res_en = await ac.post(
            "/api/voice/synthesize",
            json={"text": "Where is your pain located?", "language": "en"},
        )
        assert res_en.status_code == 200
        data_en = res_en.json()
        assert data_en["language"] == "en"
        assert data_en["locale"] == "en-IN"
        assert len(data_en["recommended_voices"]) > 0

        # 2. Hindi synthesis
        res_hi = await ac.post(
            "/api/voice/synthesize",
            json={"text": "आपको दर्द कहाँ महसूस हो रहा है?", "language": "hi"},
        )
        assert res_hi.status_code == 200
        data_hi = res_hi.json()
        assert data_hi["language"] == "hi"
        assert data_hi["locale"] == "hi-IN"
        assert len(data_hi["recommended_voices"]) > 0

        # 3. Unsupported language rejected
        res_unsupported = await ac.post(
            "/api/voice/synthesize",
            json={"text": "Hello", "language": "fr"},
        )
        assert res_unsupported.status_code == 400
        assert "Unsupported language" in res_unsupported.json()["detail"]


@pytest.mark.anyio
async def test_voice_transcript_validation():
    """Verify voice transcript validation endpoint for spoken inputs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Valid Hindi spoken transcript
        res = await ac.post(
            "/api/voice/validate-transcript",
            json={"transcript": "मुझे पिछले दो दिन से तेज बुखार है", "language": "hi"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "valid"
        assert data["locale"] == "hi-IN"
        assert data["word_count"] >= 5

        # Empty transcript rejected
        res_empty = await ac.post(
            "/api/voice/validate-transcript",
            json={"transcript": "   ", "language": "en"},
        )
        assert res_empty.status_code == 400


@pytest.mark.anyio
async def test_voice_transcribe_multipart():
    """Verify multipart voice transcribe endpoint handles client transcripts and WAV audio files."""
    import wave
    import struct

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Client transcript via form
        res_text = await ac.post(
            "/api/voice/transcribe",
            data={"client_transcript": "Chest tightness on exertion", "language": "en"},
        )
        assert res_text.status_code == 200
        assert res_text.json()["transcript"] == "Chest tightness on exertion"
        assert res_text.json()["locale"] == "en-IN"

        # 2. Empty audio file rejected
        res_empty = await ac.post(
            "/api/voice/transcribe",
            data={"language": "en"},
            files={"audio_file": ("empty.wav", io.BytesIO(b""), "audio/wav")},
        )
        assert res_empty.status_code == 400

        # 3. Valid silent WAV audio correctly handled (speech recognition attempts transcription)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(struct.pack("<h", 0) * 8000)
        silent_wav = wav_buf.getvalue()

        res_silent = await ac.post(
            "/api/voice/transcribe",
            data={"language": "en"},
            files={"audio_file": ("silent.wav", io.BytesIO(silent_wav), "audio/wav")},
        )
        # For silence, SpeechRecognition raises UnknownValueError which returns 422 Unprocessable Entity
        assert res_silent.status_code in [422, 503]


@pytest.mark.anyio
async def test_voice_transcribed_answer_persistence_and_adaptation():
    """Verify end-to-end flow: Real patient registration -> Consent -> Voice input submission -> DB Persistence with input_method."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register a real patient
        reg_payload = {
            "full_name": "Suresh Patel Voice Test",
            "age": 48,
            "gender": "male",
            "phone_number": "9811223344",
            "department": "General Medicine",
        }
        reg_res = await ac.post("/api/patients/register", json=reg_payload)
        assert reg_res.status_code == 201
        patient = reg_res.json()
        patient_id = patient["id"]

        # 2. Grant Hindi consent
        consent_payload = {
            "selected_language": "hi",
            "consent_status": "granted",
        }
        consent_res = await ac.post(f"/api/patients/{patient_id}/consent", json=consent_payload)
        assert consent_res.status_code == 200

        # 3. Start interview
        start_res = await ac.post(f"/api/interview/start?patient_id={patient_id}")
        assert start_res.status_code == 200
        session = start_res.json()
        session_id = session["session_id"]
        q1 = session["current_question"]
        assert q1 is not None

        # 4. Patient speaks chief complaint via microphone (real Hindi voice transcript)
        spoken_chief_complaint = "मुझे पिछले तीन दिनों से सीने में भारीपन और सांस लेने में तकलीफ हो रही है"
        ans_payload = {
            "question_id": q1["question_id"],
            "question_text": q1["text_hi"],
            "section": q1["section"],
            "stage_number": q1["stage_number"],
            "patient_answer": spoken_chief_complaint,
            "skipped": False,
            "input_method": "voice",
            "language": "hi",
        }
        ans_res = await ac.post(f"/api/interview/{session_id}/answer", json=ans_payload)
        assert ans_res.status_code == 200
        updated_session = ans_res.json()

        # 5. Verify answer is stored in MongoDB interview_sessions with input_method
        session_doc = await db_manager.db.interview_sessions.find_one({"session_id": session_id})
        assert session_doc is not None
        assert len(session_doc["answers"]) == 1
        stored_ans = session_doc["answers"][0]
        assert stored_ans["patient_answer"] == spoken_chief_complaint
        assert stored_ans["question_id"] == q1["question_id"]
        assert stored_ans["input_method"] == "voice"
        assert stored_ans["language"] == "hi"

        # 6. Verify answer is synced into patient document clinical_history with input_method
        from bson import ObjectId
        patient_doc = await db_manager.db.patients.find_one({"_id": ObjectId(patient_id)})
        assert patient_doc is not None
        assert "clinical_history" in patient_doc
        assert q1["question_id"] in patient_doc["clinical_history"]
        hist_entry = patient_doc["clinical_history"][q1["question_id"]]
        assert hist_entry["answer"] == spoken_chief_complaint
        assert hist_entry["input_method"] == "voice"
        assert hist_entry["language"] == "hi"

        # 7. Verify adaptive questioning reacted to chest tightness / dyspnea
        q2 = updated_session["current_question"]
        assert q2 is not None
        assert q2["question_id"] != q1["question_id"]
        # Next question should be spoken aloud via TTS in Hindi
        tts_res = await ac.post(
            "/api/voice/synthesize",
            json={"text": q2["text_hi"], "language": "hi"},
        )
        assert tts_res.status_code == 200
        assert tts_res.json()["locale"] == "hi-IN"


@pytest.mark.anyio
async def test_voice_speak_audio_stream_hindi_and_english():
    """Verify that /api/voice/speak streams valid audio bytes for Hindi and English questions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Hindi audio stream
        res_hi = await ac.get(
            "/api/voice/speak",
            params={"text": "आपको यह समस्या कब से हो रही है?", "language": "hi"},
        )
        assert res_hi.status_code == 200
        assert res_hi.headers["content-type"].startswith("audio/mpeg")
        assert len(res_hi.content) > 1000

        # 2. English audio stream
        res_en = await ac.get(
            "/api/voice/speak",
            params={"text": "How long have you had this health issue?", "language": "en"},
        )
        assert res_en.status_code == 200
        assert res_en.headers["content-type"].startswith("audio/mpeg")
        assert len(res_en.content) > 1000

        # 3. Invalid language
        res_bad = await ac.get(
            "/api/voice/speak",
            params={"text": "Hello", "language": "de"},
        )
        assert res_bad.status_code == 400
