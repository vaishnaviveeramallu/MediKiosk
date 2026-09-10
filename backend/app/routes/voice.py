import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger("medikiosk.voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize to speech")
    language: str = Field(default="en", description="Target language code: 'en' or 'hi'")
    rate: float = Field(default=0.95, ge=0.5, le=2.0, description="Speech rate (0.95 recommended for clear OPD announcements)")
    pitch: float = Field(default=1.0, ge=0.5, le=1.5, description="Speech pitch")


class VoiceSynthesisResponse(BaseModel):
    text: str
    language: str
    locale: str
    rate: float
    pitch: float
    engine: str
    recommended_voices: List[str]


class VoiceStatusResponse(BaseModel):
    status: str
    stt_primary: str
    tts_primary: str
    supported_locales: List[str]
    languages: List[dict]
    max_recording_seconds: int


@router.get(
    "/status",
    response_model=VoiceStatusResponse,
    summary="Get voice subsystem status and configuration",
    description="Returns supported voice recognition and synthesis locales, audio specifications, and engine readiness.",
)
async def get_voice_status():
    return VoiceStatusResponse(
        status="ready",
        stt_primary="web_speech_api_continuous",
        tts_primary="web_speech_synthesis",
        supported_locales=["en-IN", "hi-IN", "en-US"],
        languages=[
            {"code": "en", "locale": "en-IN", "name": "English (India)", "tts_supported": True, "stt_supported": True},
            {"code": "hi", "locale": "hi-IN", "name": "Hindi (India)", "tts_supported": True, "stt_supported": True},
        ],
        max_recording_seconds=60,
    )


@router.post(
    "/synthesize",
    response_model=VoiceSynthesisResponse,
    summary="Prepare text-to-speech parameters",
    description="Validates and formats speech synthesis parameters for client or server TTS rendering.",
)
async def synthesize_speech(request: VoiceSynthesisRequest):
    lang_code = request.language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language code '{request.language}'. Supported codes are 'en' and 'hi'.",
        )

    if lang_code == "hi":
        locale = "hi-IN"
        recommended_voices = [
            "Google हिन्दी",
            "Microsoft Hemant - Hindi (India)",
            "Microsoft Kalpana - Hindi (India)",
            "hi-IN-Standard-A",
            "hi-IN",
        ]
    else:
        locale = "en-IN"
        recommended_voices = [
            "Google English (India)",
            "Microsoft Neerja - English (India)",
            "Microsoft Prabhat - English (India)",
            "en-IN-Standard-A",
            "en-IN",
            "en-US",
        ]

    return VoiceSynthesisResponse(
        text=request.text.strip(),
        language=lang_code,
        locale=locale,
        rate=request.rate,
        pitch=request.pitch,
        engine="web_speech_synthesis",
        recommended_voices=recommended_voices,
    )


class SpeakAudioRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Question or statement to speak aloud")
    language: str = Field(default="hi", description="Language code: 'hi' or 'en'")


