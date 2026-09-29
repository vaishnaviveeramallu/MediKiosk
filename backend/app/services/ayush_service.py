import logging
from typing import List, Optional, Dict, Any

from app.models.interview import AdaptiveQuestionItem
from app.models.ayush import AYUSHClinicalData, DashavidhaPariksha

logger = logging.getLogger("medikiosk.ayush_service")

# Initial AYUSH Chief Complaint Question
INITIAL_AYUSH_QUESTION = AdaptiveQuestionItem(
    question_id="ayush_chief_complaint",
    section="chief_complaint",
    stage_number=1,
    stage_title_en="Stage 1: AYUSH Chief Complaint",
    stage_title_hi="चरण 1: आयुष मुख्य समस्या",
    section_title_en="Holistic Intake & Chief Complaint",
    section_title_hi="समग्र स्वास्थ्य व मुख्य समस्या",
    text_en="What is your primary health concern or symptom bringing you to the AYUSH consultation today?",
    text_hi="आज आयुष परामर्श के लिए आने का आपका मुख्य स्वास्थ्य कारण या लक्षण क्या है?",
    hint_en="Please describe your main health issue in your own words (e.g., digestive sluggishness, joint stiffness, sleep disturbance).",
    hint_hi="कृपया अपनी मुख्य परेशानी अपने शब्दों में बताएं (जैसे पाचन की कमजोरी, जोड़ों में जकड़न, नींद की परेशानी)।",
    options_en=[
        "Digestive issues / Acidity / Gas",
        "Joint or body stiffness / Pain",
        "Sleep disturbance / Stress / Fatigue",
        "General weakness / Low stamina",
        "Skin condition / Allergy",
        "Chronic cold / Cough / Respiratory",
        "I don't know / General checkup",
    ],
    options_hi=[
        "पाचन की समस्या / एसिडिटी / गैस",
        "जोड़ों या शरीर में दर्द व जकड़न",
        "नींद न आना / तनाव / थकान",
        "सामान्य कमजोरी / कम ऊर्जा",
        "त्वचा संबंधी परेशानी / एलर्जी",
        "पुरानी सर्दी / खांसी / सांस की समस्या",
        "पता नहीं / सामान्य जांच",
    ],
    input_type="chips",
    is_terminal=False,
)


