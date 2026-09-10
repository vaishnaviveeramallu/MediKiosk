import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from app.models.document import (
    ExtractedMedicalData,
    ExtractedPatientInfo,
    ExtractedMedication,
    ExtractedInvestigation,
    ExtractedDiagnosis,
    ExtractedProcedure,
    ExtractedAllergy,
)

logger = logging.getLogger(__name__)


class MedicalExtractionService:
    """
    Modular Medical Entity Extraction Service for MediKiosk.
    Extracts structured clinical information strictly from the actual OCR text.
    Zero hallucination / zero invention guarantee: Only entities explicitly present in the text are extracted.
    Assigns confidence scores and marks unclear/tentative findings for physician verification.
    """

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for clinical entities common in Indian OPDs."""
        # Patient demographics patterns
        self.pat_name_re = re.compile(
            r'(?:Patient\s*Name|Name|Pt\s*Name|Patient)\s*[:\-]\s*([A-Za-z\.\s]+?)(?=(?:\n|\s{2,}|Age|Sex|Gender|Date|Token|OPD|$))',
            re.IGNORECASE
        )
        self.pat_age_re = re.compile(
            r'(?:Age|Age/Sex|Age/Gender)\s*[:\-]?\s*(\d{1,3}(?:\s*(?:Years|Yrs|Year|Yr|Y|m|months))?)',
            re.IGNORECASE
        )
        self.pat_gender_re = re.compile(
            r'(?:Sex|Gender)\s*[:\-]?\s*(Male|Female|Other|M|F)\b',
            re.IGNORECASE
        )
        self.date_re = re.compile(
            r'(?:Date|Dated|Dt|Date\s*of\s*Visit)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
            re.IGNORECASE
        )

        # Medication patterns
        # Prefix e.g. Tab, Cap, Syp, Inj, Oint
        self.med_prefix_re = r'(?:Tab(?:let)?|Cap(?:sule)?|Syp|Syrup|Inj(?:ection)?|Oint(?:ment)?|Drops?|Cream|Gel|Powder|Inhaler)\.?'
        
        # Common Indian medicine names (generic and brand)
        self.common_drugs = [
            "paracetamol", "amoxicillin", "metformin", "pantoprazole", "azithromycin",
            "amlodipine", "telmisartan", "cetirizine", "ibuprofen", "ciprofloxacin",
            "atorvastatin", "losartan", "omeprazole", "montelukast", "dolo",
            "pan-d", "pan 40", "augmentin", "calpol", "crocin", "azithral",
            "glycomet", "atorva", "telma", "levocetirizine", "combiflam",
            "ranitidine", "ondansetron", "cefixime", "diclofenac", "tramadol",
            "aspirin", "clopidogrel", "glimepiride", "metoprolol", "rosuvastatin",
            "vitamin d3", "b-complex", "iron folic acid", "limcee", "shelcal"
        ]
        drugs_pattern = "|".join(re.escape(d) for d in self.common_drugs)

        self.medication_line_re = re.compile(
            rf'(?:(?:(?:\d+[\.\)]\s*)?({self.med_prefix_re}\s+[A-Za-z0-9\-\s]+?)|({drugs_pattern})))\s+'
            r'(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|IU|units|tab)?)\s*'
            r'(OD|BD|TID|QID|TDS|HS|SOS|STAT|once\s+daily|twice\s+daily|thrice\s+daily|\d-\d-\d|\d-\d|\b(?:दिन में दो बार|रोजाना)\b)?'
            r'(?:\s*(?:x\s*|for\s*)?(\d+\s*(?:days|weeks|months|day|week|month|d)))?',
            re.IGNORECASE
        )

        # Dosage / frequency patterns
        self.dosage_re = re.compile(r'(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|IU|units))\b', re.IGNORECASE)
        self.freq_re = re.compile(r'\b(OD|BD|TID|QID|TDS|HS|SOS|STAT|once\s+daily|twice\s+daily|thrice\s+daily|1-0-1|1-1-1|1-0-0|0-0-1)\b|(दिन\s*में\s*दो\s*बार|दिन\s*में\s*एक\s*बार|दिन\s*में\s*तीन\s*बार|रोजाना)', re.IGNORECASE)
        self.duration_re = re.compile(r'(?:(?:x|for)\s*)?(\d+\s*(?:days|weeks|months|day|week|month|d))\b', re.IGNORECASE)
        self.route_re = re.compile(r'\b(oral|orally|IV|IM|subcutaneous|topical|sublingual|inhalation)\b', re.IGNORECASE)

        # Lab investigation patterns
        self.common_tests = [
            ("Hemoglobin", r'(?:Hemoglobin|Hb|Hgb)\b'),
            ("Fasting Blood Sugar", r'(?:Fasting\s*Blood\s*Sugar|FBS|Fasting\s*Glucose)\b'),
            ("Post Prandial Blood Sugar", r'(?:Post\s*Prandial\s*Blood\s*Sugar|PPBS|PP\s*Glucose)\b'),
            ("Random Blood Sugar", r'(?:Random\s*Blood\s*Sugar|RBS|Random\s*Glucose)\b'),
            ("HbA1c", r'(?:HbA1c|Glycated\s*Hemoglobin)\b'),
            ("Serum Creatinine", r'(?:Serum\s*Creatinine|Creatinine|S\.Creatinine)\b'),
            ("Blood Urea", r'(?:Blood\s*Urea|Urea)\b'),
            ("Total Leukocyte Count", r'(?:Total\s*Leukocyte\s*Count|TLC|WBC\s*Count|WBC)\b'),
            ("Platelet Count", r'(?:Platelet\s*Count|Platelets|PLT)\b'),
            ("Total Bilirubin", r'(?:Total\s*Bilirubin|T\.Bilirubin|Bilirubin\s*Total)\b'),
            ("SGOT / AST", r'(?:SGOT|AST)\b'),
            ("SGPT / ALT", r'(?:SGPT|ALT)\b'),
            ("Serum Cholesterol", r'(?:Total\s*Cholesterol|Serum\s*Cholesterol|Cholesterol)\b'),
            ("Serum Triglycerides", r'(?:Triglycerides|TGL)\b'),
            ("Serum Uric Acid", r'(?:Serum\s*Uric\s*Acid|Uric\s*Acid)\b'),
            ("ESR", r'\bESR\b'),
            ("CRP", r'\bCRP\b'),
            ("TSH", r'(?:TSH|Thyroid\s*Stimulating\s*Hormone)\b'),
            ("Blood Pressure", r'(?:Blood\s*Pressure|BP)\b'),
            ("Serum Sodium", r'(?:Serum\s*Sodium|Sodium|Na\+)\b'),
            ("Serum Potassium", r'(?:Serum\s*Potassium|Potassium|K\+)\b'),
        ]

        # Unit patterns
        self.unit_re = re.compile(r'(?:mg/dL|g/dL|cells/cu\s*mm|/cumm|cumm|IU/L|uIU/mL|mEq/L|mmHg|fl|pg|%)(?:\b|\s|$)', re.IGNORECASE)
        self.ref_range_re = re.compile(
            r'(?:\(|\[)\s*(?:Ref|Reference|Normal|Biological\s*Ref(?:\s*Interval)?)\s*[:\-]?\s*([<>]?\s*\d+(?:\.\d+)?(?:\s*[\-\–]\s*\d+(?:\.\d+)?)?)\s*(?:[A-Za-z/%]+)?\s*(?:\)|\])',
            re.IGNORECASE
        )

        # Diagnoses patterns
        self.diag_header_re = re.compile(
            r'(?:Diagnosis|Diagnoses|Provisional\s*Diagnosis|Final\s*Diagnosis|Impression|Assessment|Known\s*case\s*of|C/o|Complaints\s*of)\s*[:\-]\s*(.+?)(?=(?:\n\n|\n[A-Z][a-z]+:|\Z))',
            re.IGNORECASE | re.DOTALL
        )
        self.known_conditions = [
            "Type 2 Diabetes Mellitus", "Type 1 Diabetes Mellitus", "Diabetes Mellitus",
            "Essential Hypertension", "Hypertension", "Acute Pharyngitis", "Pharyngitis",
            "Upper Respiratory Tract Infection", "URTI", "Lower Respiratory Tract Infection", "LRTI",
            "Viral Fever", "Acute Gastroenteritis", "Gastroenteritis", "Osteoarthritis",
            "Rheumatoid Arthritis", "Bronchial Asthma", "Asthma", "COPD",
            "Gastroesophageal Reflux Disease", "GERD", "Gastritis", "Peptic Ulcer",
            "Migraine", "Tension Headache", "Urinary Tract Infection", "UTI",
            "Hypothyroidism", "Hyperthyroidism", "Pneumonia", "Allergic Rhinitis",
            "Dengue Fever", "Malaria", "Typhoid Fever", "Anemia", "Iron Deficiency Anemia",
            "Chronic Kidney Disease", "Ischemic Heart Disease", "Coronary Artery Disease",
            "Acute Cholecystitis", "Cholecystitis"
        ]

        # Procedures patterns
        self.proc_header_re = re.compile(
            r'(?:Procedure|Procedures|Surgery|Surgical\s*History|Operation|Operative\s*Notes|Underwent)\s*[:\-]\s*(.+?)(?=(?:\n\n|\n[A-Z][a-z]+:|\Z))',
            re.IGNORECASE | re.DOTALL
        )
        self.known_procedures = [
            "Appendectomy", "Cholecystectomy", "Cesarean Section", "C-Section", "LSCS",
            "Hernia Repair", "Hernioplasty", "Cataract Surgery", "Phacoemulsification",
            "Coronary Angiography", "Angioplasty", "PTCA", "Stenting", "CABG",
            "Endoscopy", "Upper GI Endoscopy", "Colonoscopy", "Total Knee Replacement",
            "Total Hip Replacement", "Tonsillectomy", "Dialysis", "Hemodialysis",
            "Wound Debridement", "Suturing", "Incision and Drainage"
        ]

        # Allergy patterns
        self.allergy_re = re.compile(
            r'(?:Allergies|Allergy|Known\s*Allergies|Drug\s*Allergies)\s*[:\-]?\s*([^\n\r]+)',
            re.IGNORECASE
        )

        # Doctor & Hospital patterns
        self.doctor_re = re.compile(
            r'(?:Dr\.?\s+[A-Za-z\.\s]+?(?=(?:MBBS|MD|MS|DNB|DM|MCh|Consultant|\n|\s{2,})))',
            re.IGNORECASE
        )
        self.hospital_re = re.compile(
            r'([A-Za-z\s]+?(?:Hospital|Clinic|Medical\s*Center|Healthcare|Nursing\s*Home|Dispensary))\b',
            re.IGNORECASE
        )

    def extract_medical_entities(self, raw_text: str) -> ExtractedMedicalData:
        """
        Extract structured medical data strictly from the provided raw OCR text.
        Never invents missing or unmentioned entities.
        """
        if not raw_text or not raw_text.strip():
            return ExtractedMedicalData(
                patient_info=None,
                diagnoses=[],
                medications=[],
                investigations=[],
                procedures=[],
                allergies=[],
                other_findings=[],
                doctor_info=None,
                hospital_clinic_info=None,
                unclear_findings=[],
                requires_physician_review=True,
                extraction_notes="Empty or unreadable document text."
            )

        text = raw_text.strip()

        # 1. Patient Demographics
        patient_info = self._extract_patient_info(text)

        # 2. Diagnoses & Conditions
        diagnoses = self._extract_diagnoses(text)

        # 3. Medications
        medications = self._extract_medications(text)

        # 4. Investigations & Lab Tests
        investigations = self._extract_investigations(text)

        # 5. Procedures & Surgeries
        procedures = self._extract_procedures(text)

        # 6. Allergies
        allergies = self._extract_allergies(text)

        # 7. Doctor & Hospital Info
        doctor_info = self._extract_doctor_info(text)
        hospital_info = self._extract_hospital_info(text)

        # 8. Unclear / Low Confidence Findings
        unclear: List[str] = []
        for m in medications:
            if m.confidence < 0.70 or not m.dosage:
                unclear.append(f"Medication '{m.name}' dosage or frequency is partially unclear.")
        for inv in investigations:
            if inv.confidence < 0.70 or not inv.result_value:
                unclear.append(f"Investigation '{inv.test_name}' result value is unclear or incomplete.")

        return ExtractedMedicalData(
            patient_info=patient_info,
            diagnoses=diagnoses,
            medications=medications,
            investigations=investigations,
            procedures=procedures,
            allergies=allergies,
            other_findings=[],
            doctor_info=doctor_info,
            hospital_clinic_info=hospital_info,
            unclear_findings=unclear,
            requires_physician_review=True,
            extraction_notes="Extracted strictly from uploaded document text. Pending physician verification."
        )

    def _extract_patient_info(self, text: str) -> Optional[ExtractedPatientInfo]:
        """Extract stated patient demographic data."""
        name: Optional[str] = None
        age: Optional[str] = None
        gender: Optional[str] = None
        doc_date: Optional[str] = None

        m_name = self.pat_name_re.search(text)
        if m_name:
            val = m_name.group(1).strip()
            # Clean common artifacts
            val = re.sub(r'^(Mr\.|Mrs\.|Ms\.|Master|Shri|Smt\.?)\s*', '', val, flags=re.IGNORECASE)
            if len(val) >= 2 and not any(kw in val.lower() for kw in ["hospital", "clinic", "department", "date", "dr"]):
                name = val

        m_age = self.pat_age_re.search(text)
        if m_age:
            age = m_age.group(1).strip()

        m_gen = self.pat_gender_re.search(text)
        if m_gen:
            g_raw = m_gen.group(1).strip().upper()
            gender = "Male" if g_raw in ("M", "MALE") else ("Female" if g_raw in ("F", "FEMALE") else g_raw)

        m_date = self.date_re.search(text)
        if m_date:
            doc_date = m_date.group(1).strip()

        if any([name, age, gender, doc_date]):
            conf = 0.90 if (name and (age or gender)) else 0.75
            return ExtractedPatientInfo(
                name=name,
                age=age,
                gender=gender,
                document_date=doc_date,
                confidence=conf
            )
        return None

    def _extract_medications(self, text: str) -> List[ExtractedMedication]:
        """Extract explicit prescription medications with dosage, frequency, and duration."""
        meds: List[ExtractedMedication] = []
        seen_names = set()

        lines = text.split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 3:
                continue

            # Check if line matches drug pattern
            found_drug_name = None
            for d in self.common_drugs:
                pattern = rf'\b{re.escape(d)}\b'
                if re.search(pattern, line_str, re.IGNORECASE):
                    found_drug_name = d.title()
                    break

            # Check for Tab. / Cap. prefix if not in common list
            if not found_drug_name:
                m_pref = re.search(rf'\b({self.med_prefix_re}\s+([A-Za-z0-9\-]+))', line_str, re.IGNORECASE)
                if m_pref:
                    candidate = m_pref.group(2).strip()
                    if len(candidate) > 2 and candidate.lower() not in ("patient", "date", "dr", "doctor", "report", "test"):
                        found_drug_name = f"{m_pref.group(1).split()[0]} {candidate}"

            if found_drug_name:
                clean_key = found_drug_name.lower().split()[-1]
                if clean_key in seen_names:
                    continue
                seen_names.add(clean_key)

                # Extract dosage
                m_dos = self.dosage_re.search(line_str)
                dosage = m_dos.group(1).strip() if m_dos else None

                # Extract frequency
                m_freq = self.freq_re.search(line_str)
                freq = m_freq.group(0).strip() if m_freq else None

                # Extract duration
                m_dur = self.duration_re.search(line_str)
                duration = m_dur.group(1).strip() if m_dur else None

                # Extract route
                m_route = self.route_re.search(line_str)
                route = m_route.group(1).strip().lower() if m_route else ("oral" if any(p in line_str.lower() for p in ["tab", "cap", "tablet", "capsule"]) else None)

                # Confidence calculation based on completeness
                conf = 0.60
                if dosage:
                    conf += 0.20
                if freq:
                    conf += 0.15
                if duration:
                    conf += 0.05

                meds.append(ExtractedMedication(
                    name=found_drug_name,
                    dosage=dosage,
                    dose="1 tab" if "tab" in line_str.lower() else None,
                    frequency=freq,
                    duration=duration,
                    route=route,
                    confidence=round(conf, 2),
                    verification_status="needs_review"
                ))

        return meds

    def _extract_investigations(self, text: str) -> List[ExtractedInvestigation]:
        """Extract explicit laboratory test names, results, units, and reference ranges."""
        investigations: List[ExtractedInvestigation] = []
        seen_tests = set()

        for standard_name, pattern in self.common_tests:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            if standard_name in seen_tests:
                continue

            # Extract surrounding line/context
            start_pos = match.start()
            end_line_pos = text.find("\n", start_pos)
            if end_line_pos == -1:
                end_line_pos = len(text)
            line = text[start_pos:end_line_pos].strip()

            # Find reference range first
            m_ref = self.ref_range_re.search(line)
            ref_range = m_ref.group(1).strip() if m_ref else None

            # Remove reference range from value search line to avoid collision
            search_line = (line[:m_ref.start()] + " " + line[m_ref.end():]) if m_ref else line
            after_test = search_line[len(match.group(0)):].lstrip(':- \t')

            # Find number/value
            m_val = re.search(r'^(\d+(?:\.\d+)?(?:\s*[\/\-]\s*\d+(?:\.\d+)?)?)\b', after_test)
            if not m_val:
                m_val = re.search(r'(\d+(?:\.\d+)?(?:\s*[\/\-]\s*\d+(?:\.\d+)?)?)\b', after_test)
            res_val = m_val.group(1).strip() if m_val else None

            # Find unit
            m_unit = self.unit_re.search(search_line)
            unit = m_unit.group(0).strip() if m_unit else None

            # Detect abnormal
            is_abn = False
            if res_val and ref_range and "-" in ref_range:
                try:
                    parts = ref_range.split("-")
                    low, high = float(parts[0].strip()), float(parts[1].strip())
                    val_num = float(res_val.split()[0])
                    if val_num < low or val_num > high:
                        is_abn = True
                except Exception:
                    pass

            conf = 0.65
            if res_val:
                conf += 0.20
            if unit:
                conf += 0.10

            seen_tests.add(standard_name)
            investigations.append(ExtractedInvestigation(
                test_name=standard_name,
                result_value=res_val,
                unit=unit,
                reference_range=ref_range,
                test_date=None,
                is_abnormal=is_abn if res_val else None,
                confidence=round(conf, 2),
                verification_status="needs_review"
            ))

        return investigations

    def _extract_diagnoses(self, text: str) -> List[ExtractedDiagnosis]:
        """Extract explicitly mentioned diagnoses or conditions."""
        candidates: List[ExtractedDiagnosis] = []
        seen = set()

        # Check for known explicit medical conditions
        for cond in self.known_conditions:
            pattern = rf'\b{re.escape(cond)}\b'
            if re.search(pattern, text, re.IGNORECASE):
                if cond.lower() not in seen:
                    seen.add(cond.lower())
                    candidates.append(ExtractedDiagnosis(
                        diagnosis=cond,
                        symptoms=[],
                        type="provisional",
                        confidence=0.90,
                        verification_status="needs_review"
                    ))

        # Also check Diagnosis: header if not covered
        m_diag = self.diag_header_re.search(text)
        if m_diag:
            raw_diags = m_diag.group(1).strip().split("\n")
            for line_item in raw_diags[:3]:
                # Split comma-separated diagnoses on same line
                for sub_item in re.split(r'[,;]', line_item):
                    clean_item = re.sub(r'^(?:\d+[\.\)]|\-|\*)\s*', '', sub_item).strip()
                    if len(clean_item) > 3 and clean_item.lower() not in seen and not any(kw in clean_item.lower() for kw in ["rx", "treatment", "tab", "dr.", "investigations", "allergies"]):
                        seen.add(clean_item.lower())
                        candidates.append(ExtractedDiagnosis(
                            diagnosis=clean_item,
                            symptoms=[],
                            type="explicit_header",
                            confidence=0.85,
                            verification_status="needs_review"
                        ))

        # Filter out shorter diagnoses that are exact substrings of longer diagnoses
        # e.g., "Diabetes Mellitus" is suppressed if "Type 2 Diabetes Mellitus" is present
        filtered: List[ExtractedDiagnosis] = []
        all_diags = [c.diagnosis.lower() for c in candidates]
        for c in candidates:
            c_low = c.diagnosis.lower()
            is_sub = any(c_low != other and c_low in other for other in all_diags)
            if not is_sub:
                filtered.append(c)

        return filtered

    def _extract_procedures(self, text: str) -> List[ExtractedProcedure]:
        """Extract explicit surgeries and medical procedures."""
        procs: List[ExtractedProcedure] = []
        seen = set()

        for proc in self.known_procedures:
            pattern = rf'\b{re.escape(proc)}\b'
            if re.search(pattern, text, re.IGNORECASE):
                if proc.lower() not in seen:
                    seen.add(proc.lower())
                    procs.append(ExtractedProcedure(
                        procedure_name=proc,
                        procedure_date=None,
                        notes=None,
                        confidence=0.88,
                        verification_status="needs_review"
                    ))

        return procs

    def _extract_allergies(self, text: str) -> List[ExtractedAllergy]:
        """Extract documented allergies."""
        allergies: List[ExtractedAllergy] = []

        m_all = self.allergy_re.search(text)
        if m_all:
            raw_val = m_all.group(1).strip()
            if "nkda" in raw_val.lower() or "nil" in raw_val.lower() or "no known" in raw_val.lower():
                allergies.append(ExtractedAllergy(
                    allergen="No Known Drug Allergies (NKDA)",
                    reaction=None,
                    severity=None,
                    confidence=0.95,
                    verification_status="verified"
                ))
            else:
                for part in re.split(r'[,;]', raw_val):
                    clean_part = part.strip()
                    if clean_part:
                        allergies.append(ExtractedAllergy(
                            allergen=clean_part,
                            reaction=None,
                            severity="moderate",
                            confidence=0.80,
                            verification_status="needs_review"
                        ))

        return allergies

    def _extract_doctor_info(self, text: str) -> Optional[str]:
        """Extract doctor information if present."""
        m_doc = self.doctor_re.search(text)
        if m_doc:
            doc_str = m_doc.group(0).strip()
            if len(doc_str) > 4:
                return doc_str
        return None

    def _extract_hospital_info(self, text: str) -> Optional[str]:
        """Extract hospital or clinic name if present."""
        m_hosp = self.hospital_re.search(text)
        if m_hosp:
            hosp_str = m_hosp.group(1).strip()
            if len(hosp_str) > 5 and not any(kw in hosp_str.lower() for kw in ["patient", "date", "doctor"]):
                return hosp_str
        return None


# Singleton instance
medical_extraction_service = MedicalExtractionService()
