from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["languages"])


class LanguageOption(BaseModel):
    code: str
    name: str
    native_name: str
    ui_supported: bool
    voice_supported: bool
    description: str
    voice_locale: str = "en-IN"


# Modular language registry designed for future Indian language expansion
SUPPORTED_LANGUAGES: List[LanguageOption] = [
    LanguageOption(
        code="en",
        name="English",
        native_name="English",
        ui_supported=True,
        voice_supported=True,
        description="Standard English UI intake with Indian English voice interface (en-IN)",
        voice_locale="en-IN",
    ),
    LanguageOption(
        code="hi",
        name="Hindi",
        native_name="हिन्दी",
        ui_supported=True,
        voice_supported=True,
        description="हिन्दी भाषा इंटरफ़ेस (आवाज इनपुट और स्पीच समर्थित - hi-IN)",
        voice_locale="hi-IN",
    ),
]


@router.get(
    "/languages",
    response_model=List[LanguageOption],
    summary="List supported languages",
    description="Returns available kiosk languages with explicit UI and speech capability flags.",
)
async def get_supported_languages():
    return SUPPORTED_LANGUAGES