class AYUSHService:
    """
    Structured adaptive history-taking service for AYUSH (Ayurveda, Yoga, Unani, Siddha, Homeopathy).
    Collects comprehensive patient-reported parameters:
    Agni, Koshta, Bala, Satmya, Ahara, Vihara, Nidra, Mala, Mutra, Manasika, and Dashavidha Pariksha.

    CRITICAL SAFETY INVARIANT:
    Strictly non-diagnostic. Never auto-diagnoses Prakriti or disease.
    Every question includes 'I don't know' / 'Prefer not to answer' options.
    """

    def get_initial_question(self, language: str = "en") -> AdaptiveQuestionItem:
        """Returns standard initial AYUSH chief complaint question."""
        return INITIAL_AYUSH_QUESTION

    def has_digestive_complaint(self, answers: List[dict]) -> bool:
        """Check if patient reported any digestive or abdominal complaint."""
        for a in answers:
            ans_text = (a.get("patient_answer") or "").lower()
            if any(w in ans_text for w in [
                "digest", "acid", "gas", "bloat", "stomach", "pet", "constipat",
                "loose", "bowel", "अपच", "गैस", "एसिडिटी", "पेट", "कब्ज", "दस्त"
            ]):
                return True
        return False

    def get_next_question(
        self,
        patient_info: dict,
        answers: List[dict],
        language: str = "en",
    ) -> AdaptiveQuestionItem:
        """
        Adaptively decides the next AYUSH clinical question based on collected answers.
        Explores Agni, Koshta, Ahara, Vihara, Nidra, Manasika, and Dashavidha Pariksha parameters.
        """
        answered_ids = {a.get("question_id") for a in answers}
        has_digestion_issue = self.has_digestive_complaint(answers)

        # 1. Agni (Digestive / Metabolic Fire)
        if "ayush_agni" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_agni",
                section="agni",
                stage_number=2,
                stage_title_en="Stage 2: Agni & Metabolism",
                stage_title_hi="चरण 2: अग्नि एवं पाचन शक्ति",
                section_title_en="Digestive Fire (Agni)",
                section_title_hi="पाचन अग्नि",
                text_en="How is your natural appetite and digestion pattern (Agni)?",
                text_hi="आपकी स्वाभाविक भूख और पाचन शक्ति (अग्नि) कैसी रहती है?",
                hint_en="Agni refers to your digestive power: Sama (balanced), Tikshna (excessive/quick), Manda (slow), or Vishama (irregular).",
                hint_hi="अग्नि का अर्थ है पाचन शक्ति: सम (संतुलित), तीक्ष्ण (तेज भूख), मंद (धीमी भूख), या विषम (अनियमित)।",
                options_en=[
                    "Normal & timely appetite (Sama Agni)",
                    "Strong appetite / gets hungry very quickly (Tikshna Agni)",
                    "Low appetite / food feels heavy for hours (Manda Agni)",
                    "Irregular / hungry some days, not on others (Vishama Agni)",
                    "I don't know / Not sure",
                ],
                options_hi=[
                    "सामान्य व समय पर भूख लगना (सम अग्नि)",
                    "बहुत तेज भूख / जल्दी भूख लगना (तीक्ष्ण अग्नि)",
                    "कम भूख / खाना घंटों भारी लगना (मंद अग्नि)",
                    "अनियमित / कभी तेज कभी बिल्कुल नहीं (विषम अग्नि)",
                    "पता नहीं / निश्चित नहीं",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 2. Koshta (Bowel Habit Nature) - prioritize if patient reported digestive issues
        if "ayush_koshta" not in answered_ids and has_digestion_issue:
            return AdaptiveQuestionItem(
                question_id="ayush_koshta",
                section="koshta",
                stage_number=2,
                stage_title_en="Stage 2: Koshta & Elimination",
                stage_title_hi="चरण 2: कोष्ठ एवं मल विसर्जन",
                section_title_en="Bowel Nature (Koshta)",
                section_title_hi="कोष्ठ प्रकृति",
                text_en="How would you describe your bowel movements and evacuation (Koshta)?",
                text_hi="आपके मल त्याग की प्रकृति (कोष्ठ) कैसी रहती है?",
                hint_en="Koshta indicates bowel tendency: Mridu (easy/soft), Madhyama (normal), Krura (hard/constipated).",
                hint_hi="कोष्ठ का अर्थ: मृदु (सरल/ढीला), मध्यम (सामान्य), क्रूर (कड़ा/कब्जियत)।",
                options_en=[
                    "Soft / easy motion / sensitive to milk (Mridu Koshta)",
                    "Normal / once or twice daily without effort (Madhyama Koshta)",
                    "Hard stools / prone to constipation / needs straining (Krura Koshta)",
                    "Irregular with gas or bloating",
                    "I don't know / Prefer not to answer",
                ],
                options_hi=[
                    "सरल मल विसर्जन / दूध से भी पेट साफ (मृदु कोष्ठ)",
                    "सामान्य / दिन में एक या दो बार बिना परेशानी (मध्यम कोष्ठ)",
                    "कड़ा मल / कब्ज की प्रवृत्ति (क्रूर कोष्ठ)",
                    "अनियमित / पेट में गैस या भारीपन के साथ",
                    "पता नहीं / उत्तर नहीं देना चाहते",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 3. Ahara (Dietary Habits & Food Preferences)
        if "ayush_ahara" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_ahara",
                section="ahara",
                stage_number=2,
                stage_title_en="Stage 2: Dietary Habits (Ahara)",
                stage_title_hi="चरण 2: आहार एवं खानपान",
                section_title_en="Food Routine & Preferences",
                section_title_hi="खानपान की आदतें",
                text_en="What are your general food preferences and eating habits (Ahara)?",
                text_hi="आपकी सामान्य खानपान की आदतें और पसंद (आहार) क्या हैं?",
                hint_en="e.g., Warm freshly cooked food, spicy or sour tastes, sweet tastes, or frequent snacking.",
                hint_hi="जैसे ताजा गर्म भोजन पसंद, तीखा/खट्टा पसंद, मीठा पसंद, या समय पर भोजन।",
                options_en=[
                    "Prefer freshly cooked warm meals on fixed schedule",
                    "Prone to irregular meal timings and outside food",
                    "Prefer light vegetarian diet",
                    "Prefer spicy, oily, or sour foods",
                    "Regular non-vegetarian intake",
                    "I don't know / Mixed",
                ],
                options_hi=[
                    "निश्चित समय पर ताजा गर्म घर का खाना",
                    "अनियमित समय पर भोजन व बाहर का खाना",
                    "हल्का शाकाहारी भोजन पसंद",
                    "तीखा, तला-भुना या खट्टा भोजन पसंद",
                    "नियमित मांसाहार सेवन",
                    "पता नहीं / मिलाजुला",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 4. Nidra (Sleep Quality & Pattern)
        if "ayush_nidra" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_nidra",
                section="nidra",
                stage_number=3,
                stage_title_en="Stage 3: Sleep & Regimen (Nidra & Vihara)",
                stage_title_hi="चरण 3: निद्रा एवं दिनचर्या",
                section_title_en="Sleep Pattern (Nidra)",
                section_title_hi="नींद की स्थिति",
                text_en="How is your daily sleep quality and duration (Nidra)?",
                text_hi="आपकी दैनिक नींद की गुणवत्ता और समय (निद्रा) कैसा रहता है?",
                hint_en="Nidra is one of the three pillars of health (Trayopastambha) in AYUSH.",
                hint_hi="आयुष में निद्रा स्वास्थ्य के तीन मुख्य आधार स्तंभों में से एक है।",
                options_en=[
                    "Sound, refreshing sleep for 6-8 hours",
                    "Light sleep / wake up frequently at night",
                    "Difficulty falling asleep / racing thoughts",
                    "Excessive sleepiness during daytime (Divasvapna)",
                    "Wake up feeling unrefreshed or tired",
                    "I don't know / Not sure",
                ],
                options_hi=[
                    "गहरी और ताजगी भरी नींद (6-8 घंटे)",
                    "हल्की नींद / रात में बार-बार आंख खुलना",
                    "देर से नींद आना / विचारों का चलना",
                    "दिन में बहुत अधिक सुस्ती या नींद आना",
                    "उठने पर थकान या भारीपन लगना",
                    "पता नहीं / निश्चित नहीं",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 5. Vihara & Vyayama Shakti (Daily Activity & Physical Endurance)
        if "ayush_vihara" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_vihara",
                section="vihara",
                stage_number=3,
                stage_title_en="Stage 3: Daily Regimen & Stamina",
                stage_title_hi="चरण 3: दिनचर्या एवं शारीरिक शक्ति",
                section_title_en="Physical Activity (Vyayama Shakti)",
                section_title_hi="शारीरिक व्यायाम व श्रम क्षमता",
                text_en="How much physical activity or exercise do you do, and how is your stamina (Vyayama Shakti)?",
                text_hi="आपकी शारीरिक गतिविधि व श्रम सहने की क्षमता (व्यायाम शक्ति) कैसी है?",
                hint_en="Vyayama Shakti is the 9th parameter of Dashavidha Pariksha.",
                hint_hi="व्यायाम शक्ति दशविध परीक्षा का 9वां प्रमुख अंग है।",
                options_en=[
                    "Good stamina — can walk or exercise vigorously without exhaustion (Pravara)",
                    "Moderate stamina — comfortable with routine daily tasks (Madhyama)",
                    "Low stamina — get tired or breathless quickly with mild effort (Avara)",
                    "Mostly sedentary lifestyle / very little walking",
                    "I don't know / Not sure",
                ],
                options_hi=[
                    "अच्छी शक्ति — बिना थके काफी चल या व्यायाम कर सकते हैं (प्रवर)",
                    "मध्यम शक्ति — रोजमर्रा के काम आसानी से कर लेते हैं (मध्यम)",
                    "कम शक्ति — थोड़े से श्रम से जल्दी थकान या सांस फूलना (अवर)",
                    "अधिकतर बैठे रहने वाली दिनचर्या",
                    "पता नहीं / निश्चित नहीं",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 6. Manasika & Satva (Mental Stamina & Emotional State)
        if "ayush_manasika" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_manasika",
                section="manasika",
                stage_number=4,
                stage_title_en="Stage 4: Mental Disposition (Satva)",
                stage_title_hi="चरण 4: मानसिक स्थिति एवं सत्व",
                section_title_en="Mental Stamina (Satva)",
                section_title_hi="मनोबल एवं मानसिक स्वभाव",
                text_en="How would you describe your mental resilience, stress tolerance, and temperament (Satva)?",
                text_hi="आपका मानसिक स्वभाव, तनाव सहने की क्षमता और मनोबल (सत्व) कैसा है?",
                hint_en="Satva reflects psychological strength: Pravara (strong/calm), Madhyama (moderate), Avara (sensitive/anxious).",
                hint_hi="सत्व का अर्थ मानसिक बल: प्रवर (स्थिर व शांत), मध्यम (सामान्य), अवर (जल्दी घबराने वाला)।",
                options_en=[
                    "Calm, steady, handles challenges with composure (Pravara Satva)",
                    "Moderate — occasional worry but manageable (Madhyama Satva)",
                    "Prone to frequent anxiety, fearfulness, or low mood (Avara Satva)",
                    "Prone to quick irritability or anger",
                    "I don't know / Prefer not to answer",
                ],
                options_hi=[
                    "शांत, धैर्यवान, कठिनाई में स्थिर रहने वाले (प्रवर सत्व)",
                    "मध्यम — कभी-कभी तनाव लेकिन संभाल लेते हैं (मध्यम सत्व)",
                    "जल्दी घबराने, चिंता या उदासी की प्रवृत्ति (अवर सत्व)",
                    "जल्दी गुस्सा या चिड़चिड़ापन आने की प्रवृत्ति",
                    "पता नहीं / उत्तर नहीं देना चाहते",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 7. Dashavidha Pariksha: Samhanana & Bala (Physical Build & Constitutional Tolerance)
        if "ayush_samhanana" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_samhanana",
                section="dashavidha_pariksha",
                stage_number=4,
                stage_title_en="Stage 4: Physical Build (Samhanana)",
                stage_title_hi="चरण 4: शारीरिक संहनन व गठन",
                section_title_en="Body Compactness & Climate Tolerance",
                section_title_hi="शरीर का गठन व मौसम सहनशीलता",
                text_en="How is your natural physical build and tolerance to weather (Samhanana & Satmya)?",
                text_hi="आपके शरीर की बनावट और मौसम के प्रति संवेदनशीलता (संहनन व सात्म्य) कैसी है?",
                hint_en="Report your natural physical tendency. No constitutional diagnosis is inferred.",
                hint_hi="अपनी स्वाभाविक शारीरिक बनावट बताएं। कोई निदान स्वचालित रूप से नहीं लगाया जाता।",
                options_en=[
                    "Heavier / broad build, sensitive to cold/damp, rarely catches fever",
                    "Medium athletic build, sensitive to heat, sweats easily",
                    "Lean / slender build, dry skin, sensitive to cold winds",
                    "Balanced / average body structure",
                    "I don't know / Unsure",
                ],
                options_hi=[
                    "भारी / चौड़ा गठन, ठंड व सीलन से परेशानी, जल्दी बीमार न होना",
                    "मध्यम गठीला शरीर, गर्मी असहनीय, पसीना जल्दी आना",
                    "दुबला / पतला शरीर, रूखी त्वचा, ठंडी हवा से परेशानी",
                    "संतुलित / सामान्य शारीरिक गठन",
                    "पता नहीं / अनिश्चित",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 8. Elimination: Mala & Mutra (Bowel & Urinary habits if not yet captured)
        if "ayush_mala_mutra" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_mala_mutra",
                section="mala_mutra",
                stage_number=5,
                stage_title_en="Stage 5: Excretory Functions (Mala & Mutra)",
                stage_title_hi="चरण 5: मल एवं मूत्र प्रवृत्ति",
                section_title_en="Urinary & Bowel Habits",
                section_title_hi="मूत्र एवं मल विसर्जन",
                text_en="Do you experience any burning, frequency changes, or difficulties during urination or bowel movements?",
                text_hi="क्या पेशाब या शौच में किसी प्रकार की जलन, बार-बार जाने की आवश्यकता या कोई अन्य परेशानी होती है?",
                hint_en="Select any reported symptoms or choose 'Normal / No issues'.",
                hint_hi="कोई लक्षण महसूस हो रहा हो तो चुनें या 'सामान्य / कोई परेशानी नहीं' चुनें।",
                options_en=[
                    "Normal urination and regular bowel habits — No issues",
                    "Burning sensation during urination",
                    "Frequent urination, especially at night",
                    "Constipation or incomplete evacuation",
                    "Loose or watery stools",
                    "I don't know / Prefer not to answer",
                ],
                options_hi=[
                    "सामान्य पेशाब व नियमित पेट साफ — कोई समस्या नहीं",
                    "पेशाब में जलन होना",
                    "बार-बार पेशाब आना (विशेषकर रात में)",
                    "कब्ज या पेट पूरी तरह साफ न होना",
                    "पतले दस्त लगना",
                    "पता नहीं / उत्तर नहीं देना चाहते",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 9. Treatment History: Prior AYUSH / Traditional Therapies
        if "ayush_treatment_history" not in answered_ids:
            return AdaptiveQuestionItem(
                question_id="ayush_treatment_history",
                section="treatment_history",
                stage_number=6,
                stage_title_en="Stage 6: Past Therapies & Routine Habits",
                stage_title_hi="चरण 6: पूर्व उपचार एवं आदतें",
                section_title_en="Prior AYUSH Care & Medications",
                section_title_hi="पूर्व आयुष चिकित्सा व दवाएं",
                text_en="Have you previously taken any Ayurvedic, Homeopathic, or traditional medicines, or undergone Panchakarma?",
                text_hi="क्या आपने पहले कभी कोई आयुर्वेदिक, होम्योपैथिक या पारंपरिक दवा ली है, या पंचकर्म कराया है?",
                hint_en="Helps the consulting physician understand your prior holistic exposure.",
                hint_hi="परामर्शदाता चिकित्सक को आपके पूर्व उपचार को समझने में मदद मिलती है।",
                options_en=[
                    "Yes, currently or previously taking Ayurvedic medicines",
                    "Yes, undergone Panchakarma / traditional detoxification",
                    "Yes, taking Homeopathic / Unani medicines",
                    "Only allopathic (modern medicine) taken so far",
                    "No prior treatment / First consultation",
                    "I don't know / Not sure",
                ],
                options_hi=[
                    "हाँ, पहले या वर्तमान में आयुर्वेदिक दवाएं ली हैं",
                    "हाँ, पूर्व में पंचकर्म / शोधन चिकित्सा कराई है",
                    "हाँ, होम्योपैथिक या यूनानी दवा ली है",
                    "अब तक केवल एलोपैथिक दवाएं ही ली हैं",
                    "कोई पूर्व उपचार नहीं / पहला परामर्श",
                    "पता नहीं / निश्चित नहीं",
                ],
                input_type="chips",
                is_terminal=False,
            )

        # 10. Conclusion / Completion
        return AdaptiveQuestionItem(
            question_id="ayush_conclusion",
            section="conclusion",
            stage_number=6,
            stage_title_en="Intake Complete",
            stage_title_hi="पूछताछ पूर्ण",
            section_title_en="AYUSH Intake Summary Ready",
            section_title_hi="आयुष विवरण तैयार",
            text_en="Thank you. Your structured AYUSH clinical history has been thoroughly collected. The consulting physician will review your details shortly.",
            text_hi="धन्यवाद। आपका समग्र आयुष स्वास्थ्य विवरण सफलतापूर्वक दर्ज कर लिया गया है। परामर्शदाता चिकित्सक शीघ्र ही इसका अवलोकन करेंगे।",
            hint_en="You may proceed to upload previous medical records or await your OPD token call.",
            hint_hi="अब आप अपने पुराने पर्चे/रिपोर्ट अपलोड कर सकते हैं या ओपीडी में अपनी बारी की प्रतीक्षा कर सकते हैं।",
            options_en=["Proceed to Document Upload", "Proceed to Summary Review"],
            options_hi=["दस्तावेज अपलोड करें", "विवरण समीक्षा देखें"],
            input_type="chips",
            is_terminal=True,
        )

    def parse_ayush_clinical_data(self, answers: List[dict]) -> AYUSHClinicalData:
        """
        Structures collected answers into AYUSHClinicalData and DashavidhaPariksha.
        Zero diagnosis. Purely maps patient-reported answers.
        """
        ans_map = {a.get("question_id"): a.get("patient_answer", "") for a in answers}

        # Dashavidha Pariksha mapping
        dp = DashavidhaPariksha(
            prakriti=ans_map.get("ayush_samhanana"),
            vikriti=ans_map.get("ayush_chief_complaint"),
            sara=None,
            samhanana=ans_map.get("ayush_samhanana"),
            pramana=None,
            satmya=ans_map.get("ayush_ahara"),
            satva=ans_map.get("ayush_manasika"),
            ahara_shakti=ans_map.get("ayush_agni"),
            vyayama_shakti=ans_map.get("ayush_vihara"),
            vaya=None,
        )

        return AYUSHClinicalData(
            prakriti=ans_map.get("ayush_samhanana"),
            vikriti=ans_map.get("ayush_chief_complaint"),
            agni=ans_map.get("ayush_agni"),
            koshta=ans_map.get("ayush_koshta"),
            bala=ans_map.get("ayush_vihara"),
            satmya=ans_map.get("ayush_ahara"),
            ahara=ans_map.get("ayush_ahara"),
            vihara=ans_map.get("ayush_vihara"),
            vyayama_shakti=ans_map.get("ayush_vihara"),
            nidra=ans_map.get("ayush_nidra"),
            mala=ans_map.get("ayush_koshta") or ans_map.get("ayush_mala_mutra"),
            mutra=ans_map.get("ayush_mala_mutra"),
            manasika=ans_map.get("ayush_manasika"),
            lifestyle=ans_map.get("ayush_vihara"),
            personal_history=None,
            family_history=None,
            treatment_history=ans_map.get("ayush_treatment_history"),
            dashavidha_pariksha=dp,
            patient_reported_prakriti_notes=ans_map.get("ayush_samhanana"),
            attending_physician_notes=None,
        )


ayush_service = AYUSHService()
