import re
import unicodedata
from typing import List, Optional, Dict, Any
from app.models.triage import TriageAlertPriority, TriageDetectionResult


class TriageDetector:
    """
    Deterministic, transparent rule-based Red-Flag and Triage symptom detector.
    Analyzes normalized patient responses in English, Hindi, and Hinglish.
    Does NOT diagnose diseases — identifies urgent clinical warning signs only.
    """

    EMERGENCY_INSTRUCTION_EN = (
        "Urgent attention may be needed. "
        "Please stop the questionnaire and immediately inform the hospital staff or proceed to the Emergency/Casualty Desk."
    )
    EMERGENCY_INSTRUCTION_HI = (
        "तत्काल चिकित्सा सहायता की आवश्यकता हो सकती है। "
        "कृपया प्रश्नावली रोकें और तुरंत अस्पताल के कर्मचारियों को सूचित करें या आपातकालीन/कैजुअल्टी डेस्क पर जाएं।"
    )

    RULES = [
        {
            "category": "cardiovascular_severe",
            "priority": TriageAlertPriority.URGENT,
            "description": "Severe chest pain, pressure, or cardiac warning symptoms detected",
            "keywords_en": [
                "severe chest pain", "crushing chest pain", "crushing pain",
                "chest pain and sweating", "chest pain and shortness of breath",
                "chest pain and difficulty breathing", "heavy chest pain",
                "chest pressure", "heavy pressure in chest", "pain in heart",
                "radiating to left arm", "radiating to arm", "radiating to jaw",
                "chest tightness and sweating", "squeezing chest pain",
                "chest pain", "chest discomfort", "heavy tightness in chest"
            ],
            "keywords_hi": [
                "सीने में बहुत तेज दर्द", "सीने में तेज दर्द", "छाती में तेज दर्द",
                "सीने में भारी दबाव", "सीने में जकड़न", "सीने में भारीपन",
                "दिल में तेज दर्द", "छाती में बहुत दर्द", "सीने का दर्द",
                "सीने में दर्द", "छाती में दर्द"
            ],
            "keywords_hinglish": [
                "chest me bahut tez dard", "chest me tez dard", "seene me tez dard",
                "seene me bahut dard", "chest pain bahut jyada", "seene me dard",
                "chest me heaviness", "chest me pressure", "chest me tight"
            ],
        },
        {
            "category": "respiratory_distress",
            "priority": TriageAlertPriority.URGENT,
            "description": "Acute respiratory distress, severe dyspnea, or airway compromise detected",
            "keywords_en": [
                "difficulty breathing", "severe difficulty breathing",
                "severe shortness of breath", "shortness of breath",
                "cannot breathe", "unable to breathe", "cant breathe",
                "gasping for air", "gasping", "choking", "choking sensation",
                "struggling to breathe", "severe breathlessness", "breathless while resting"
            ],
            "keywords_hi": [
                "सांस लेने में बहुत परेशानी", "सांस लेने में परेशानी",
                "सांस लेने में बहुत तकलीफ", "सांस लेने में तकलीफ", "सांस फूल रही है", "सांस नहीं आ रही",
                "दम घुट रहा है", "गंभीर सांस की तकलीफ", "सांस लेने में दिक्कत", "सांस लेने में बहुत दिक्कत",
                "सांस फूलना", "सांस रुक रही है"
            ],
            "keywords_hinglish": [
                "saans lene me takleef", "saans lene me pareshani", "saans phool rahi hai",
                "saans nahi aa rahi", "dam ghut raha hai", "breath nahi le pa raha",
                "breathing difficulty", "breathless ho raha", "saans me dikkat",
                "saas lene me takleef", "saas lene me dikkat", "saas lene me problem",
                "saans lene me problem", "saas phool rahi hai"
            ],
        },
        {
            "category": "neurological_altered",
            "priority": TriageAlertPriority.URGENT,
            "description": "Altered consciousness, syncope, slurred speech, or acute focal weakness detected",
            "keywords_en": [
                "loss of consciousness", "lost consciousness", "fainted", "fainting",
                "passed out", "passing out", "blacked out", "blacking out",
                "unconscious", "fell unconscious", "slurred speech",
                "cannot speak", "unable to speak", "sudden weakness in arm",
                "sudden weakness in leg", "face drooping", "sudden confusion",
                "sudden paralysis"
            ],
            "keywords_hi": [
                "बेहोश हो गया", "बेहोश हो गई", "बेहोशी", "अचेत हो गया",
                "चक्कर खाकर गिर गया", "चक्कर खाकर गिर पड़ी", "बोल नहीं पा रहा",
                "बोल नहीं पा रही", "आवाज लड़खड़ा रही है", "अचानक हाथ में कमजोरी",
                "अचानक पैर में कमजोरी", "अचानक भ्रम", "चेहरा टेढ़ा हो गया"
            ],
            "keywords_hinglish": [
                "behosh ho gaya", "behosh ho gayi", "faint ho gaya", "faint ho gayi",
                "bol nahi pa raha", "bol nahi pa rahi", "slurred speech",
                "chakkar aakar gir gaya", "sudden weakness"
            ],
        },
        {
            "category": "hemorrhage_severe",
            "priority": TriageAlertPriority.URGENT,
            "description": "Active, heavy, or uncontrolled bleeding detected",
            "keywords_en": [
                "heavy bleeding", "uncontrolled bleeding", "bleeding heavily",
                "profuse bleeding", "vomiting blood", "coughing up blood",
                "blood in vomit", "bleeding won't stop", "blood pouring"
            ],
            "keywords_hi": [
                "बहुत ज्यादा खून बह रहा है", "खून बह रहा है", "खून की उल्टी",
                "खांसी में खून", "खून रुक नहीं रहा", "गंभीर रक्तस्राव", "खून गिर रहा है"
            ],
            "keywords_hinglish": [
                "bahut bleeding ho rahi hai", "bleeding ruk nahi rahi",
                "khoon ki ulti", "khoon ruk nahi raha", "khoon beh raha hai"
            ],
        },
        {
            "category": "anaphylaxis_allergy",
            "priority": TriageAlertPriority.URGENT,
            "description": "Signs of acute allergic reaction or airway swelling detected",
            "keywords_en": [
                "throat swelling", "swelling in throat", "swollen throat",
                "swollen lips and tongue", "swelling in face and difficulty breathing",
                "severe allergic reaction", "anaphylaxis"
            ],
            "keywords_hi": [
                "गले में सूजन", "गले में सूजन और सांस लेने में तकलीफ",
                "होठों और जीभ में सूजन", "चेहरे पर सूजन और सांस", "गंभीर एलर्जी"
            ],
            "keywords_hinglish": [
                "gale me sujan", "throat me swelling", "gale me sujan aur saans",
                "severe allergy"
            ],
        },
        {
            "category": "severe_pain_unbearable",
            "priority": TriageAlertPriority.HIGH,
            "description": "Unbearable or 10/10 extreme pain severity reported",
            "keywords_en": [
                "unbearable pain", "excruciating pain", "worst pain of my life",
                "pain is 10/10", "cannot bear the pain", "10 out of 10 pain"
            ],
            "keywords_hi": [
                "असहनीय दर्द", "बर्दाश्त नहीं हो रहा दर्द", "बहुत ज्यादा असहनीय दर्द",
                "जीवन का सबसे बुरा दर्द"
            ],
            "keywords_hinglish": [
                "asahania dard", "pain bardasht nahi ho raha", "unbearable pain hai"
            ],
        },
    ]

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Normalizes text by stripping punctuation, extra spaces, and lowercasing ASCII."""
        if not text:
            return ""
        norm = unicodedata.normalize("NFKC", text)
        norm = norm.lower()
        norm = re.sub(r"[^\w\s\u0900-\u097F]", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm

    @classmethod
    def detect(cls, text: str, language: str = "en") -> TriageDetectionResult:
        """
        Scans normalized patient text against clinical red-flag rules.
        Returns TriageDetectionResult.
        """
        if not text or not text.strip():
            return TriageDetectionResult(has_red_flag=False)

        normalized = cls.normalize_text(text)
        matched_categories = []

        for rule in cls.RULES:
            matched_terms = []
            all_keywords = (
                rule["keywords_en"]
                + rule["keywords_hi"]
                + rule["keywords_hinglish"]
            )
            for kw in all_keywords:
                norm_kw = cls.normalize_text(kw)
                if norm_kw and norm_kw in normalized:
                    matched_terms.append(kw)

            if matched_terms:
                matched_categories.append({
                    "category": rule["category"],
                    "priority": rule["priority"],
                    "description": rule["description"],
                    "matched_keywords": list(set(matched_terms)),
                })

        if not matched_categories:
            return TriageDetectionResult(has_red_flag=False)

        # Pick highest priority match (URGENT over HIGH)
        urgent_matches = [m for m in matched_categories if m["priority"] == TriageAlertPriority.URGENT]
        primary = urgent_matches[0] if urgent_matches else matched_categories[0]

        all_matched_keywords = []
        for m in matched_categories:
            all_matched_keywords.extend(m["matched_keywords"])

        return TriageDetectionResult(
            has_red_flag=True,
            category=primary["category"],
            priority=primary["priority"],
            matched_keywords=list(set(all_matched_keywords)),
            rule_description=primary["description"],
            patient_instruction_en=cls.EMERGENCY_INSTRUCTION_EN,
            patient_instruction_hi=cls.EMERGENCY_INSTRUCTION_HI,
        )


triage_detector = TriageDetector()
