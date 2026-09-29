"use client";

import React, { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Stethoscope,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  Clock,
  User,
  ShieldCheck,
  Send,
  HelpCircle,
  EyeOff,
  RefreshCw,
  Sparkles,
  FileCheck,
  Check,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  RotateCcw,
  Languages,
  Loader2,
  FileText,
  ClipboardList,
} from "lucide-react";
import { WavAudioRecorder } from "@/lib/audioRecorder";
import { getAuthHeaders } from "@/lib/auth";

interface AdaptiveQuestionItem {
  question_id: string;
  section: string;
  stage_number: number;
  stage_title_en: string;
  stage_title_hi: string;
  section_title_en: string;
  section_title_hi: string;
  text_en: string;
  text_hi: string;
  hint_en?: string;
  hint_hi?: string;
  options_en?: string[];
  options_hi?: string[];
  input_type: string;
  is_terminal: boolean;
}

interface AnswerRecord {
  question_id: string;
  question_text: string;
  section: string;
  stage_number?: number;
  patient_answer: string;
  skipped: boolean;
  answered_at: string;
  question_order?: number;
  input_method?: string;
  language?: string;
  mode?: string;
}

interface TriageAlertInfo {
  alert_id: string;
  patient_id: string;
  token_number: string;
  patient_name?: string;
  full_name?: string;
  language?: string;
  priority: "URGENT" | "HIGH";
  detected_category?: string;
  category?: string;
  title_en?: string;
  title_hi?: string;
  rule_description?: string;
  description_en?: string;
  description_hi?: string;
  patient_instruction_en?: string;
  patient_instruction_hi?: string;
  triggering_answer?: string;
  triggering_text?: string;
  status: string;
  detected_at: string;
}

interface InterviewSession {
  session_id: string;
  patient_id: string;
  token_number: string;
  full_name: string;
  selected_language: "en" | "hi";
  status: "in_progress" | "completed" | "triage_alert";
  history_mode?: "general" | "ayush";
  started_at: string;
  completed_at?: string;
  answers: AnswerRecord[];
  current_question?: AdaptiveQuestionItem;
  answered_count: number;
  total_questions: number;
  current_question_index: number;
  current_stage_number: number;
  current_stage_title_en: string;
  current_stage_title_hi: string;
  is_complete: boolean;
  has_triage_alert?: boolean;
  triage_alert?: TriageAlertInfo | null;
  questions?: AdaptiveQuestionItem[];
}

