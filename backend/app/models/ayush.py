from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AYUSHHistoryMode(str, Enum):
    GENERAL = "general"
    AYUSH = "ayush"


class DashavidhaPariksha(BaseModel):
    """
    Classical Ayurvedic Ten-Fold Clinical Assessment Parameters (Dashavidha Pariksha)
    Structured strictly from patient-reported responses. Never auto-diagnosed.
    """
    prakriti: Optional[str] = Field(None, description="Reported constitutional traits (Vata/Pitta/Kapha tendencies)")
    vikriti: Optional[str] = Field(None, description="Reported current dosha imbalance or morbidity site")
    sara: Optional[str] = Field(None, description="Tissue excellence / constitutional essence (Dhatu Sara)")
    samhanana: Optional[str] = Field(None, description="Body compactness / muscular build (Sushlishta / Madhyama / Asamhat)")
    pramana: Optional[str] = Field(None, description="Body proportions and stature")
    satmya: Optional[str] = Field(None, description="Adaptability / dietary habituation (Oka Satmya / Desha Satmya)")
    satva: Optional[str] = Field(None, description="Mental stamina / psychic constitution (Pravara / Madhyama / Avara Satva)")
    ahara_shakti: Optional[str] = Field(None, description="Food intake capacity (Abhyavaharana) and digestive capacity (Jarana Shakti)")
    vyayama_shakti: Optional[str] = Field(None, description="Physical exertion and work capacity (Karma Shakti)")
    vaya: Optional[str] = Field(None, description="Life stage / age category (Bala, Madhyama, Vriddha)")


class AYUSHClinicalData(BaseModel):
    """
    Comprehensive structured AYUSH Clinical History parameters.
    """
    prakriti: Optional[str] = Field(None, description="Reported constitutional tendencies")
    vikriti: Optional[str] = Field(None, description="Reported current health imbalance / chief complaint")
    agni: Optional[str] = Field(None, description="Digestive fire state: Sama (balanced), Tikshna (sharp), Manda (slow), or Vishama (erratic)")
    koshta: Optional[str] = Field(None, description="Bowel habit nature: Mridu (soft/lax), Madhyama (moderate), or Krura (hard/constipated)")
    bala: Optional[str] = Field(None, description="Physical and immune vitality: Pravara (high), Madhyama (moderate), or Avara (low)")
    satmya: Optional[str] = Field(None, description="Dietary and climate habituation / food tolerances")
    ahara: Optional[str] = Field(None, description="Dietary routine, preferred tastes (Rasa), meal timings, appetite")
    vihara: Optional[str] = Field(None, description="Daily regimen (Dinacharya), physical activity, occupation, day sleep")
    vyayama_shakti: Optional[str] = Field(None, description="Physical exertion and stamina capacity")
    nidra: Optional[str] = Field(None, description="Sleep quality, duration, daytime drowsiness, sleep disturbances")
    mala: Optional[str] = Field(None, description="Bowel elimination frequency, consistency, bloating, gas")
    mutra: Optional[str] = Field(None, description="Urination pattern, frequency, color, burning/dysuria")
    manasika: Optional[str] = Field(None, description="Mental temperament, stress level, irritability, mental clarity")
    lifestyle: Optional[str] = Field(None, description="Daily habits, substance use (tobacco/alcohol), routine regularity")
    personal_history: Optional[str] = Field(None, description="Past medical ailments, surgeries, childhood illnesses")
    family_history: Optional[str] = Field(None, description="Hereditary medical history in family line")
    treatment_history: Optional[str] = Field(None, description="Prior Ayurvedic/AYUSH treatments, Panchakarma, co-medications")
    dashavidha_pariksha: Optional[DashavidhaPariksha] = None
    patient_reported_prakriti_notes: Optional[str] = None
    attending_physician_notes: Optional[str] = None
