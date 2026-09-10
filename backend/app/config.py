from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MONGODB_URI: str = "mongodb://127.0.0.1:27017"
    DATABASE_NAME: str = "medikiosk"
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # AI Service Configuration
    AI_API_KEY: Union[str, None] = None
    AI_MODEL: str = "gemini-1.5-flash"
    AI_PROVIDER: str = "gemini"  # "gemini", "openai", or "heuristic"
    AI_TIMEOUT_SECONDS: float = 8.0
    MAX_ADAPTIVE_QUESTIONS: int = 15

    # OCR and Medical Document Processing
    TESSERACT_CMD: Union[str, None] = None
    TESSDATA_PREFIX: Union[str, None] = None
    OCR_MAX_PAGES: int = 10
    OCR_TIMEOUT_SECONDS: float = 30.0
    OCR_DEFAULT_LANGUAGES: str = "eng+hin"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(item) for item in v]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()