function InterviewComponent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const patientIdParam = searchParams.get("patientId") || "";

  // State
  const [patientIdInput, setPatientIdInput] = useState(patientIdParam);
  const [historyMode, setHistoryMode] = useState<"general" | "ayush">("general");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingAnswer, setSavingAnswer] = useState(false);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [consentBlockedMessage, setConsentBlockedMessage] = useState<string | null>(null);

  // Voice Interface State (Phase 5 Fix)
  type VoiceState = "IDLE" | "LISTENING" | "PROCESSING" | "RECOGNIZED" | "ERROR";
  const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
  const [voiceLanguage, setVoiceLanguage] = useState<"en" | "hi">("en");
  const [selectedLanguage, setSelectedLanguage] = useState<"en" | "hi">("en");
  const [interimPreview, setInterimPreview] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sttSupported, setSttSupported] = useState(true);
  const [ttsSupported, setTtsSupported] = useState(true);
  const [autoSpeakEnabled, setAutoSpeakEnabled] = useState(true);
  const [voiceStatusMessage, setVoiceStatusMessage] = useState<string | null>(null);
  const [voiceErrorMessage, setVoiceErrorMessage] = useState<string | null>(null);
  const [wasVoiceInput, setWasVoiceInput] = useState(false);

  // Browser Voices & TTS Audio State
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [nativeHindiVoiceAvailable, setNativeHindiVoiceAvailable] = useState<boolean | null>(null);
  const [ttsFallbackNotice, setTtsFallbackNotice] = useState<string | null>(null);
  const [activeVoiceName, setActiveVoiceName] = useState<string>("");

  const recognitionRef = useRef<any>(null);
  const isListeningModeRef = useRef(false);
  const committedTranscriptRef = useRef("");
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const wavRecorderRef = useRef<WavAudioRecorder>(new WavAudioRecorder());

  // Helper to pick the best Hindi voice available in the browser/device
  const selectBestHindiVoice = (voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null => {
    const hiVoices = voices.filter(
      (v) =>
        v.lang.toLowerCase() === "hi-in" ||
        v.lang.toLowerCase().startsWith("hi") ||
        v.name.toLowerCase().includes("hindi") ||
        v.name.toLowerCase().includes("हिन्दी")
    );
    if (hiVoices.length === 0) return null;

    // Prioritize exact hi-IN
    const hiIn = hiVoices.filter((v) => v.lang.toLowerCase() === "hi-in");
    const candidates = hiIn.length > 0 ? hiIn : hiVoices;

    // Prioritize natural/neural/Google/Microsoft high quality voices
    const preferred = candidates.find(
      (v) =>
        v.name.toLowerCase().includes("natural") ||
        v.name.toLowerCase().includes("google") ||
        v.name.toLowerCase().includes("swara") ||
        v.name.toLowerCase().includes("madhur") ||
        v.name.toLowerCase().includes("hemant") ||
        v.name.toLowerCase().includes("kalpana")
    );
    return preferred || candidates[0];
  };

  // Helper to pick the best English voice (preferring Indian English en-IN)
  const selectBestEnglishVoice = (voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null => {
    const enIn = voices.filter(
      (v) =>
        v.lang.toLowerCase() === "en-in" ||
        v.name.toLowerCase().includes("india") ||
        v.name.toLowerCase().includes("neerja") ||
        v.name.toLowerCase().includes("prabhat") ||
        v.name.toLowerCase().includes("heera")
    );
    if (enIn.length > 0) {
      const preferred = enIn.find(
        (v) =>
          v.name.toLowerCase().includes("natural") ||
          v.name.toLowerCase().includes("google") ||
          v.name.toLowerCase().includes("microsoft")
      );
      return preferred || enIn[0];
    }
    return voices.find((v) => v.lang.toLowerCase().startsWith("en")) || null;
  };

  // Refresh and detect available voices from browser
  const refreshVoices = useCallback(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    try {
      const voices = window.speechSynthesis.getVoices();
      if (voices && voices.length > 0) {
        setBrowserVoices(voices);
        const bestHi = selectBestHindiVoice(voices);
        setNativeHindiVoiceAvailable(bestHi !== null);
      }
    } catch (_) {}
  }, []);

  useEffect(() => {
    refreshVoices();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.onvoiceschanged = refreshVoices;
    }
  }, [refreshVoices]);

  // Synchronize language when session is ready
  useEffect(() => {
    if (session?.selected_language === "hi" || session?.selected_language === "en") {
      setSelectedLanguage(session.selected_language);
      setVoiceLanguage(session.selected_language);
    }
  }, [session?.selected_language]);

  // Check browser speech support on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const hasSTT = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
      const hasTTS = "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
      setSttSupported(Boolean(hasSTT));
      setTtsSupported(Boolean(hasTTS));
    }
  }, []);

  // Stop any active speech, recognition, and recording on unmount
  useEffect(() => {
    return () => {
      isListeningModeRef.current = false;
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (audioPlayerRef.current) {
        try {
          audioPlayerRef.current.pause();
        } catch (_) {}
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
      wavRecorderRef.current.cancel();
    };
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch (_) {}
    }
    if (audioPlayerRef.current) {
      try {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      } catch (_) {}
    }
    setIsSpeaking(false);
  }, []);

  // Speak clinical question aloud matching selected language
  const speakQuestion = useCallback((overrideText?: string, langOverride?: "en" | "hi") => {
    if (typeof window === "undefined") {
      return;
    }
    const currentQ = session?.current_question;
    if (!currentQ && !overrideText) return;

    stopSpeaking();
    setTtsFallbackNotice(null);

    const activeLang = langOverride || selectedLanguage;
    const isHindi = activeLang === "hi";
    const textToSpeak = overrideText || (isHindi ? currentQ!.text_hi : currentQ!.text_en);
    if (!textToSpeak) return;

    const hasTTS = "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

    if (isHindi) {
      // 1. Check if browser has an authentic Hindi voice installed
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const bestHiVoice = selectBestHindiVoice(voices);

      if (bestHiVoice && hasTTS) {
        // Native device/browser Hindi voice found
        setActiveVoiceName(`${bestHiVoice.name} (Device Hindi Voice)`);
        setTtsFallbackNotice(null);
        const utterance = new SpeechSynthesisUtterance(textToSpeak);
        utterance.voice = bestHiVoice;
        utterance.lang = "hi-IN";
        utterance.rate = 0.92; // Steady, clear OPD delivery
        utterance.pitch = 1.0;

        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = (err) => {
          console.warn("Browser SpeechSynthesis error:", err);
          setIsSpeaking(false);
        };

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
        return;
      }

      // 2. No native Hindi voice on device/browser -> Fallback to MediKiosk backend audio stream
      // Requirement 4: "If no Hindi voice is available, clearly show a fallback message instead of pretending Hindi TTS is working."
      // Requirement 8: "Do not use fake audio files or prerecorded/sample speech. Use real browser/device TTS or the existing real TTS backend implementation."
      setTtsFallbackNotice(
        "सूचना: इस डिवाइस पर मूल हिन्दी आवाज उपलब्ध नहीं है। मेडीकियोस्क हॉस्पिटल ऑडियो इंजन द्वारा वाचन किया जा रहा है।"
      );
      setActiveVoiceName("मेडीकियोस्क हॉस्पिटल ऑडियो इंजन (हिन्दी)");

      try {
        const audioUrl = `http://127.0.0.1:8000/api/voice/speak?text=${encodeURIComponent(textToSpeak)}&language=hi`;
        const audio = new Audio(audioUrl);
        audioPlayerRef.current = audio;

        audio.onplay = () => setIsSpeaking(true);
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = (e) => {
          console.warn("Backend Hindi TTS playback error:", e);
          setIsSpeaking(false);
          setTtsFallbackNotice(
            "हिन्दी आवाज वाचन अनुपलब्ध है। कृपया ऊपर प्रदर्शित प्रश्न पढ़ें।"
          );
        };

        const playPromise = audio.play();
        if (playPromise !== undefined) {
          playPromise.catch((err) => {
            console.warn("Audio playback prevented by browser autoplay policy:", err);
            setIsSpeaking(false);
          });
        }
      } catch (err) {
        console.warn("Error initiating backend TTS audio:", err);
        setIsSpeaking(false);
      }
    } else {
      // English Voice Synthesis
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const bestEnVoice = selectBestEnglishVoice(voices);

      if (bestEnVoice && hasTTS) {
        setActiveVoiceName(`${bestEnVoice.name} (en-IN)`);
        setTtsFallbackNotice(null);
        const utterance = new SpeechSynthesisUtterance(textToSpeak);
        utterance.voice = bestEnVoice;
        utterance.lang = bestEnVoice.lang || "en-IN";
        utterance.rate = 0.92;
        utterance.pitch = 1.0;

        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
        return;
      }

      // Fallback to backend English audio if browser lacks English voice
      setTtsFallbackNotice(
        "Notice: Device English voice unavailable. Using MediKiosk Hospital Audio Engine."
      );
      setActiveVoiceName("MediKiosk Hospital Audio Engine (en-IN)");

      try {
        const audioUrl = `http://127.0.0.1:8000/api/voice/speak?text=${encodeURIComponent(textToSpeak)}&language=en`;
        const audio = new Audio(audioUrl);
        audioPlayerRef.current = audio;

        audio.onplay = () => setIsSpeaking(true);
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = () => setIsSpeaking(false);

        const playPromise = audio.play();
        if (playPromise !== undefined) {
          playPromise.catch(() => setIsSpeaking(false));
        }
      } catch (_) {
        setIsSpeaking(false);
      }
    }
  }, [session, selectedLanguage, stopSpeaking]);

  // Auto-speak question when a new question arrives
  useEffect(() => {
    if (
      session &&
      session.current_question &&
      !session.is_complete &&
      session.status === "in_progress" &&
      autoSpeakEnabled
    ) {
      const timer = setTimeout(() => {
        speakQuestion();
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [session?.current_question?.question_id, autoSpeakEnabled, speakQuestion]);

  // Stop any active audio immediately upon triage alert
  useEffect(() => {
    if (session?.has_triage_alert || session?.status === "triage_alert" || session?.triage_alert) {
      stopSpeaking();
    }
  }, [session?.has_triage_alert, session?.status, session?.triage_alert, stopSpeaking]);

  // Language switcher: updates locale and resets active recognition without touching prior answers
  const handleLanguageSwitch = (newLang: "en" | "hi") => {
    if (newLang === selectedLanguage) return;

    stopSpeaking();
    if (isListeningModeRef.current) {
      isListeningModeRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
      wavRecorderRef.current.cancel();
      setVoiceState("IDLE");
    }

    setSelectedLanguage(newLang);
    setVoiceLanguage(newLang);
    setVoiceErrorMessage(null);
    setVoiceStatusMessage(
      newLang === "hi"
        ? "भाषा: हिन्दी (hi-IN) चयनित। आवाज और प्रश्न अद्यतन किए गए।"
        : "Language: English (en-IN) selected. Voice and questions updated."
    );

    // Sync language to backend session in MongoDB
    if (session?.session_id) {
      fetch(`http://127.0.0.1:8000/api/interview/${session.session_id}/language`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify({ language: newLang }),
      }).catch((e) => console.warn("Failed to persist language switch:", e));
    }

    // Immediately speak the question in the newly selected language if auto-speak is ON
    if (autoSpeakEnabled && session?.current_question) {
      setTimeout(() => {
        speakQuestion(undefined, newLang);
      }, 250);
    }
  };

  // Start continuous microphone speech recognition
  const startListening = async () => {
    if (typeof window === "undefined") return;

    stopSpeaking();
    setVoiceErrorMessage(null);
    setVoiceStatusMessage(null);
    setInterimPreview("");
    setVoiceState("LISTENING");
    isListeningModeRef.current = true;

    // Retain previously entered or recognized text, allowing continuous accumulation
    committedTranscriptRef.current = currentAnswer.trim();

    // 1. Start raw microphone audio recorder in background for robust WAV fallback
    try {
      await wavRecorderRef.current.start();
    } catch (micErr: any) {
      console.warn("Microphone hardware access error:", micErr);
      isListeningModeRef.current = false;
      setVoiceState("ERROR");
      if (micErr.name === "NotAllowedError" || micErr.name === "PermissionDeniedError") {
        setVoiceErrorMessage(
          voiceLanguage === "hi"
            ? "माइक्रोफ़ोन की अनुमति अस्वीकृत कर दी गई है। कृपया ब्राउज़र सेटिंग्स में माइक्रोफ़ोन की अनुमति दें।"
            : "Microphone permission denied. Please allow microphone access in your browser settings."
        );
      } else {
        setVoiceErrorMessage(
          voiceLanguage === "hi"
            ? "माइक्रोफ़ोन उपलब्ध नहीं है। कृपया ऑडियो इनपुट जांचें या नीचे टाइप करें।"
            : "Microphone unavailable. Please verify your audio hardware or type below."
        );
      }
      return;
    }

    // 2. Setup low-latency Web Speech API
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      setVoiceStatusMessage(
        voiceLanguage === "hi"
          ? "माइक सक्रिय है... अपनी गति से पूरा वाक्य बोलें। समाप्त होने पर 'बोलना समाप्त करें' दबाएं।"
          : "Microphone active... Speak your full sentence naturally. Tap 'Tap to Stop' when finished."
      );
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.lang = voiceLanguage === "hi" ? "hi-IN" : "en-IN";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setVoiceStatusMessage(
          voiceLanguage === "hi"
            ? "सुन रहे हैं... अपनी गति से पूरा वाक्य बोलें (रुकने पर सत्र बंद नहीं होगा)"
            : "Listening... Speak naturally in complete sentences without rushing"
        );
      };

      recognition.onresult = (event: any) => {
        let finalChunk = "";
        let interimChunk = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const result = event.results[i];
          if (result.isFinal) {
            finalChunk += result[0].transcript + " ";
          } else {
            interimChunk += result[0].transcript;
          }
        }

        if (finalChunk) {
          const updated = committedTranscriptRef.current
            ? `${committedTranscriptRef.current} ${finalChunk.trim()}`
            : finalChunk.trim();
          committedTranscriptRef.current = updated;
          setCurrentAnswer(updated);
          setWasVoiceInput(true);
          setInterimPreview("");
        } else if (interimChunk) {
          setInterimPreview(interimChunk);
        }
      };

      recognition.onerror = (event: any) => {
        const err = event.error;
        console.warn("Speech recognition event:", err);

        // Natural pauses: do not abort listening mode
        if (err === "no-speech") {
          return;
        }

        if (err === "not-allowed" || err === "permission-denied") {
          isListeningModeRef.current = false;
          wavRecorderRef.current.cancel();
          setVoiceState("ERROR");
          setVoiceErrorMessage(
            voiceLanguage === "hi"
              ? "माइक्रोफ़ोन की अनुमति अस्वीकृत कर दी गई है। कृपया ब्राउज़र में अनुमति दें या नीचे टाइप करें।"
              : "Microphone access denied. Please allow microphone permission or type below."
          );
          return;
        }

        // On network error from browser Speech API, log notice (audio recorder will supply audio)
        if (err === "network") {
          console.log("Client Speech API network timeout — fallback audio recorder active.");
        }
      };

      recognition.onend = () => {
        // Continuous auto-restart: if user is still in listening mode, restart seamlessly
        if (isListeningModeRef.current) {
          try {
            recognition.start();
          } catch (_) {}
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e: any) {
      console.warn("SpeechRec start error:", e);
      setVoiceStatusMessage(
        voiceLanguage === "hi"
          ? "ऑडियो रिकॉर्डिंग सक्रिय है... बोलने के बाद 'बोलना समाप्त करें' दबाएं।"
          : "Audio recording active... Tap 'Tap to Stop' when finished speaking."
      );
    }
  };

  // Stop listening: commit transcripts and run backend WAV fallback if needed
  const stopListening = async () => {
    isListeningModeRef.current = false;
    setVoiceState("PROCESSING");

    // 1. Stop Web Speech recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
    }

    // 2. Commit any in-flight interim preview
    let accumulated = committedTranscriptRef.current.trim();
    if (interimPreview.trim()) {
      accumulated = accumulated
        ? `${accumulated} ${interimPreview.trim()}`
        : interimPreview.trim();
      setInterimPreview("");
    }

    // 3. Stop WAV recorder
    let audioBlob: Blob | null = null;
    try {
      if (wavRecorderRef.current.isRecording) {
        audioBlob = await wavRecorderRef.current.stop();
      }
    } catch (recErr) {
      console.warn("WAV recorder stop error:", recErr);
    }

    // If client Web Speech API accumulated speech, finalize and display
    if (accumulated) {
      setCurrentAnswer(accumulated);
      setWasVoiceInput(true);
      setVoiceState("RECOGNIZED");
      setVoiceStatusMessage(
        voiceLanguage === "hi"
          ? "आवाज पहचानी गई! आप नीचे उत्तर को संपादित कर सकते हैं या 'उत्तर दर्ज करें' दबाएं।"
          : "Voice recognized! You can review or edit the text below, then tap Submit Answer."
      );
      return;
    }

    // If Web Speech API caught nothing (e.g. Chrome network timeout), send WAV audio to backend STT
    if (audioBlob && audioBlob.size > 1000) {
      try {
        setVoiceStatusMessage(
          voiceLanguage === "hi"
            ? "आवाज का विश्लेषण किया जा रहा है..."
            : "Processing microphone audio via hospital speech engine..."
        );

        const formData = new FormData();
        formData.append("audio_file", audioBlob, "patient_speech.wav");
        formData.append("language", voiceLanguage);

        const res = await fetch("http://127.0.0.1:8000/api/voice/transcribe", {
          method: "POST",
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          if (data.transcript && data.transcript.trim()) {
            const serverTranscript = data.transcript.trim();
            setCurrentAnswer(serverTranscript);
            setWasVoiceInput(true);
            setVoiceState("RECOGNIZED");
            setVoiceStatusMessage(
              voiceLanguage === "hi"
                ? "आवाज सफलतापूर्वक पहचानी गई। आप नीचे उत्तर संपादित कर सकते हैं।"
                : "Spoken answer recognized successfully! You can review or edit below."
            );
            return;
          }
        }
      } catch (backendErr) {
        console.warn("Backend STT error:", backendErr);
      }
    }

    // If neither engine captured intelligible speech
    setVoiceState("ERROR");
    setVoiceErrorMessage(
      voiceLanguage === "hi"
        ? "कोई स्पष्ट आवाज नहीं सुनी गई। कृपया पुनः माइक दबाकर बोलें या नीचे लिखें।"
        : "No speech was detected. Please tap the microphone again and speak clearly, or type below."
    );
  };

  // Initialize or resume interview session
  const initSession = async (pid: string, modeOverride?: "general" | "ayush") => {
    if (!pid.trim()) return;
    setLoading(true);
    setErrorMessage(null);
    setConsentBlockedMessage(null);

    const activeMode = modeOverride || historyMode;

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/interview/start?patient_id=${encodeURIComponent(pid.trim())}&mode=${activeMode}`, {
        method: "POST",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 403) {
          setConsentBlockedMessage(errData.detail || "Patient consent is required before starting the clinical interview.");
          setLoading(false);
          return;
        }
        throw new Error(errData.detail || "Could not start interview session.");
      }

      const data: InterviewSession = await res.json();
      setSession(data);
      if (data.history_mode === "ayush" || data.history_mode === "general") {
        setHistoryMode(data.history_mode);
      }
      setCurrentAnswer("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load clinical interview session.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const urlMode = searchParams.get("mode") as "general" | "ayush" | null;
    const initialMode = urlMode === "ayush" ? "ayush" : "general";
    if (urlMode) {
      setHistoryMode(initialMode);
    }
    if (patientIdParam) {
      initSession(patientIdParam, initialMode);
    } else {
      setLoading(false);
    }
  }, [patientIdParam, searchParams]);

  // Submit Answer to MongoDB & fetch next adaptive question
  const handleAnswerSubmit = async (answerText: string, isSkipped = false) => {
    if (!session || !session.current_question) return;
    const currentQ = session.current_question;

    const trimmed = answerText.trim();
    if (!trimmed) {
      setErrorMessage(
        session.selected_language === "hi"
          ? "कृपया उत्तर दर्ज करें या नीचे दिए गए विकल्पों में से चुनें।"
          : "Please enter an answer or choose from the quick options below."
      );
      return;
    }

    const usedVoice = wasVoiceInput;
    stopSpeaking();
    isListeningModeRef.current = false;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
    }
    wavRecorderRef.current.cancel();
    setVoiceState("IDLE");
    setVoiceStatusMessage(null);
    setVoiceErrorMessage(null);
    setInterimPreview("");
    setWasVoiceInput(false);

    setSavingAnswer(true);
    setErrorMessage(null);

    const isHindi = selectedLanguage === "hi";
    const questionText = isHindi ? currentQ.text_hi : currentQ.text_en;
    const isAyush = (session?.history_mode === "ayush") || (historyMode === "ayush") || currentQ.question_id.startsWith("ayush_");

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/interview/${session.session_id}/answer`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          question_id: currentQ.question_id,
          question_text: questionText,
          section: currentQ.section,
          stage_number: currentQ.stage_number,
          patient_answer: trimmed,
          skipped: isSkipped,
          input_method: usedVoice ? "voice" : "text",
          language: selectedLanguage,
          mode: isAyush ? "ayush" : "general",
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to save answer to database.");
      }

      const updatedSession: InterviewSession = await res.json();
      setSession(updatedSession);
      if (updatedSession.selected_language === "hi" || updatedSession.selected_language === "en") {
        setSelectedLanguage(updatedSession.selected_language);
        setVoiceLanguage(updatedSession.selected_language);
      }
      setCurrentAnswer("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to persist answer.");
    } finally {
      setSavingAnswer(false);
    }
  };

  // Complete Interview manually
  const handleCompleteInterview = async (sessionId: string) => {
    setSavingAnswer(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/interview/${sessionId}/complete`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const completedSession: InterviewSession = await res.json();
        setSession(completedSession);
      }
    } catch (err) {
      console.error("Error finalizing interview:", err);
    } finally {
      setSavingAnswer(false);
    }
  };

  // 1. LOADING STATE
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <div className="w-16 h-16 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <h2 className="text-xl font-bold text-slate-800">Initializing Clinical Interview...</h2>
        <p className="text-slate-500 text-sm">Validating consent and preparing adaptive intake session.</p>
      </div>
    );
  }

  // 2. CONSENT BLOCKED GUARD
  if (consentBlockedMessage) {
    return (
      <div className="max-w-2xl mx-auto py-12 px-4">
        <div className="bg-amber-50 border-2 border-amber-300 rounded-3xl p-6 sm:p-8 text-center space-y-6 shadow-md">
          <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-2xl flex items-center justify-center mx-auto">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-amber-950">Patient Consent Required</h2>
            <p className="text-sm sm:text-base text-amber-900 leading-relaxed max-w-lg mx-auto">
              {consentBlockedMessage}
            </p>
          </div>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            {patientIdParam && (
              <Link
                href={`/consent?patientId=${encodeURIComponent(patientIdParam)}`}
                className="w-full sm:w-auto px-6 py-3.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold text-sm shadow transition"
              >
                Go to Consent Screen
              </Link>
            )}
            <Link
              href="/queue"
              className="w-full sm:w-auto px-6 py-3.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-sm shadow transition"
            >
              Back to OPD Queue
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 3. LOOKUP FORM IF NO PATIENT ID
  if (!session) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4">
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
          <div className="text-center space-y-2">
            <div className="w-14 h-14 bg-teal-50 text-teal-700 rounded-2xl flex items-center justify-center mx-auto">
              <Stethoscope className="w-7 h-7" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900">Start Clinical Interview</h2>
            <p className="text-slate-500 text-sm">
              Please enter your OPD Token Number (e.g. MK-20260910-0001) or Patient ID to proceed.
            </p>
          </div>

          {errorMessage && (
            <div className="bg-rose-50 border border-rose-200 text-rose-800 text-sm p-4 rounded-xl flex items-start space-x-2">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                OPD Token or Patient ID
              </label>
              <input
                type="text"
                value={patientIdInput}
                onChange={(e) => setPatientIdInput(e.target.value)}
                placeholder="e.g. MK-20260910-0002"
                className="w-full text-lg font-mono px-4 py-3.5 border-2 border-slate-200 rounded-xl focus:border-teal-500 focus:outline-none uppercase"
              />
            </div>

            {/* History Mode Selector */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                Select Intake History Mode
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setHistoryMode("general")}
                  className={`p-3.5 rounded-xl border-2 text-left transition ${
                    historyMode === "general"
                      ? "border-teal-600 bg-teal-50/70 text-teal-950 shadow-xs ring-1 ring-teal-600/30"
                      : "border-slate-200 bg-white hover:border-slate-300 text-slate-700"
                  }`}
                >
                  <div className="flex items-center space-x-2 font-bold text-sm">
                    <Stethoscope className="w-4 h-4 text-teal-600" />
                    <span>General Clinical</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 leading-snug">
                    Standard allopathic clinical inquiry: symptoms, onset, severity, systems.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setHistoryMode("ayush")}
                  className={`p-3.5 rounded-xl border-2 text-left transition ${
                    historyMode === "ayush"
                      ? "border-emerald-600 bg-emerald-50/70 text-emerald-950 shadow-xs ring-1 ring-emerald-600/30"
                      : "border-slate-200 bg-white hover:border-slate-300 text-slate-700"
                  }`}
                >
                  <div className="flex items-center space-x-2 font-bold text-sm">
                    <span className="text-base">🌿</span>
                    <span>AYUSH History</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 leading-snug">
                    Classical holistic intake: Agni, Koshta, Ahara, Vihara, Bala & Dashavidha.
                  </p>
                </button>
              </div>
            </div>

            <button
              onClick={() => initSession(patientIdInput, historyMode)}
              disabled={!patientIdInput.trim() || loading}
              className="w-full py-4 px-6 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl font-bold text-base shadow-md flex items-center justify-center space-x-2 transition"
            >
              <span>Begin Intake</span>
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3.5 TRIAGE EMERGENCY ALERT SCREEN
  if (session.has_triage_alert || session.status === "triage_alert" || session.triage_alert) {
    const alert = session.triage_alert;
    const isHindi = session.selected_language === "hi";

    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        {/* Urgent Emergency Alert Card */}
        <div className="bg-rose-50 border-4 border-rose-500 rounded-3xl p-6 sm:p-10 shadow-2xl space-y-6">
          <div className="flex flex-col sm:flex-row items-center sm:items-start space-y-4 sm:space-y-0 sm:space-x-6">
            <div className="w-20 h-20 bg-rose-600 text-white rounded-3xl flex items-center justify-center flex-shrink-0 shadow-lg animate-pulse">
              <AlertTriangle className="w-12 h-12" />
            </div>
            <div className="text-center sm:text-left space-y-2 flex-1">
              <div className="inline-flex items-center space-x-2 px-3.5 py-1 rounded-full text-xs font-black bg-rose-600 text-white tracking-widest uppercase shadow-sm">
                <span>⚠️ {alert?.priority || "URGENT"} TRIAGE ALERT</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-rose-950 tracking-tight">
                {isHindi
                  ? "तत्काल चिकित्सा सहायता की आवश्यकता हो सकती है"
                  : "Urgent Medical Attention Required"}
              </h1>
              <p className="text-base sm:text-lg font-semibold text-rose-900 leading-snug">
                {isHindi
                  ? "कृपया प्रश्नावली रोकें और तुरंत अस्पताल के कर्मचारियों को सूचित करें या आपातकालीन/कैजुअल्टी डेस्क पर जाएं।"
                  : "Please stop the questionnaire immediately and notify hospital staff or proceed directly to the Emergency / Casualty Desk."}
              </p>
            </div>
          </div>

          {/* Bilingual Information Box */}
          <div className="bg-white border-2 border-rose-200 rounded-2xl p-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-rose-50/70 rounded-xl border border-rose-200 space-y-1">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Patient Details / मरीज का विवरण
                </span>
                <p className="text-lg font-bold text-slate-900">{session.full_name}</p>
                <p className="text-xs font-mono font-semibold text-slate-600">
                  OPD Token: <span className="text-teal-700 font-bold">{session.token_number}</span>
                </p>
                {alert?.alert_id && (
                  <p className="text-xs font-mono text-slate-500">
                    Alert ID: {alert.alert_id}
                  </p>
                )}
              </div>

              <div className="p-4 bg-rose-50/70 rounded-xl border border-rose-200 space-y-1">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Flagged Warning / चेतावनी श्रेणी
                </span>
                <p className="text-base font-bold text-rose-900">
                  {isHindi ? alert?.title_hi || alert?.title_en || alert?.detected_category : alert?.title_en || alert?.detected_category || alert?.rule_description || "Acute Clinical Warning Sign"}
                </p>
                <p className="text-xs text-rose-800">
                  {isHindi ? alert?.description_hi || alert?.description_en || alert?.rule_description : alert?.rule_description || alert?.description_en}
                </p>
              </div>
            </div>

            {/* Emergency Action Directive */}
            <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl space-y-2">
              <span className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                Action Instructions / तत्काल निर्देश:
              </span>
              <p className="text-sm text-amber-950 font-semibold leading-relaxed">
                {isHindi
                  ? alert?.patient_instruction_hi || "कृपया तुरंत ओपीडी नर्स या नजदीकी आपातकालीन कक्ष (Casualty) से संपर्क करें।"
                  : alert?.patient_instruction_en || "Please immediately contact the nearest OPD nurse or walk to the Emergency Room / Casualty."}
              </p>
              {!isHindi && alert?.patient_instruction_hi && (
                <p className="text-xs text-amber-900 border-t border-amber-200 pt-2 font-medium">
                  (हिन्दी): {alert.patient_instruction_hi}
                </p>
              )}
            </div>

            {/* Quoted Patient Input */}
            {(alert?.triggering_answer || alert?.triggering_text) && (
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1">
                <span className="font-bold text-slate-600 uppercase tracking-wider">
                  Reported Symptom / दर्ज लक्षण:
                </span>
                <p className="font-mono text-slate-800 italic bg-white p-2.5 rounded border border-slate-200 text-sm">
                  &ldquo;{alert?.triggering_answer || alert?.triggering_text}&rdquo;
                </p>
              </div>
            )}
          </div>

          {/* Safety & Protocol Notice */}
          <div className="text-xs text-rose-900 bg-rose-100/70 border border-rose-200 p-4 rounded-xl space-y-1">
            <p className="font-semibold">
              🔒 <strong>Hospital Safety Protocol:</strong> The clinical intake questionnaire has been suspended to prevent delay in care. Hospital triage personnel have received an active alert on the central monitor.
            </p>
            <p className="text-[11px] text-rose-800">
              Note: This is an automated safety alert, NOT a clinical diagnosis. An emergency physician or nurse will evaluate you in person.
            </p>
          </div>

          {/* Actions */}
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4">
            <Link
              href="/queue"
              className="w-full sm:w-auto px-6 py-3.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-sm shadow transition text-center"
            >
              Return to OPD Queue
            </Link>
            <Link
              href="/triage"
              className="w-full sm:w-auto px-6 py-3.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold text-sm shadow-md transition text-center flex items-center justify-center space-x-2"
            >
              <AlertTriangle className="w-4 h-4" />
              <span>View Hospital Triage Board</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 4. INTERVIEW COMPLETED SUMMARY SCREEN
  if (session.status === "completed" || session.is_complete || (session.current_question && session.current_question.is_terminal)) {
    const isHindi = session.selected_language === "hi";

    return (
      <div className="max-w-3xl mx-auto py-6 px-4">
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-10 shadow-sm text-center space-y-8">
          <div className="w-20 h-20 bg-teal-50 text-teal-600 rounded-3xl flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-10 h-10" />
          </div>

          <div className="space-y-2">
            <span className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold bg-teal-50 text-teal-700 border border-teal-200 uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isHindi ? "क्लिनिकल हिस्ट्री दर्ज" : "Adaptive Intake Complete"}</span>
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {isHindi ? "क्लिनिकल हिस्ट्री सफलतापूर्वक दर्ज की गई" : "Clinical History Recorded Successfully"}
            </h2>
            <p className="text-sm sm:text-base text-slate-600 max-w-lg mx-auto">
              {isHindi
                ? "आपके द्वारा दी गई जानकारी सुरक्षित रूप से डेटाबेस में दर्ज कर ली गई है। डॉक्टर इस सारांश की समीक्षा करेंगे।"
                : "Your clinical history has been organized and securely persisted for physician review during your OPD consultation."}
            </p>
          </div>

          {/* Patient Card */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-4 text-left">
            <div>
              <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider block">
                {isHindi ? "मरीज का नाम" : "Patient Name"}
              </span>
              <strong className="text-lg font-bold text-slate-900">{session.full_name}</strong>
            </div>
            <div className="sm:text-right">
              <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider block">
                {isHindi ? "ओपीडी टोकन" : "OPD Token"}
              </span>
              <span className="text-lg font-mono font-bold text-teal-700 bg-teal-50 px-3 py-1 rounded-lg border border-teal-200 inline-block">
                {session.token_number}
              </span>
            </div>
            <div className="sm:text-right">
              <span className="text-xs text-slate-500 font-semibold uppercase tracking-wider block">
                {isHindi ? "कुल दर्ज उत्तर" : "Answers Logged"}
              </span>
              <span className="text-lg font-bold text-slate-800 inline-flex items-center space-x-1">
                <FileCheck className="w-4 h-4 text-teal-600" />
                <span>{session.answers.length} Questions</span>
              </span>
            </div>
          </div>

          {/* Recorded History Summary List */}
          <div className="text-left space-y-3">
            <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">
              {isHindi ? "दर्ज क्लिनिकल इतिहास सारांश" : "Recorded Clinical History Summary"}
            </h3>
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {session.answers.map((ans, i) => (
                <div key={i} className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs sm:text-sm">
                  <div className="flex justify-between items-center text-slate-500 font-semibold text-[11px] uppercase tracking-wider">
                    <span>{ans.section.replace("_", " ")}</span>
                    <span className="text-slate-400 font-mono">Q#{i + 1}</span>
                  </div>
                  <div className="font-medium text-slate-800 mt-0.5">{ans.question_text}</div>
                  <div className="font-bold text-teal-800 mt-1 pl-2 border-l-2 border-teal-600 bg-teal-50/50 py-1 rounded-r">
                    {ans.patient_answer}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Next Steps Card */}
          <div className="bg-teal-50 border border-teal-200 rounded-2xl p-4 text-left text-sm text-teal-950 flex items-start space-x-3">
            <Clock className="w-5 h-5 text-teal-600 flex-shrink-0 mt-0.5" />
            <div>
              <strong className="block text-teal-900 font-bold">
                {isHindi ? "अगला कदम: ओपीडी प्रतीक्षा कक्ष" : "Next Step: OPD Waiting Hall"}
              </strong>
              <p className="text-xs sm:text-sm text-teal-800 mt-0.5">
                {isHindi
                  ? "कृपया ओपीडी प्रतीक्षा कक्ष में बैठें। जब आपका टोकन स्क्रीन पर पुकारा जाए, तो डॉक्टर के कमरे में जाएं। डॉक्टर आपके इस इतिहास की समीक्षा करेंगे।"
                  : "Please proceed to the OPD Waiting Hall. When your token is called on the screen, proceed to the physician's room. Your doctor will review and confirm this intake summary."}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <Link
              href={`/summary?patientId=${encodeURIComponent(session.patient_id)}`}
              className="w-full py-3.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm sm:text-base shadow-md flex items-center justify-center space-x-2 transition"
            >
              <ClipboardList className="w-5 h-5" />
              <span>{isHindi ? "मेडिकल टाइमलाइन और सारांश देखें" : "View Timeline & Summary"}</span>
            </Link>
            <Link
              href={`/documents?patientId=${encodeURIComponent(session.patient_id)}`}
              className="w-full py-3.5 px-4 bg-teal-600 hover:bg-teal-700 text-white rounded-xl font-bold text-sm sm:text-base shadow-md flex items-center justify-center space-x-2 transition"
            >
              <FileText className="w-5 h-5" />
              <span>{isHindi ? "दस्तावेज़ अपलोड करें" : "Upload Documents"}</span>
            </Link>
            <Link
              href="/queue"
              className="w-full py-3.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl font-bold text-sm sm:text-base transition flex items-center justify-center space-x-1.5"
            >
              <span>View in OPD Queue</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
            <Link
              href="/"
              className="w-full py-3.5 px-4 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold text-sm sm:text-base shadow transition flex items-center justify-center"
            >
              <span>Back to Home</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 5. ACTIVE ADAPTIVE INTERVIEW INTERFACE
  const isHindi = selectedLanguage === "hi";
  const currentQ = session.current_question;

  if (!currentQ) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center space-y-4">
        <p className="text-slate-600">Loading next question...</p>
        <button
          onClick={() => initSession(session.patient_id)}
          className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-bold"
        >
          Refresh Question
        </button>
      </div>
    );
  }

  const stageTitle = isHindi ? currentQ.stage_title_hi : currentQ.stage_title_en;
  const sectionTitle = isHindi ? currentQ.section_title_hi : currentQ.section_title_en;
  const questionText = isHindi ? currentQ.text_hi : currentQ.text_en;
  const questionHint = isHindi ? currentQ.hint_hi : currentQ.hint_en;
  const options = isHindi ? currentQ.options_hi : currentQ.options_en;
  const stageProgressPercent = Math.min(Math.round((currentQ.stage_number / 6) * 100), 100);

  return (
    <div className="max-w-3xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Top Bar: Breadcrumb + Patient Info + Language Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-slate-600 hover:text-slate-900 text-sm font-semibold transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{isHindi ? "होम पर वापस" : "Exit to Home"}</span>
        </Link>

        <div className="flex items-center space-x-3">
          {/* Top Quick Language Switcher */}
          <div className="flex items-center space-x-1 bg-white border border-slate-200 p-1 rounded-xl shadow-xs">
            <button
              type="button"
              onClick={() => handleLanguageSwitch("en")}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                selectedLanguage === "en"
                  ? "bg-teal-600 text-white shadow-xs"
                  : "text-slate-600 hover:text-teal-700 hover:bg-teal-50"
              }`}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => handleLanguageSwitch("hi")}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                selectedLanguage === "hi"
                  ? "bg-teal-600 text-white shadow-xs"
                  : "text-slate-600 hover:text-teal-700 hover:bg-teal-50"
              }`}
            >
              हिन्दी
            </button>
          </div>

          {/* Patient Identity Tag */}
          <div className="flex items-center space-x-3 bg-white border border-slate-200 rounded-xl px-4 py-2 shadow-sm">
            <div className="w-8 h-8 rounded-lg bg-teal-100 text-teal-700 flex items-center justify-center">
              <User className="w-4 h-4" />
            </div>
            <div>
              <span className="text-xs font-bold text-slate-900 block">{session.full_name}</span>
              <span className="text-[11px] font-mono text-teal-700">Token: {session.token_number}</span>
            </div>
          </div>
        </div>
      </div>

      {/* AYUSH Mode Active Banner */}
      {session.history_mode === "ayush" && (
        <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50 border-2 border-emerald-300 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2.5">
            <span className="text-xl">🌿</span>
            <div>
              <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-950 block">
                {isHindi ? "आयुष नैदानिक इतिहास मोड" : "AYUSH Clinical History Mode"}
              </span>
              <span className="text-xs text-emerald-800">
                {isHindi
                  ? "पारंपरिक आयुर्वेदिक/होलिस्टिक स्वास्थ्य डेटा (अग्नि, कोष्ठ, आहार, विहार, बल एवं दशविध परीक्षा)"
                  : "Holistic intake assessing Agni, Koshta, Ahara, Vihara, Bala & Dashavidha"}
              </span>
            </div>
          </div>
          <span className="self-start sm:self-auto text-[10px] uppercase font-bold tracking-widest bg-emerald-200 text-emerald-900 px-2.5 py-1 rounded-full whitespace-nowrap">
            Non-Diagnostic
          </span>
        </div>
      )}

      {/* Adaptive Progress Bar Container */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2">
        <div className="flex justify-between items-center text-xs sm:text-sm font-bold text-slate-700">
          <span className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-600 animate-pulse" />
            <span className="text-teal-900 font-extrabold">{stageTitle}</span>
          </span>
          <span className="text-slate-500 font-mono text-xs">
            {isHindi ? `दर्ज उत्तर: ${session.answered_count}` : `Logged: ${session.answered_count} Questions`}
          </span>
        </div>

        {/* Visual Progress Bar */}
        <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
          <div
            className="bg-gradient-to-r from-teal-500 to-emerald-600 h-full rounded-full transition-all duration-300"
            style={{ width: `${Math.max(stageProgressPercent, 15)}%` }}
          />
        </div>
      </div>

      {/* Main Question Card */}
      <div className="bg-white border-2 border-teal-600/30 rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
        {/* Section Badge & Question Voice Playback Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-teal-50 text-teal-700 border border-teal-200">
              <Sparkles className="w-3.5 h-3.5 text-teal-600" />
              <span>{sectionTitle}</span>
            </span>
            <span className="text-xs font-semibold text-slate-400">
              {isHindi ? "एआई क्लिनिकल सहायक" : "Adaptive AI Intake"}
            </span>
          </div>

          {/* Voice Speaker (TTS) Action Bar */}
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => (isSpeaking ? stopSpeaking() : speakQuestion())}
              className={`inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition border ${
                isSpeaking
                  ? "bg-rose-50 text-rose-700 border-rose-300 animate-pulse shadow-sm"
                  : "bg-slate-50 hover:bg-teal-50 text-slate-700 hover:text-teal-800 border-slate-200"
              }`}
              title={isHindi ? "सवाल आवाज में सुनें" : "Listen to question aloud"}
            >
              {isSpeaking ? (
                <>
                  <VolumeX className="w-4 h-4 text-rose-600" />
                  <span>{isHindi ? "आवाज रोकें (Speaking)" : "Stop Audio"}</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-4 h-4 text-teal-600" />
                  <span>{isHindi ? "सवाल दोबारा सुनें" : "Replay Question"}</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setAutoSpeakEnabled(!autoSpeakEnabled)}
              className={`px-2.5 py-1.5 rounded-xl text-[11px] font-semibold transition border ${
                autoSpeakEnabled
                  ? "bg-teal-50 text-teal-800 border-teal-200"
                  : "bg-slate-100 text-slate-400 border-slate-200"
              }`}
              title={
                autoSpeakEnabled
                  ? (isHindi ? "स्वतः वाचन चालू है" : "Auto-play question audio is ON")
                  : (isHindi ? "स्वतः वाचन बंद है" : "Auto-play question audio is OFF")
              }
            >
              {autoSpeakEnabled ? (isHindi ? "ऑटो-स्पीच: ऑन" : "Auto-TTS: ON") : (isHindi ? "ऑटो-स्पीच: बंद" : "Auto-TTS: OFF")}
            </button>
          </div>
        </div>

        {/* TTS Fallback Notice (Requirement 4) */}
        {ttsFallbackNotice && (
          <div className="bg-amber-50 border border-amber-200 text-amber-900 text-xs px-3.5 py-2.5 rounded-xl flex items-start space-x-2 text-left">
            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <span className="leading-relaxed">{ttsFallbackNotice}</span>
          </div>
        )}

        {/* Active Speaking Indicator */}
        {isSpeaking && activeVoiceName && (
          <div className="bg-teal-50 border border-teal-200 text-teal-900 text-xs px-3.5 py-2 rounded-xl flex items-center space-x-2 text-left animate-pulse">
            <Volume2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
            <span>{isHindi ? `आवाज वाचन: ${activeVoiceName}` : `Speaking via: ${activeVoiceName}`}</span>
          </div>
        )}

        {/* Question Text */}
        <div className="space-y-2 text-left">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 leading-snug">
            {questionText}
          </h2>
          {questionHint && (
            <p className="text-sm text-slate-500 flex items-start space-x-1.5 pt-1">
              <span className="text-teal-600 font-bold">ℹ</span>
              <span>{questionHint}</span>
            </p>
          )}
        </div>

        {/* Quick Touch Options */}
        {options && options.length > 0 && (
          <div className="space-y-2 text-left pt-1">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block">
              {isHindi ? "त्वरित विकल्प (टच करें)" : "Quick Touch Options (Tap to Select)"}
            </span>
            <div className="flex flex-wrap gap-2">
              {options.map((opt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setCurrentAnswer(opt)}
                  className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition border ${
                    currentAnswer === opt
                      ? "bg-teal-600 text-white border-teal-600 shadow-sm"
                      : "bg-slate-50 hover:bg-teal-50 text-slate-700 hover:text-teal-900 border-slate-200"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            {/* Quick Non-Diagnostic Right-to-Decline Chips for AYUSH */}
            {session.history_mode === "ayush" && (
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100 mt-2">
                <button
                  type="button"
                  onClick={() => setCurrentAnswer(isHindi ? "मुझे नहीं पता / अनिश्चित" : "I don't know / Not sure")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    currentAnswer === (isHindi ? "मुझे नहीं पता / अनिश्चित" : "I don't know / Not sure")
                      ? "bg-slate-700 text-white border-slate-700 shadow-xs"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-300"
                  }`}
                >
                  ❓ {isHindi ? "मुझे नहीं पता / अनिश्चित" : "I don't know / Not sure"}
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentAnswer(isHindi ? "उत्तर नहीं देना चाहते" : "Prefer not to answer")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    currentAnswer === (isHindi ? "उत्तर नहीं देना चाहते" : "Prefer not to answer")
                      ? "bg-slate-700 text-white border-slate-700 shadow-xs"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-300"
                  }`}
                >
                  🛡️ {isHindi ? "उत्तर नहीं देना चाहते" : "Prefer not to answer"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Scale Widget (1 to 10) */}
        {currentQ.input_type === "scale" && (
          <div className="space-y-2 text-left pt-1">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block">
              {isHindi ? "गंभीरता स्तर (1 = हल्का, 10 = असहनीय)" : "Severity Scale (1 = Mild, 10 = Worst)"}
            </span>
            <div className="grid grid-cols-5 sm:grid-cols-10 gap-2">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setCurrentAnswer(String(num))}
                  className={`py-3 rounded-xl font-bold text-base transition border ${
                    currentAnswer === String(num)
                      ? "bg-teal-600 text-white border-teal-600 shadow-md scale-105"
                      : num <= 3
                      ? "bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100"
                      : num <= 6
                      ? "bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100"
                      : "bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100"
                  }`}
                >
                  {num}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Patient Voice Microphone Input Section (Phase 5 Fix) */}
        <div className="bg-gradient-to-br from-teal-50/90 via-slate-50 to-emerald-50/70 border-2 border-teal-300 rounded-2xl p-4 sm:p-5 space-y-3 text-left shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <span className={`w-2.5 h-2.5 rounded-full ${voiceState === "LISTENING" ? "bg-rose-600 animate-ping" : "bg-teal-600"}`} />
              <span className="text-xs font-bold uppercase tracking-wider text-teal-950">
                {isHindi ? "मरीज आवाज इनपुट (माइक)" : "Patient Voice Input (Microphone)"}
              </span>
            </div>

            {/* Language Switcher */}
            <div className="flex items-center space-x-1 bg-white border border-teal-200 p-1 rounded-xl shadow-xs">
              <span className="text-[11px] font-semibold text-slate-500 px-2 flex items-center space-x-1">
                <Languages className="w-3.5 h-3.5 text-teal-600" />
                <span>{isHindi ? "भाषा:" : "Lang:"}</span>
              </span>
              <button
                type="button"
                onClick={() => handleLanguageSwitch("en")}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                  selectedLanguage === "en"
                    ? "bg-teal-600 text-white shadow-xs"
                    : "text-slate-600 hover:text-teal-700 hover:bg-teal-50"
                }`}
              >
                English (en-IN)
              </button>
              <button
                type="button"
                onClick={() => handleLanguageSwitch("hi")}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                  selectedLanguage === "hi"
                    ? "bg-teal-600 text-white shadow-xs"
                    : "text-slate-600 hover:text-teal-700 hover:bg-teal-50"
                }`}
              >
                हिन्दी (hi-IN)
              </button>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            {/* Big Hospital Kiosk Microphone Button */}
            <button
              type="button"
              disabled={voiceState === "PROCESSING"}
              onClick={voiceState === "LISTENING" ? stopListening : startListening}
              className={`w-full sm:w-auto px-6 py-3.5 rounded-2xl font-bold text-sm sm:text-base flex items-center justify-center space-x-2.5 transition shadow ${
                voiceState === "LISTENING"
                  ? "bg-rose-600 hover:bg-rose-700 text-white animate-pulse ring-4 ring-rose-200"
                  : voiceState === "PROCESSING"
                  ? "bg-amber-600 text-white cursor-wait opacity-80"
                  : "bg-teal-600 hover:bg-teal-700 text-white shadow-teal-700/20"
              }`}
            >
              {voiceState === "LISTENING" ? (
                <>
                  <MicOff className="w-5 h-5 animate-bounce" />
                  <span>{isHindi ? "बोलना समाप्त करें (Tap to Stop)" : "🎙 Listening... Tap to Stop"}</span>
                </>
              ) : voiceState === "PROCESSING" ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>{isHindi ? "आवाज का विश्लेषण जारी..." : "Transcribing Audio..."}</span>
                </>
              ) : (
                <>
                  <Mic className="w-5 h-5" />
                  <span>{isHindi ? "बोलकर उत्तर दें (माइक दबाएं)" : "Tap to Speak your Answer"}</span>
                </>
              )}
            </button>

            {/* Listening Live Feedback */}
            <div className="text-xs text-slate-600 flex items-center space-x-2">
              {voiceState === "LISTENING" ? (
                <div className="flex items-center space-x-1.5 text-rose-600 font-bold">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-600 animate-ping" />
                  <span>{isHindi ? "माइक सक्रिय है... अपनी गति से पूरा वाक्य बोलें" : "Microphone active... Speak naturally in full sentences"}</span>
                </div>
              ) : (
                <span className="text-slate-500">
                  {isHindi
                    ? "माइक दबाकर बोलें। आप जितने चाहे वाक्य बोल सकते हैं।"
                    : "Tap mic, speak naturally. You can speak complete sentences without rushing."}
                </span>
              )}
            </div>
          </div>

          {/* Real-Time Interim Speech Display (while patient is actively speaking) */}
          {voiceState === "LISTENING" && interimPreview && (
            <div className="bg-amber-50/90 border border-amber-200 rounded-xl px-4 py-2.5 text-xs text-amber-900 flex items-start space-x-2">
              <span className="font-bold text-amber-700 flex-shrink-0">👂 {isHindi ? "सुना जा रहा है:" : "Hearing:"}</span>
              <span className="italic">"{interimPreview}..."</span>
            </div>
          )}

          {/* Voice Success / Guidance Banner */}
          {voiceStatusMessage && !voiceErrorMessage && (
            <div className="bg-white/95 border border-teal-300 rounded-xl px-3.5 py-2 text-xs text-teal-800 flex items-center space-x-2 shadow-xs">
              <CheckCircle2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
              <span>{voiceStatusMessage}</span>
            </div>
          )}

          {/* Voice Error Banner */}
          {voiceErrorMessage && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3.5 text-xs text-rose-800 flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-semibold">{voiceErrorMessage}</span>
                <p className="text-slate-600">
                  {isHindi
                    ? "वैकल्पिक रूप से: आप नीचे दिए गए बॉक्स में टाइप कर सकते हैं या त्वरित विकल्प टच कर सकते हैं।"
                    : "Voice recognition is temporarily unavailable. You can try again or type your answer below."}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Text Area Input */}
        <div className="space-y-2 text-left pt-1">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block">
              {isHindi ? "आपका उत्तर (समीक्षा / संपादन करें)" : "Your Response (Review / Edit below)"}
            </label>
            {wasVoiceInput && currentAnswer && (
              <span className="text-[11px] font-bold text-teal-700 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded-md flex items-center space-x-1">
                <Mic className="w-3 h-3 text-teal-600" />
                <span>{isHindi ? "आवाज से दर्ज (संपादनीय)" : "Spoken Answer (Editable)"}</span>
              </span>
            )}
          </div>
          <textarea
            rows={3}
            value={currentAnswer}
            onChange={(e) => setCurrentAnswer(e.target.value)}
            placeholder={
              isHindi
                ? "माइक दबाकर बोलें या यहां अपनी स्थिति के बारे में विस्तार से लिखें..."
                : "Speak via microphone or type your details here..."
            }
            className="w-full text-base p-4 border-2 border-slate-200 rounded-2xl focus:border-teal-600 focus:outline-none transition resize-none"
          />
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm p-3.5 rounded-xl flex items-start space-x-2 text-left">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-600 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Actions Toolbar */}
        <div className="space-y-3 pt-2">
          {/* Primary Submit Button */}
          <button
            type="button"
            disabled={savingAnswer}
            onClick={() => handleAnswerSubmit(currentAnswer)}
            className="w-full py-4 px-6 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-2xl font-bold text-base shadow-md flex items-center justify-center space-x-2 transition"
          >
            {savingAnswer ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>{isHindi ? "दर्ज किया जा रहा है..." : "Saving & Generating Next..."}</span>
              </>
            ) : (
              <>
                <span>{isHindi ? "उत्तर दर्ज करें और आगे बढ़ें" : "Submit Answer & Continue"}</span>
                <Send className="w-5 h-5" />
              </>
            )}
          </button>

          {/* Quick-Skip / Assist Buttons */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
            <button
              type="button"
              disabled={savingAnswer}
              onClick={() => handleAnswerSubmit(isHindi ? "मुझे नहीं पता" : "I don't know", true)}
              className="py-2.5 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center justify-center space-x-1 transition"
            >
              <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
              <span>{isHindi ? "मुझे नहीं पता" : "I don't know"}</span>
            </button>

            <button
              type="button"
              disabled={savingAnswer}
              onClick={() => handleAnswerSubmit(isHindi ? "उत्तर नहीं देना चाहते" : "Prefer not to answer", true)}
              className="py-2.5 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center justify-center space-x-1 transition"
            >
              <EyeOff className="w-3.5 h-3.5 text-slate-500" />
              <span>{isHindi ? "उत्तर नहीं देना" : "Prefer not to answer"}</span>
            </button>

            {session.answered_count >= 2 && (
              <button
                type="button"
                disabled={savingAnswer}
                onClick={() => handleCompleteInterview(session.session_id)}
                className="col-span-2 sm:col-span-1 py-2.5 px-3 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-xl text-xs font-bold flex items-center justify-center space-x-1 transition"
              >
                <Check className="w-3.5 h-3.5 text-amber-600" />
                <span>{isHindi ? "इंटरव्यू समाप्त करें" : "Finish Intake"}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function InterviewPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-2xl mx-auto py-16 text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
        </div>
      }
    >
      <InterviewComponent />
    </Suspense>
  );
}
