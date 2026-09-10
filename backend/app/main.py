from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import settings
from app.database import db_manager
from app.routes.patient import router as patient_router
from app.routes.language import router as language_router
from app.routes.interview import router as interview_router
from app.routes.voice import router as voice_router
from app.routes.triage import router as triage_router
from app.routes.document import router as document_router, documents_direct_router
from app.routes.summary import router as summary_router
from app.routes.doctor import router as doctor_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("medikiosk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MediKiosk Backend Service...")
    try:
        await db_manager.connect()
        logger.info("MediKiosk Backend is fully ready to process patient registrations.")
    except Exception as e:
        logger.warning(
            f"Could not connect to MongoDB on startup ({e}). "
            "Ensure MongoDB is running at the configured MONGODB_URI."
        )
    yield
    logger.info("Shutting down MediKiosk Backend Service...")
    await db_manager.disconnect()


app = FastAPI(
    title="MediKiosk API",
    description="Backend service for MediKiosk – AI Patient Case-Taking Software in Indian OPDs",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for Next.js frontend
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patient_router)
app.include_router(language_router)
app.include_router(interview_router)
app.include_router(voice_router)
app.include_router(triage_router)
app.include_router(document_router)
app.include_router(documents_direct_router)
app.include_router(summary_router)
app.include_router(doctor_router)


@app.get("/", tags=["root"])
async def root():
    return {
        "service": "MediKiosk API",
        "status": "online",
        "docs": "/docs",
        "description": "Patient Intake and Clinical History Engine",
    }
