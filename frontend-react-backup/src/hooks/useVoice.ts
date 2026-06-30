import { useState, useEffect, useRef, useCallback } from "react";

// Tipos para Web Speech API (no incluidos en TS por defecto)
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
  readonly isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export type VoiceState = "idle" | "listening" | "processing" | "speaking";

export function useSpeechRecognition() {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  const finalTextRef = useRef("");
  const stateRef = useRef<VoiceState>("idle");

  // Mantener stateRef sincronizado
  const updateState = useCallback((s: VoiceState) => {
    stateRef.current = s;
    setState(s);
  }, []);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setSupported(!!SR);
  }, []);

  const start = useCallback((onFinal: (text: string) => void) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setError("Tu navegador no soporta reconocimiento de voz. Usa Chrome o Safari.");
      return;
    }

    onFinalRef.current = onFinal;
    finalTextRef.current = "";
    setError(null);
    setTranscript("");
    setInterim("");

    const rec = new SR();
    rec.lang = "es-ES";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => updateState("listening");

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }
      if (finalText) {
        finalTextRef.current = finalText;
        setTranscript(finalText);
        setInterim("");
      } else {
        setInterim(interimText);
      }
    };

    rec.onerror = (event: Event) => {
      const err = event as unknown as { error?: string };
      const isLocalhost = window.location.hostname === "localhost";
      const is127 = window.location.hostname === "127.0.0.1";
      if (err.error === "not-allowed" || err.error === "service-not-allowed") {
        setError("Permiso de micrófono denegado. Actívalo en el navegador.");
      } else if (err.error === "no-speech") {
        setError("No detecté audio. Intenta de nuevo.");
      } else if (err.error === "audio-capture") {
        setError("No se pudo acceder al micrófono. Verifica que esté conectado.");
      } else if (err.error === "network") {
        if (is127) {
          setError("Chrome bloquea voz en http://127.0.0.1. Usa http://localhost:8077 o cambia a modo Whisper.");
        } else if (!isLocalhost && window.location.protocol !== "https:") {
          setError("Web Speech API requiere HTTPS. Usa http://localhost:8077 o cambia a modo Whisper.");
        } else {
          setError("Speech API no responde. Voy a cambiar a modo Whisper automáticamente.");
        }
      } else if (err.error === "aborted") {
        // Cancelado por el usuario, no mostrar error
      } else {
        setError("Error en reconocimiento de voz: " + (err.error || "desconocido"));
      }
      updateState("idle");
    };

    rec.onend = () => {
      setInterim("");
      const text = finalTextRef.current.trim();
      const curState = stateRef.current;
      if (text && onFinalRef.current && curState === "listening") {
        updateState("processing");
        onFinalRef.current(text);
      } else if (curState === "listening") {
        updateState("idle");
      }
    };

    recognitionRef.current = rec;
    try {
      rec.start();
    } catch (e) {
      setError("No se pudo iniciar el micrófono. Intenta de nuevo.");
      updateState("idle");
    }
  }, [updateState]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    updateState("idle");
  }, [updateState]);

  const reset = useCallback(() => {
    updateState("idle");
    setTranscript("");
    setInterim("");
    setError(null);
    finalTextRef.current = "";
  }, [updateState]);

  return { state, setState: updateState, transcript, interim, supported, error, start, stop, reset };
}

export type TTSVoiceSettings = {
  rate: number;
  pitch: number;
  voiceURI: string | null;
  usePremium: boolean;
};

const TTS_STORAGE_KEY = "app_tts_settings";

function loadVoiceSettings(): TTSVoiceSettings {
  try {
    const raw = localStorage.getItem(TTS_STORAGE_KEY);
    if (raw) return { rate: 1.0, pitch: 1.0, voiceURI: null, usePremium: false, ...JSON.parse(raw) };
  } catch {
    // ignore
  }
  return { rate: 1.0, pitch: 1.0, voiceURI: null, usePremium: false };
}

function saveVoiceSettings(settings: TTSVoiceSettings) {
  localStorage.setItem(TTS_STORAGE_KEY, JSON.stringify(settings));
}

function escogerVozNativa(voices: SpeechSynthesisVoice[], preferURI: string | null): SpeechSynthesisVoice | null {
  if (preferURI) {
    const preferida = voices.find((v) => v.voiceURI === preferURI);
    if (preferida) return preferida;
  }
  // Preferir voces español de alta calidad (Chrome/Google) en orden
  const langOrder = ["es-419", "es-MX", "es-ES", "es-US", "es-CO", "es-AR", "es-CL", "es-PE", "es-"];
  for (const lang of langOrder) {
    const voz = voices.find((v) => v.lang.toLowerCase().startsWith(lang));
    if (voz) return voz;
  }
  return voices.find((v) => v.lang.startsWith("es")) || null;
}

export function useSpeechSynthesis() {
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [settings, setSettings] = useState<TTSVoiceSettings>(loadVoiceSettings());
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    if ("speechSynthesis" in window) {
      const load = () => setVoices(window.speechSynthesis.getVoices());
      load();
      window.speechSynthesis.onvoiceschanged = load;
    }
  }, []);

  const updateSettings = useCallback((patch: Partial<TTSVoiceSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveVoiceSettings(next);
      return next;
    });
  }, []);

  const speakNative = useCallback((texto: string, onEnd?: () => void) => {
    if (!("speechSynthesis" in window)) {
      onEnd?.();
      return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(texto);
    utterance.lang = "es-ES";
    utterance.rate = settings.rate;
    utterance.pitch = settings.pitch;

    const voz = escogerVozNativa(voices, settings.voiceURI);
    if (voz) utterance.voice = voz;

    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => {
      setSpeaking(false);
      onEnd?.();
    };
    utterance.onerror = () => {
      setSpeaking(false);
      onEnd?.();
    };

    window.speechSynthesis.speak(utterance);
  }, [voices, settings.rate, settings.pitch, settings.voiceURI]);

  const speakPremium = useCallback(async (texto: string, onEnd?: () => void) => {
    try {
      const res = await fetch("/api/voz/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      if (!res.ok) {
        // Fallback a nativa
        speakNative(texto, onEnd);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onplay = () => setSpeaking(true);
      audio.onended = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
        onEnd?.();
      };
      audio.onerror = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
        speakNative(texto, onEnd);
      };
      await audio.play();
    } catch {
      speakNative(texto, onEnd);
    }
  }, [speakNative]);

  const speak = useCallback((texto: string, onEnd?: () => void) => {
    if (settings.usePremium) {
      speakPremium(texto, onEnd);
    } else {
      speakNative(texto, onEnd);
    }
  }, [settings.usePremium, speakNative, speakPremium]);

  const cancel = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    audioRef.current?.pause();
    audioRef.current = null;
    setSpeaking(false);
  }, []);

  return { speaking, supported, voices, settings, updateSettings, speak, cancel };
}

export function useMediaRecorder() {
  const [recording, setRecording] = useState(false);
  const [supported, setSupported] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices);
  }, []);

  const startRecording = useCallback(async (): Promise<boolean> => {
    if (!navigator.mediaDevices || !window.MediaRecorder) return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
      return true;
    } catch (e) {
      console.error("Error accediendo al micrófono:", e);
      return false;
    }
  }, []);

  const stopRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder) {
        resolve(new Blob());
        return;
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        mediaRecorderRef.current = null;
        setRecording(false);
        resolve(blob);
      };

      recorder.stop();
    });
  }, []);

  const cancelRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    setRecording(false);
  }, []);

  return { recording, supported, startRecording, stopRecording, cancelRecording };
}
