import json
import logging
import re
from typing import List, Optional, Dict, Any
import httpx

from app.config import settings
from app.models.interview import (
    AdaptiveQuestionItem,
    INITIAL_CHIEF_COMPLAINT_QUESTION,
)

logger = logging.getLogger("medikiosk.ai_service")


class ClinicalHeuristicEngine:
    """
    Deterministic clinical case-taking engine implementing standard medical history protocols
    (SOCRATES / OPQRST / Review of Systems). Operates as the robust core and offline fallback,
    ensuring 100% availability even if external LLMs are unreachable or unconfigured.
    """

    @classmethod
    def detect_category(cls, answers: List[dict]) -> str:
        """Analyze the chief complaint to identify the primary clinical category."""
        cc_text = ""
        for a in answers:
            if a.get("question_id") == "chief_complaint":
                cc_text = a.get("patient_answer", "")
                break

        # Fallback to searching the first recorded answer if chief_complaint is missing
        if not cc_text and answers:
            cc_text = answers[0].get("patient_answer", "")

        cc_lower = cc_text.lower()

        # Check category against the presenting complaint
        if any(w in cc_lower for w in ["chest", "heart", "angina", "palpitation", "सीने", "छाती", "दिल"]):
            return "cardiac"
        elif any(w in cc_lower for w in ["headache", "migraine", "head pain", "सिरदर्द", "सिर में दर्द"]):
            return "neurological"
        elif any(w in cc_lower for w in ["knee", "joint", "back pain", "arthritis", "bone", "leg pain", "घुटने", "जोड़", "कमर दर्द"]):
            return "musculoskeletal"
        elif any(w in cc_lower for w in ["cough", "breath", "wheez", "asthma", "phlegm", "खांसी", "सांस"]):
            return "respiratory"
        elif any(w in cc_lower for w in ["stomach", "abdomen", "vomit", "diarrhea", "loose motion", "pet", "पेट", "उल्टी", "दस्त"]):
            return "gastrointestinal"
        elif any(w in cc_lower for w in ["fever", "chills", "temperature", "बुखार", "ठंड"]):
            return "fever"
        else:
            return "general"

    @classmethod
    def get_next_question(
        cls,
        patient_info: dict,
        answers: List[dict],
        language: str = "en",
    ) -> AdaptiveQuestionItem:
        answered_q_ids = {a.get("question_id") for a in answers}
        category = cls.detect_category(answers)

        # -------------------------------------------------------------
        # STAGE 2: History of Present Illness (HPI) - Category Tailored
        # -------------------------------------------------------------
        if "hpi_severity" not in answered_q_ids:
            if category == "cardiac":
                if "hpi_radiation" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_radiation",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Pain Radiation",
                        section_title_hi="दर्द का फैलाव",
                        text_en="Does this chest pain or discomfort spread or radiate to any other part of your body?",
                        text_hi="क्या यह सीने का दर्द आपके शरीर के किसी अन्य हिस्से (जैसे बाएं हाथ, गर्दन, जबड़े या पीठ) में फैलता है?",
                        hint_en="Select where the pain radiates, or choose 'Stays in chest only'.",
                        hint_hi="दर्द कहाँ फैलता है चुनें, या 'केवल सीने में रहता है' चुनें।",
                        options_en=["Spreads to left arm / shoulder", "Spreads to neck / jaw", "Spreads to upper back", "Stays in center of chest only"],
                        options_hi=["बाएं हाथ / कंधे में फैलता है", "गर्दन / जबड़े में फैलता है", "पीठ के ऊपरी हिस्से में फैलता है", "केवल सीने के बीच में रहता है"],
                        input_type="chips",
                    )
                if "hpi_character" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_character",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Character of Pain",
                        section_title_hi="दर्द का प्रकार",
                        text_en="How would you describe the feeling of the chest discomfort?",
                        text_hi="सीने की तकलीफ किस तरह की महसूस होती है?",
                        hint_en="e.g. Squeezing, heavy tightness, sharp stabbing, or burning sensation.",
                        hint_hi="जैसे भारी दबाव, कसाव, चुभन या जलन का अहसास।",
                        options_en=["Tight squeezing / heavy pressure", "Sharp stabbing pain", "Burning sensation / acidity-like", "Dull continuous ache"],
                        options_hi=["भारी दबाव / कसाव जैसा", "तेज चुभन भरा दर्द", "जलन / एसिडिटी जैसा", "हल्का लगातार दर्द"],
                        input_type="chips",
                    )
                if "hpi_aggravating" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_aggravating",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Aggravating Factors",
                        section_title_hi="दर्द बढ़ाने वाले कारक",
                        text_en="What brings on the chest pain or makes it worse?",
                        text_hi="यह दर्द किस स्थिति में बढ़ता है?",
                        hint_en="e.g. Physical exertion like climbing stairs, emotional stress, deep breathing, or eating.",
                        hint_hi="जैसे सीढ़ियां चढ़ने या चलने पर, गहरी सांस लेने पर, या बिना किसी वजह के।",
                        options_en=["Worse with walking / climbing stairs", "Worse when taking a deep breath", "Worse when pressing on chest", "Happens even when resting"],
                        options_hi=["चलने या सीढ़ियां चढ़ने पर बढ़ता है", "गहरी सांस लेने पर बढ़ता है", "सीने को छूने या दबाने पर बढ़ता है", "आराम करते समय भी होता है"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Associated Symptoms",
                        section_title_hi="जुड़े हुए लक्षण",
                        text_en="Are you experiencing any of these associated symptoms with the chest discomfort?",
                        text_hi="क्या सीने में दर्द के साथ इनमें से कोई अन्य लक्षण भी हैं?",
                        hint_en="Select any that apply.",
                        hint_hi="जो लक्षण महसूस हो रहे हों उन्हें चुनें।",
                        options_en=["Shortness of breath", "Cold sweating / diaphoresis", "Dizziness / lightheadedness", "Rapid heart racing / palpitations", "None of these"],
                        options_hi=["सांस फूलना", "ठंडा पसीना आना", "चक्कर आना", "दिल की धड़कन तेज होना", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            elif category == "neurological":
                if "hpi_character" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_character",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Headache Nature",
                        section_title_hi="सिरदर्द की प्रकृति",
                        text_en="How would you describe the sensation of the headache?",
                        text_hi="सिरदर्द किस प्रकार का महसूस होता है?",
                        hint_en="e.g. Pulsating/throbbing, tight band around forehead, or sharp stabbing.",
                        hint_hi="जैसे धड़कता हुआ (पल्सिंग), सिर पर कसाव जैसा, या चुभने वाला दर्द।",
                        options_en=["Throbbing / pulsating", "Tight pressing band around head", "Sharp stabbing pain", "Dull heavy ache"],
                        options_hi=["धड़कता हुआ (पल्सिंग)", "सिर पर कसाव / पट्टी जैसा", "तेज चुभने वाला दर्द", "भारीपन और लगातार दर्द"],
                        input_type="chips",
                    )
                if "hpi_location" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_location",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Headache Location",
                        section_title_hi="सिरदर्द का स्थान",
                        text_en="Where is the headache mostly concentrated?",
                        text_hi="सिरदर्द मुख्यतः सिर के किस हिस्से में है?",
                        options_en=["One side of the head only", "Forehead and temples", "Back of the head and neck", "Entire head"],
                        options_hi=["केवल सिर के एक तरफ (आधा सिर)", "माथा और कनपटी", "सिर का पिछला हिस्सा और गर्दन", "पूरे सिर में"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Associated Symptoms",
                        section_title_hi="जुड़े हुए लक्षण",
                        text_en="Do you experience any nausea, light sensitivity, or visual changes with the headache?",
                        text_hi="क्या सिरदर्द के साथ उल्टी का मन, तेज रोशनी/आवाज से परेशानी, या आंखों के आगे चमक महसूस होती है?",
                        options_en=["Nausea or vomiting", "Light / sound sensitivity", "Visual disturbances / aura", "Neck stiffness", "None of these"],
                        options_hi=["उल्टी या जी मिचलाना", "रोशनी या तेज आवाज से परेशानी", "आंखों के आगे चमक या धुंधलापन", "गर्दन में अकड़न", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            elif category == "musculoskeletal":
                if "hpi_location" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_location",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Joint Affected",
                        section_title_hi="प्रभावित जोड़ / अंग",
                        text_en="Which specific joint or area is affected?",
                        text_hi="शरीर का कौन सा जोड़ या हिस्सा मुख्य रूप से प्रभावित है?",
                        options_en=["Right knee", "Left knee", "Both knees", "Lower back", "Shoulder", "Hip or ankle"],
                        options_hi=["दायां घुटना", "बायां घुटना", "दोनों घुटने", "कमर का निचला हिस्सा", "कंधा", "कूल्हा या टखना"],
                        input_type="chips",
                    )
                if "hpi_weight_bearing" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_weight_bearing",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Mobility & Weight Bearing",
                        section_title_hi="चलने-फिरने की क्षमता",
                        text_en="Are you able to walk and put weight on the affected joint?",
                        text_hi="क्या आप इस जोड़ पर वजन रखकर सामान्य रूप से चल पा रहे हैं?",
                        options_en=["Can walk with mild pain", "Walking with significant limp", "Unable to put weight / need support", "Bed rest required"],
                        options_hi=["हल्के दर्द के साथ चल पा रहे हैं", "लंगड़ा कर चल रहे हैं", "वजन बिल्कुल नहीं रख पा रहे / सहारे की जरूरत", "बिस्तर पर आराम जरूरी है"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Joint Signs",
                        section_title_hi="जोड़ों के लक्षण",
                        text_en="Have you noticed visible swelling, joint locking, or morning stiffness?",
                        text_hi="क्या जोड़ में सूजन, सुबह उठने पर अकड़न, या जोड़ का लॉक होना महसूस हुआ है?",
                        options_en=["Visible swelling", "Morning stiffness lasting > 30 mins", "Joint clicking / locking sensation", "Warmth and redness", "None of these"],
                        options_hi=["दिखने वाली सूजन", "सुबह 30 मिनट से अधिक अकड़न", "जोड़ में कट-कट या लॉक होना", "गर्मी और लालिमा", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            elif category == "respiratory":
                if "hpi_character" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_character",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Cough & Breathing Quality",
                        section_title_hi="खांसी और सांस की प्रकृति",
                        text_en="Is your cough dry or producing sputum/phlegm?",
                        text_hi="क्या आपकी खांसी सूखी है या बलगम आ रहा है?",
                        options_en=["Dry hacking cough", "Productive with clear/white phlegm", "Yellow or green thick phlegm", "Blood-tinged phlegm"],
                        options_hi=["सूखी खांसी", "सफेद / साफ बलगम", "पीला या हरा गाढ़ा बलगम", "खून की हल्की झलक"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Associated Respiratory Symptoms",
                        section_title_hi="जुड़े हुए श्वसन लक्षण",
                        text_en="Do you have shortness of breath, wheezing, or chest tightness?",
                        text_hi="क्या सांस फूलने, सीने में घरघराहट (wheezing), या जकड़न की समस्या है?",
                        options_en=["Shortness of breath on mild exertion", "Audible wheezing sounds", "Chest tightness", "High fever with chills", "None of these"],
                        options_hi=["थोड़ा चलने पर सांस फूलना", "सांस लेते समय सीटी जैसी आवाज", "सीने में जकड़न", "तेज बुखार और ठंड", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            elif category == "gastrointestinal":
                if "hpi_location" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_location",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Abdominal Pain Location",
                        section_title_hi="पेट दर्द का स्थान",
                        text_en="Where in your stomach or abdomen is the discomfort concentrated?",
                        text_hi="पेट के किस हिस्से में सबसे अधिक दर्द या तकलीफ है?",
                        options_en=["Upper center (epigastric / pit of stomach)", "Right upper side (under ribs)", "Right lower abdomen", "Lower belly / generalized"],
                        options_hi=["पेट के ऊपरी बीच के हिस्से में", "दाईं तरफ पसलियों के नीचे", "पेट के निचले दाएं हिस्से में", "पेट के निचले हिस्से में / पूरे पेट में"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Associated Digestive Symptoms",
                        section_title_hi="पाचन संबंधी लक्षण",
                        text_en="Are you experiencing vomiting, loose stools, or difficulty eating?",
                        text_hi="क्या आपको उल्टी, दस्त, या खाने में परेशानी हो रही है?",
                        options_en=["Vomiting or nausea", "Loose motions / diarrhea", "Constipation / no bowel movement", "Acidity / severe burning", "None of these"],
                        options_hi=["उल्टी या जी मिचलाना", "पतले दस्त", "कब्ज / पेट साफ न होना", "एसिडिटी / तेज जलन", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            elif category == "fever":
                if "hpi_pattern" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_pattern",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Fever Pattern & Duration",
                        section_title_hi="बुखार का प्रकार व अवधि",
                        text_en="How long have you had fever, and does it come with chills or shivering?",
                        text_hi="बुखार कितने दिनों से है, और क्या इसके साथ ठंड लगकर कंपकंपी होती है?",
                        hint_en="Select the fever duration and pattern.",
                        hint_hi="बुखार की अवधि और प्रकार चुनें।",
                        options_en=["1-2 days with shivering chills", "3-5 days intermittent spikes", "Continuous high fever", "Low grade mild fever > 1 week"],
                        options_hi=["1-2 दिन से ठंड लगकर कंपकंपी के साथ", "3-5 दिन से रुक-रुक कर तेज बुखार", "लगातार तेज बुखार बना हुआ है", "एक हफ्ते से अधिक समय से हल्का बुखार"],
                        input_type="chips",
                    )
                if "hpi_associated" not in answered_q_ids:
                    return AdaptiveQuestionItem(
                        question_id="hpi_associated",
                        section="hpi",
                        stage_number=2,
                        stage_title_en="Stage 2: Symptom Exploration (HPI)",
                        stage_title_hi="चरण 2: लक्षणों का विवरण",
                        section_title_en="Associated Fever Symptoms",
                        section_title_hi="बुखार से जुड़े लक्षण",
                        text_en="Do you have any associated symptoms like severe body aches, rash, or burning urination?",
                        text_hi="क्या बुखार के साथ बदन दर्द, त्वचा पर लाल चकत्ते या पेशाब में जलन जैसे कोई अन्य लक्षण हैं?",
                        options_en=["Severe body aches & headache", "Burning urination (dysuria)", "Cough & throat pain", "Nausea or vomiting", "None of these"],
                        options_hi=["तेज बदन दर्द और सिरदर्द", "पेशाब में जलन", "खांसी और गले में खराश", "जी मिचलाना या उल्टी", "इनमें से कोई नहीं"],
                        input_type="chips",
                    )

            # Common HPI question across all categories: Severity rating
            return AdaptiveQuestionItem(
                question_id="hpi_severity",
                section="hpi",
                stage_number=2,
                stage_title_en="Stage 2: Symptom Exploration (HPI)",
                stage_title_hi="चरण 2: लक्षणों का विवरण",
                section_title_en="Severity Rating",
                section_title_hi="गंभीरता का स्तर",
                text_en="On a scale of 1 to 10, how severe is your discomfort right now (1 = very mild, 10 = worst imaginable)?",
                text_hi="1 से 10 के पैमाने पर, आपकी तकलीफ कितनी गंभीर है (1 = बहुत हल्की, 10 = असहनीय दर्द)?",
                hint_en="Select the number that best reflects your pain level.",
                hint_hi="अपने दर्द के स्तर के अनुसार संख्या चुनें।",
                options_en=["1 - Very Mild", "2", "3 - Mild", "4", "5 - Moderate", "6", "7 - Severe", "8", "9", "10 - Unbearable"],
                options_hi=["1 - बहुत हल्का", "2", "3 - हल्का", "4", "5 - मध्यम", "6", "7 - गंभीर", "8", "9", "10 - असहनीय"],
                input_type="scale",
            )

        # -------------------------------------------------------------
        # STAGE 3: Past Medical & Surgical History (PMH)
        # -------------------------------------------------------------
        if "pmh_conditions" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="pmh_conditions",
                section="past_medical",
                stage_number=3,
                stage_title_en="Stage 3: Past Medical History",
                stage_title_hi="चरण 3: पुरानी बीमारियां",
                section_title_en="Chronic Medical Conditions",
                section_title_hi="पुरानी बीमारियां",
                text_en="Do you have any long-standing diagnosed medical conditions?",
                text_hi="क्या आपको इनमें से कोई पुरानी या पहले से ज्ञात बीमारी है?",
                hint_en="Select any known conditions (BP, Diabetes, Heart condition, Asthma, etc.).",
                hint_hi="यदि कोई बीमारी हो तो चुनें (बीपी, शुगर, दिल की बीमारी, दमा आदि)।",
                options_en=["High Blood Pressure (Hypertension)", "Diabetes (Sugar)", "Heart disease / Prior heart attack", "Asthma / Bronchitis", "Thyroid disorder", "No known medical conditions"],
                options_hi=["हाई ब्लड प्रेशर (बीपी)", "डायबिटीज (शुगर)", "दिल की बीमारी / पहले दिल का दौरा", "अस्थमा / दमा", "थायराइड", "कोई पुरानी बीमारी नहीं"],
                input_type="chips",
            )

        if "pmh_surgeries" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="pmh_surgeries",
                section="past_surgical",
                stage_number=3,
                stage_title_en="Stage 3: Past Medical History",
                stage_title_hi="चरण 3: पुरानी बीमारियां",
                section_title_en="Past Surgeries & Hospitalizations",
                section_title_hi="पूर्व सर्जरी व अस्पताल भर्ती",
                text_en="Have you ever had any surgery or been admitted to a hospital in the past?",
                text_hi="क्या आपकी पहले कभी कोई सर्जरी (ऑपरेशन) हुई है या आप अस्पताल में भर्ती हुए हैं?",
                hint_en="Mention the type of surgery or reason for admission, or select 'No prior surgeries'.",
                hint_hi="यदि ऑपरेशन हुआ हो तो संक्षेप में बताएं, या 'कोई सर्जरी नहीं' चुनें।",
                options_en=["No prior surgeries or hospital admissions", "Stent / Angioplasty", "Abdominal surgery (Appendix/Gallbladder/Hernia)", "Joint replacement / Bone surgery", "Cesarean delivery (C-section)"],
                options_hi=["कोई सर्जरी या अस्पताल भर्ती नहीं", "स्टेंट / एंजियोप्लास्टी", "पेट का ऑपरेशन (अपेंडिक्स/पित्त/हर्निया)", "जोड़ या हड्डी का ऑपरेशन", "सिजेरियन डिलीवरी"],
                input_type="text",
            )

        # -------------------------------------------------------------
        # STAGE 4: Medications & Allergies
        # -------------------------------------------------------------
        if "medications_current" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="medications_current",
                section="medications",
                stage_number=4,
                stage_title_en="Stage 4: Medications & Allergies",
                stage_title_hi="चरण 4: दवाइयां और एलर्जी",
                section_title_en="Current Medications",
                section_title_hi="वर्तमान दवाइयां",
                text_en="What regular medications or prescription tablets are you currently taking?",
                text_hi="वर्तमान में आप नियमित रूप से कौन सी दवाइयां या गोलियां ले रहे हैं?",
                hint_en="Include daily BP/Sugar tablets, blood thinners, inhalers, or pain relievers.",
                hint_hi="दैनिक बीपी/शुगर की दवाइयां, खून पतला करने की दवा, या इनहेलर शामिल करें।",
                options_en=["Not taking any regular medications", "Blood pressure tablets", "Diabetes tablets / Insulin", "Blood thinner (Aspirin/Clopidogrel)", "Inhaler for breathing"],
                options_hi=["कोई नियमित दवा नहीं ले रहे", "ब्लड प्रेशर की दवा", "शुगर की दवा / इंसुलिन", "खून पतला करने की दवा", "सांस का इनहेलर"],
                input_type="text",
            )

        if "allergies_known" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="allergies_known",
                section="allergies",
                stage_number=4,
                stage_title_en="Stage 4: Medications & Allergies",
                stage_title_hi="चरण 4: दवाइयां और एलर्जी",
                section_title_en="Drug & Food Allergies",
                section_title_hi="दवा और भोजन एलर्जी",
                text_en="Do you have any known allergies to medicines, injections, or food?",
                text_hi="क्या आपको किसी दवा, इंजेक्शन या खाद्य पदार्थ से कोई एलर्जी है?",
                hint_en="This is critical for physician prescription safety.",
                hint_hi="डॉक्टर द्वारा सही दवा लिखने के लिए यह बहुत महत्वपूर्ण है।",
                options_en=["No known drug or food allergies", "Allergic to Penicillin / Antibiotics", "Allergic to Sulfa medicines", "Allergic to Painkillers (NSAIDs)", "Food allergies"],
                options_hi=["कोई ज्ञात दवा या भोजन एलर्जी नहीं", "पेनिसिलिन / एंटीबायोटिक से एलर्जी", "सल्फा दवाओं से एलर्जी", "दर्द निवारक दवाओं से एलर्जी", "भोजन से एलर्जी"],
                input_type="chips",
            )

        # -------------------------------------------------------------
        # STAGE 5: Family History & Social / Lifestyle
        # -------------------------------------------------------------
        if "family_history" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="family_history",
                section="family_history",
                stage_number=5,
                stage_title_en="Stage 5: Family & Lifestyle",
                stage_title_hi="चरण 5: पारिवारिक व जीवनशैली इतिहास",
                section_title_en="Family Medical History",
                section_title_hi="पारिवारिक स्वास्थ्य इतिहास",
                text_en="Does anyone in your immediate family (parents, siblings) have serious health conditions?",
                text_hi="क्या आपके परिवार (माता-पिता, भाई-बहन) में किसी को गंभीर स्वास्थ्य समस्या रही है?",
                hint_en="e.g. Early heart attack, diabetes, high blood pressure, stroke, or cancer.",
                hint_hi="जैसे कम उम्र में दिल का दौरा, शुगर, हाई बीपी या लकवा।",
                options_en=["Heart disease / Early heart attack", "Diabetes running in family", "High blood pressure", "No major family medical issues"],
                options_hi=["परिवार में दिल की बीमारी", "परिवार में शुगर की बीमारी", "हाई ब्लड प्रेशर", "परिवार में कोई गंभीर बीमारी नहीं"],
                input_type="chips",
            )

        if "social_habits" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="social_habits",
                section="social_history",
                stage_number=5,
                stage_title_en="Stage 5: Family & Lifestyle",
                stage_title_hi="चरण 5: पारिवारिक व जीवनशैली इतिहास",
                section_title_en="Lifestyle & Habits",
                section_title_hi="जीवनशैली और आदतें",
                text_en="Do you smoke, chew tobacco, or consume alcohol?",
                text_hi="क्या आप बीड़ी/सिगरेट पीते हैं, तंबाकू/गुटखा चबाते हैं, या शराब का सेवन करते हैं?",
                hint_en="This information is confidential and used solely for your medical care.",
                hint_hi="यह जानकारी पूरी तरह गोपनीय है और केवल आपके इलाज में मदद के लिए है।",
                options_en=["Do not smoke or chew tobacco, no alcohol", "Cigarette / Bidi smoker", "Chew tobacco / Gutkha", "Occasional alcohol", "Daily alcohol consumption"],
                options_hi=["न धूम्रपान, न तंबाकू, न शराब", "बीड़ी / सिगरेट पीते हैं", "तंबाकू / गुटखा चबाते हैं", "कभी-कभार शराब", "नियमित शराब सेवन"],
                input_type="chips",
            )

        # -------------------------------------------------------------
        # STAGE 6: Review of Systems (ROS) & Conclusion
        # -------------------------------------------------------------
        if "ros_systemic" not in answered_q_ids:
            return AdaptiveQuestionItem(
                question_id="ros_systemic",
                section="review_of_systems",
                stage_number=6,
                stage_title_en="Stage 6: System Review & Wrap-up",
                stage_title_hi="चरण 6: संपूर्ण समीक्षा और समापन",
                section_title_en="Systemic Health Check",
                section_title_hi="सामान्य स्वास्थ्य जांच",
                text_en="Have you experienced any unexplained weight loss, night sweats, or extreme weakness recently?",
                text_hi="क्या हाल ही में बिना कारण वजन कम होना, रात में पसीना आना या अत्यधिक कमजोरी महसूस हुई है?",
                hint_en="Select any that apply, or 'None of these'.",
                hint_hi="यदि कोई लक्षण हो तो चुनें, या 'इनमें से कोई नहीं' चुनें।",
                options_en=["Unexplained weight loss", "Night sweats with mild fever", "Extreme fatigue / weakness", "None of these"],
                options_hi=["बिना कारण वजन कम होना", "रात में पसीना और हल्का बुखार", "अत्यधिक थकान व कमजोरी", "इनमें से कोई नहीं"],
                input_type="chips",
            )

        # If all sections have been addressed -> Terminal completion
        return AdaptiveQuestionItem(
            question_id="interview_conclusion",
            section="conclusion",
            stage_number=6,
            stage_title_en="Intake Complete",
            stage_title_hi="इंटरव्यू पूरा हुआ",
            section_title_en="Clinical History Intake Complete",
            section_title_hi="क्लिनिकल हिस्ट्री पूरी हुई",
            text_en="Thank you. All essential clinical history has been successfully collected for your OPD doctor's review.",
            text_hi="धन्यवाद। आपके ओपीडी डॉक्टर की समीक्षा के लिए सभी आवश्यक क्लिनिकल जानकारी सफलतापूर्वक दर्ज कर ली गई है।",
            hint_en="Please proceed to the OPD waiting area. Your token number will be called.",
            hint_hi="कृपया ओपीडी प्रतीक्षालय में बैठें। आपका टोकन नंबर पुकारा जाएगा।",
            options_en=["Complete & Submit to Doctor"],
            options_hi=["पूरा करें और डॉक्टर को भेजें"],
            input_type="chips",
            is_terminal=True,
        )


class AIService:
    """
    Modular AI service layer coordinating adaptive questioning for MediKiosk.
    Uses configured LLM (e.g. Gemini 1.5) with strict non-diagnostic prompting,
    and seamlessly falls back to ClinicalHeuristicEngine upon any API unavailability.
    """

    def __init__(self):
        self.api_key = settings.AI_API_KEY
        self.model = settings.AI_MODEL
        self.provider = settings.AI_PROVIDER
        self.timeout = settings.AI_TIMEOUT_SECONDS

    def get_initial_question(self, language: str = "en", history_mode: str = "general") -> AdaptiveQuestionItem:
        """Returns standard initial Chief Complaint question for General or AYUSH mode."""
        if history_mode == "ayush":
            from app.services.ayush_service import ayush_service
            return ayush_service.get_initial_question(language)
        return INITIAL_CHIEF_COMPLAINT_QUESTION

    async def generate_next_question(
        self,
        patient_info: dict,
        answers: List[dict],
        language: str = "en",
        history_mode: str = "general",
    ) -> AdaptiveQuestionItem:
        """
        Determines the next adaptive clinical question based on conversation history.
        Routes to ayush_service if history_mode is 'ayush'.
        Tries external LLM provider if configured; falls back safely to ClinicalHeuristicEngine.
        """
        if history_mode == "ayush":
            from app.services.ayush_service import ayush_service
            return ayush_service.get_next_question(patient_info, answers, language)

        if not self.api_key or self.provider == "heuristic":
            return ClinicalHeuristicEngine.get_next_question(patient_info, answers, language)

        try:
            llm_question = await self._call_llm_for_question(patient_info, answers, language)
            if llm_question:
                return llm_question
        except Exception as e:
            logger.warning(f"External AI question generation failed ({e}). Falling back seamlessly to ClinicalHeuristicEngine.")

        return ClinicalHeuristicEngine.get_next_question(patient_info, answers, language)

    async def _call_llm_for_question(
        self,
        patient_info: dict,
        answers: List[dict],
        language: str = "en",
    ) -> Optional[AdaptiveQuestionItem]:
        """Calls Google Gemini API using structured JSON output."""
        system_prompt = (
            "You are the MediKiosk AI Clinical Case-Taking Assistant for an Indian Hospital OPD. "
            "Your sole function is to take an organized, thorough clinical history for the doctor. "
            "CRITICAL SAFETY INVARIANTS:\n"
            "1. NEVER give a medical diagnosis or speculate what disease the patient has.\n"
            "2. NEVER prescribe or suggest medications, home remedies, or therapies.\n"
            "3. NEVER invent symptoms or assume patient answers.\n"
            "4. Formulate one single, patient-friendly follow-up question based on the patient's actual previous answers.\n"
            "5. If sufficient history has been collected across HPI, Past Medical, Medications, Allergies, Family and Lifestyle (10+ answers), set is_terminal: true.\n"
            "6. Output MUST strictly be valid JSON matching this schema:\n"
            "{\n"
            '  "question_id": "string",\n'
            '  "section": "hpi|past_medical|medications|allergies|family_history|social_history|review_of_systems|conclusion",\n'
            '  "stage_number": 1-6,\n'
            '  "stage_title_en": "string",\n'
            '  "stage_title_hi": "string",\n'
            '  "section_title_en": "string",\n'
            '  "section_title_hi": "string",\n'
            '  "text_en": "string",\n'
            '  "text_hi": "string",\n'
            '  "hint_en": "string",\n'
            '  "hint_hi": "string",\n'
            '  "options_en": ["option1", "option2", ...],\n'
            '  "options_hi": ["विकल्प1", "विकल्प2", ...],\n'
            '  "input_type": "chips|scale|text",\n'
            '  "is_terminal": false\n'
            "}"
        )

        history_summary = []
        for a in answers:
            history_summary.append({
                "question": a.get("question_text"),
                "answer": a.get("patient_answer"),
                "section": a.get("section"),
            })

        user_prompt = (
            f"Patient Demographic: Age {patient_info.get('age')}, Gender {patient_info.get('gender')}.\n"
            f"Language Preference: {language}.\n"
            f"Recorded History So Far ({len(answers)} answers):\n"
            f"{json.dumps(history_summary, ensure_ascii=False, indent=2)}\n\n"
            "Generate the next clinically appropriate follow-up question."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_prompt + "\n\n" + user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                result = resp.json()
                candidate_text = result["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(candidate_text)
                return AdaptiveQuestionItem(**data)
            else:
                logger.warning(f"LLM API returned status {resp.status_code}: {resp.text}")
                return None


ai_service = AIService()