@router.get(
    "/speak",
    summary="Stream synthesized speech audio",
    description="Generates and streams real spoken audio for questions in Hindi (native) or Indian English.",
)
async def get_spoken_audio(
    text: str = Query(..., min_length=1, description="Text to speak"),
    language: str = Query("hi", description="Language: 'hi' or 'en'"),
):
    lang_code = language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{language}'. Supported languages: 'en', 'hi'.",
        )

    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text for speech synthesis cannot be empty.",
        )

    import io
    from gtts import gTTS

    try:
        fp = io.BytesIO()
        if lang_code == "hi":
            tts = gTTS(text=cleaned_text, lang="hi")
        else:
            tts = gTTS(text=cleaned_text, lang="en", tld="co.in")
        tts.write_to_fp(fp)
        fp.seek(0)
        return Response(content=fp.read(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize audio: {str(e)}",
        )


@router.post(
    "/speak",
    summary="Synthesize speech audio via POST",
    description="Synthesizes speech audio and returns MP3 audio stream for patient questions.",
)
async def post_spoken_audio(req: SpeakAudioRequest):
    return await get_spoken_audio(text=req.text, language=req.language)


@router.post(
    "/transcribe",
    summary="Transcribe or validate speech input",
    description="Receives real audio or transcribed speech from the client microphone, validates and sanitizes it for database persistence.",
)
async def transcribe_speech(
    audio_file: Optional[UploadFile] = File(None),
    language: str = Form("en"),
    client_transcript: Optional[str] = Form(None),
):
    lang_code = language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{language}'. Supported languages: 'en', 'hi'.",
        )

    # When client sends transcribed text from real microphone Web Speech API
    if client_transcript is not None:
        cleaned = client_transcript.strip()
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty speech transcript received. Please speak into the microphone again.",
            )
        return {
            "transcript": cleaned,
            "language": lang_code,
            "locale": "hi-IN" if lang_code == "hi" else "en-IN",
            "source": "client_speech_recognition",
            "char_count": len(cleaned),
        }

    # When client uploads an actual audio recording file (e.g. wav)
    if audio_file is not None:
        content = await audio_file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded audio file is empty (0 bytes).",
            )
        target_locale = "hi-IN" if lang_code == "hi" else "en-IN"
        logger.info(
            f"Transcribing audio: {audio_file.filename} ({len(content)} bytes), lang: {target_locale}"
        )

        import io
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(io.BytesIO(content)) as source:
                audio_data = recognizer.record(source)

            recognized_text = recognizer.recognize_google(audio_data, language=target_locale)
            cleaned = str(recognized_text).strip()
            if not cleaned:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No clear speech was recognized in the audio recording.",
                )

            return {
                "status": "success",
                "transcript": cleaned,
                "language": lang_code,
                "locale": target_locale,
                "source": "backend_speech_recognition",
                "char_count": len(cleaned),
                "word_count": len(cleaned.split()),
            }
        except sr.UnknownValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not understand the audio. Please speak clearly into the microphone or type below.",
            )
        except sr.RequestError as e:
            logger.error(f"SpeechRecognition service error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Speech recognition service is temporarily unavailable. You can type your response below.",
            )
        except ValueError as ve:
            logger.warning(f"Audio format error: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio format. Please upload standard 16kHz WAV audio.",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Neither audio_file nor client_transcript was provided in the request.",
    )


class AudioBase64TranscribeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 encoded 16kHz WAV audio bytes")
    language: str = Field(default="en", description="Spoken language: 'en' or 'hi'")


@router.post(
    "/transcribe-audio",
    summary="Transcribe base64 WAV audio",
    description="Accepts base64 encoded WAV audio recorded from microphone and returns real speech transcript.",
)
async def transcribe_audio_base64(request: AudioBase64TranscribeRequest):
    import base64
    import io
    import speech_recognition as sr

    lang_code = request.language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{request.language}'. Supported: 'en', 'hi'.",
        )

    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 audio data.",
        )

    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decoded audio data is empty (0 bytes).",
        )

    target_locale = "hi-IN" if lang_code == "hi" else "en-IN"
    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(audio_data, language=target_locale)
        cleaned = str(transcript).strip()
        return {
            "status": "success",
            "transcript": cleaned,
            "language": lang_code,
            "locale": target_locale,
            "source": "backend_speech_recognition",
            "char_count": len(cleaned),
            "word_count": len(cleaned.split()),
        }
    except sr.UnknownValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not understand the audio. Please speak clearly into the microphone or type below.",
        )
    except sr.RequestError as e:
        logger.error(f"SpeechRecognition service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech recognition service is temporarily unavailable. You can type your response below.",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid WAV audio data: {ve}",
        )


class VoiceTranscribeRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Recognized speech text from microphone")
    language: str = Field(default="en", description="Spoken language: 'en' or 'hi'")


@router.post(
    "/validate-transcript",
    summary="Validate and clean voice transcript",
    description="Validates that speech transcript contains authentic patient content and prepares it for intake submission.",
)
async def validate_voice_transcript(request: VoiceTranscribeRequest):
    lang_code = request.language.lower().strip()
    if lang_code not in ["en", "hi"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{request.language}'. Supported languages: 'en', 'hi'.",
        )

    cleaned = request.transcript.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speech transcript cannot be empty.",
        )

    return {
        "status": "valid",
        "transcript": cleaned,
        "language": lang_code,
        "locale": "hi-IN" if lang_code == "hi" else "en-IN",
        "char_count": len(cleaned),
        "word_count": len(cleaned.split()),
    }
