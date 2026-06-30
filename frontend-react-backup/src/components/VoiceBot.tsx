import { useState, useCallback, useRef, useEffect } from "react";
import { Mic, Square, Volume2, Loader2, X, Bot, Settings2, Check, Pencil, Tag, AlignLeft, Clock, Repeat } from "lucide-react";
import { useSpeechRecognition, useSpeechSynthesis, useMediaRecorder } from "../hooks/useVoice";
import { api } from "../api";
import type { Tarea, TareaDraft } from "../types";
import { VoiceSettings } from "./VoiceSettings";

interface Props {
  onTareaCreada: (t: Tarea) => void;
}

type Mode = "auto" | "speech-api" | "media-recorder";

function isLocalhost(): boolean {
  if (typeof window === "undefined") return false;
  // Web Speech API de Chrome funciona en localhost y 0.0.0.0, pero NO en 127.0.0.1
  return window.location.hostname === "localhost" || window.location.hostname === "0.0.0.0";
}

export function VoiceBot({ onTareaCreada }: Props) {
  const { state, setState, transcript, interim, supported: srSupported, error: srError, start, stop, reset } = useSpeechRecognition();
  const { speaking, speak, cancel, voices, settings: ttsSettings, updateSettings: updateTtsSettings } = useSpeechSynthesis();
  const { supported: mrSupported, startRecording, stopRecording, cancelRecording } = useMediaRecorder();
  const [open, setOpen] = useState(false);
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);
  const [respuesta, setRespuesta] = useState("");
  const [ultimaTarea, setUltimaTarea] = useState<Tarea | null>(null);
  const [mode, setMode] = useState<Mode>("auto");
  const [fallbackMsg, setFallbackMsg] = useState("");
  const [transcriptDisplay, setTranscriptDisplay] = useState("");
  const [srFailed, setSrFailed] = useState(false);
  const [motor, setMotor] = useState<"local" | "groq" | null>(null);
  const [premiumTTS, setPremiumTTS] = useState(false);
  const [draft, setDraft] = useState<TareaDraft | null>(null);
  const [editingDraft, setEditingDraft] = useState(false);
  const [editDraft, setEditDraft] = useState<TareaDraft | null>(null);
  const recordingRef = useRef(false);
  const handleMicRef = useRef<() => Promise<void>>();

  const supported = srSupported || mrSupported;

  // En auto: localhost → Speech API, ngrok → Whisper (más confiable)
  const effectiveMode: "speech-api" | "media-recorder" =
    mode === "auto"
      ? (isLocalhost() && srSupported && !srFailed ? "speech-api" : "media-recorder")
      : mode === "speech-api" ? "speech-api" : "media-recorder";

  // Consultar config del backend al abrir
  useEffect(() => {
    if (open) {
      api.vozConfig()
        .then((cfg) => {
          if (cfg.groq) setMotor("groq");
          setPremiumTTS(cfg.tts_premium);
        })
        .catch(() => {
          setMotor(null);
          setPremiumTTS(false);
        });
    }
  }, [open]);

  const procesar = useCallback(async (texto: string) => {
    if (!texto.trim()) {
      setState("idle");
      return;
    }
    setTranscriptDisplay(texto);
    try {
      const res = await api.vozProcesar(texto);
      setRespuesta(res.mensaje);
      setDraft(res.draft || null);
      setEditDraft(res.draft ? { ...res.draft } : null);
      if (res.tarea_creada) {
        setUltimaTarea(res.tarea_creada);
        onTareaCreada(res.tarea_creada);
      }
      setState("speaking");
      speak(res.mensaje, () => setState("idle"));
    } catch (e) {
      console.error(e);
      setRespuesta("Ocurrió un error procesando tu mensaje.");
      setState("idle");
    }
  }, [onTareaCreada, speak, setState]);

  const confirmarDraft = useCallback(async () => {
    if (!draft) return;
    try {
      const res = await api.vozConfirmar(draft);
      if (res.tarea_creada) {
        setUltimaTarea(res.tarea_creada);
        onTareaCreada(res.tarea_creada);
        setRespuesta(`✅ Tarea creada: ${res.tarea_creada.titulo}`);
        setDraft(null);
        setEditDraft(null);
      } else {
        setRespuesta("No pude crear la tarea. Intenta de nuevo.");
      }
    } catch (e) {
      console.error(e);
      setRespuesta("Ocurrió un error al confirmar la tarea.");
    }
  }, [draft, onTareaCreada]);

  const guardarDraftEditado = useCallback(() => {
    if (!editDraft) return;
    setDraft(editDraft);
    setEditingDraft(false);
  }, [editDraft]);

  const procesarConMediaRecorder = useCallback(async () => {
    setState("processing");
    setFallbackMsg("Transcribiendo audio...");
    try {
      const blob = await stopRecording();
      recordingRef.current = false;
      if (blob.size === 0) {
        setFallbackMsg("No se grabó audio. Intenta de nuevo.");
        setState("idle");
        return;
      }
      const res = await api.vozTranscribir(blob);
      setTranscriptDisplay(res.texto);
      setMotor((res as { motor?: string }).motor as "groq" | "local" | null);
      setFallbackMsg("");
      await procesar(res.texto);
    } catch (e) {
      console.error("Error en MediaRecorder fallback:", e);
      setFallbackMsg("Error transcribiendo. Verifica que el servicio esté activo.");
      setState("idle");
    }
  }, [stopRecording, procesar, setState]);

  const handleMic = useCallback(async () => {
    if (recordingRef.current) {
      await procesarConMediaRecorder();
      return;
    }

    if (state === "listening") {
      stop();
      return;
    }
    if (state === "speaking") {
      cancel();
      setState("idle");
      return;
    }

    setRespuesta("");
    setUltimaTarea(null);
    setTranscriptDisplay("");
    setFallbackMsg("");

    // Usar modo efectivo (auto detecta localhost vs ngrok)
    if (effectiveMode === "media-recorder" && mrSupported) {
      const ok = await startRecording();
      if (ok) {
        recordingRef.current = true;
        setState("listening");
      } else {
        setFallbackMsg("No se pudo acceder al micrófono.");
      }
      return;
    }

    // Speech API
    start(procesar);
  }, [state, stop, cancel, start, procesar, effectiveMode, mrSupported, startRecording, setState, procesarConMediaRecorder]);

  // Sincronizar handleMic con la ref para el fallback automático
  useEffect(() => {
    handleMicRef.current = handleMic;
  }, [handleMic]);

  // Detectar error de red en Speech API y cambiar automáticamente a Whisper
  useEffect(() => {
    if (srError && (srError.includes("red") || srError.includes("network") || srError.includes("127.0.0.1") || srError.includes("HTTPS") || srError.includes("no responde"))) {
      setSrFailed(true);
      if (!recordingRef.current && mrSupported) {
        setFallbackMsg("Speech API falló. Cambiando a modo Whisper...");
        reset();
        setMode("media-recorder");
        setTimeout(() => {
          if (!recordingRef.current && handleMicRef.current) {
            handleMicRef.current();
          }
        }, 300);
      }
    }
  }, [srError, mrSupported, reset]);

  const pedirResumen = useCallback(async () => {
    setState("processing");
    try {
      const res = await api.vozResumen();
      setRespuesta(res.mensaje);
      setState("speaking");
      speak(res.mensaje, () => setState("idle"));
    } catch (e) {
      console.error(e);
      setRespuesta("No pude generar el resumen.");
      setState("idle");
    }
  }, [speak, setState]);

  if (!supported) {
    return (
      <div className="fixed bottom-20 right-4 z-40">
        <div className="bg-card border border-border rounded-xl p-3 text-xs text-muted max-w-[200px]">
          Tu navegador no soporta voz. Usa Chrome o Safari.
        </div>
      </div>
    );
  }

  const colorBoton =
    state === "listening" ? "bg-red-500 animate-pulse" :
    state === "processing" ? "bg-amber-500" :
    state === "speaking" ? "bg-blue-500" :
    "bg-accent";

  const isRecording = recordingRef.current && state === "listening";

  return (
    <>
      <div className="fixed bottom-20 right-4 z-40 flex flex-col items-end gap-2">
        {open && (
          <div className="bg-card border border-border rounded-2xl shadow-xl p-4 w-80 max-w-[calc(100vw-2rem)] animate-slide-up mb-2">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Bot size={16} className="text-accent" />
                <span className="text-sm font-semibold">Asistente de voz</span>
                {effectiveMode === "media-recorder" && motor && (
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${motor === "groq" ? "bg-cyan-500/20 text-cyan-300" : "bg-muted/20 text-muted"}`}>
                    {motor === "groq" ? "Groq" : "Local"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setShowVoiceSettings(!showVoiceSettings)}
                  className={`p-1.5 rounded-lg transition-colors ${showVoiceSettings ? "text-accent bg-accent/10" : "text-muted hover:text-text"}`}
                  aria-label="Ajustes de voz"
                >
                  <Settings2 size={16} />
                </button>
                <button onClick={() => {
                  setOpen(false);
                  setShowVoiceSettings(false);
                  cancel();
                  cancelRecording();
                  recordingRef.current = false;
                  reset();
                }} className="text-muted hover:text-text p-1">
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Ajustes de voz */}
            {showVoiceSettings && (
              <VoiceSettings
                voices={voices}
                settings={ttsSettings}
                onChange={updateTtsSettings}
                premiumAvailable={premiumTTS}
              />
            )}

            {/* Selector de modo */}
            <div className="mb-2 flex items-center gap-1">
              <span className="text-[9px] text-muted mr-1">Modo:</span>
              {(["auto", "speech-api", "media-recorder"] as const).map((m) => {
                const labels: Record<string, string> = { "auto": "Auto", "speech-api": "Speech API", "media-recorder": "Whisper" };
                const isActive = mode === m;
                const isEffective = effectiveMode === (m === "auto" ? effectiveMode : m);
                return (
                  <button
                    key={m}
                    onClick={() => { setMode(m); reset(); setSrFailed(false); }}
                    className={`text-[9px] px-1.5 py-0.5 rounded-full transition-colors ${
                      isActive
                        ? "bg-accent/30 text-accent font-semibold"
                        : isEffective
                        ? "bg-accent/10 text-accent/70"
                        : "bg-bg text-muted hover:text-text"
                    }`}
                  >
                    {labels[m]}
                  </button>
                );
              })}
            </div>

            {/* Estado */}
            <div className="mb-3">
              {state === "idle" && (
                <div className="text-center py-2">
                  <div className="flex items-center justify-center gap-1.5 mb-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${effectiveMode === "media-recorder" ? "bg-cyan-400" : "bg-green-400"}`} />
                    <span className="text-[9px] font-medium text-muted uppercase tracking-wide">
                      {effectiveMode === "media-recorder" ? "Modo Whisper" : "Modo Speech API"}
                    </span>
                  </div>
                  <p className="text-xs text-muted">
                    {effectiveMode === "media-recorder"
                      ? "Toca el micrófono, habla y toca de nuevo para transcribir."
                      : "Toca el micrófono y habla. Ej: 'Crear tarea: revisar correo' o '¿Cómo voy?'"}
                  </p>
                </div>
              )}
              {state === "listening" && (
                <div className="text-center py-2">
                  <div className="flex items-center justify-center gap-1 mb-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <p className="text-xs text-red-400">
                    {isRecording ? "Grabando... toca para detener" : "Escuchando..."}
                  </p>
                </div>
              )}
              {state === "processing" && (
                <div className="text-center py-2">
                  <Loader2 size={20} className="mx-auto animate-spin text-amber-400 mb-1" />
                  <p className="text-xs text-amber-400">{fallbackMsg || "Procesando..."}</p>
                </div>
              )}
              {state === "speaking" && (
                <div className="text-center py-2">
                  <Volume2 size={20} className="mx-auto text-blue-400 mb-1 animate-pulse" />
                  <p className="text-xs text-blue-400">Hablando...</p>
                </div>
              )}
            </div>

            {/* Transcript */}
            {(transcriptDisplay || transcript || interim) && (
              <div className="bg-bg rounded-xl p-3 mb-2">
                <div className="text-[10px] text-muted mb-1">Tú dijiste:</div>
                <p className="text-sm text-text">
                  {transcriptDisplay || transcript}<span className="text-muted">{interim}</span>
                </p>
              </div>
            )}

            {/* Respuesta del bot */}
            {respuesta && (
              <div className="bg-accent/10 border border-accent/20 rounded-xl p-3 mb-2">
                <div className="text-[10px] text-accent mb-1">Jarvis:</div>
                <p className="text-sm text-text">{respuesta}</p>
                {ultimaTarea && !draft && (
                  <div className="mt-2 pt-2 border-t border-accent/10">
                    <div className="text-[10px] text-muted">Tarea creada:</div>
                    <div className="text-xs font-medium text-accent">{ultimaTarea.titulo}</div>
                  </div>
                )}
              </div>
            )}

            {/* Borrador de tarea */}
            {draft && (
              <div className="bg-card border border-accent/30 rounded-xl p-3 mb-2 space-y-2">
                {editingDraft ? (
                  <div className="space-y-2">
                    <div>
                      <label className="text-[9px] text-muted uppercase">Título</label>
                      <input
                        className="w-full bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
                        value={editDraft?.titulo || ""}
                        onChange={(e) => setEditDraft((prev) => prev ? { ...prev, titulo: e.target.value } : null)}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] text-muted uppercase">Descripción</label>
                      <textarea
                        className="w-full bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text resize-none"
                        rows={2}
                        value={editDraft?.descripcion || ""}
                        onChange={(e) => setEditDraft((prev) => prev ? { ...prev, descripcion: e.target.value } : null)}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-muted uppercase">Tipo</label>
                        <select
                          className="w-full bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
                          value={editDraft?.etiqueta || "tarea"}
                          onChange={(e) => setEditDraft((prev) => prev ? { ...prev, etiqueta: e.target.value } : null)}
                        >
                          <option value="tarea">Tarea</option>
                          <option value="habito">Hábito</option>
                          <option value="emprendimiento">Emprendimiento</option>
                          <option value="investigacion">Investigación</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-muted uppercase">Prioridad</label>
                        <select
                          className="w-full bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
                          value={editDraft?.prioridad || "media"}
                          onChange={(e) => setEditDraft((prev) => prev ? { ...prev, prioridad: e.target.value as any } : null)}
                        >
                          <option value="alta">Alta</option>
                          <option value="media">Media</option>
                          <option value="baja">Baja</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={guardarDraftEditado} className="flex-1 bg-accent text-white rounded-lg py-1.5 text-[10px] font-medium flex items-center justify-center gap-1">
                        <Check size={10} /> Guardar
                      </button>
                      <button onClick={() => setEditingDraft(false)} className="flex-1 bg-bg border border-border text-muted rounded-lg py-1.5 text-[10px] font-medium">
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start gap-2">
                      <Tag size={12} className="text-accent mt-0.5" />
                      <div className="flex-1">
                        <div className="text-[10px] text-muted uppercase">Título</div>
                        <div className="text-sm font-medium text-text">{draft.titulo}</div>
                      </div>
                    </div>
                    {draft.descripcion && (
                      <div className="flex items-start gap-2">
                        <AlignLeft size={12} className="text-muted mt-0.5" />
                        <div className="text-[10px] text-muted">{draft.descripcion}</div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[9px] font-medium capitalize">{draft.etiqueta}</span>
                      <span className="px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-300 text-[9px] font-medium capitalize">{draft.prioridad}</span>
                      {draft.horas.length > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 text-[9px] font-medium flex items-center gap-1">
                          <Clock size={8} /> {draft.horas.join(", ")}
                        </span>
                      )}
                      {draft.repetible && (
                        <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-300 text-[9px] font-medium flex items-center gap-1">
                          <Repeat size={8} /> {draft.dias_semana.join(", ") || "repetible"}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button onClick={confirmarDraft} className="flex-1 bg-accent text-white rounded-lg py-1.5 text-[10px] font-medium flex items-center justify-center gap-1">
                        <Check size={10} /> Crear
                      </button>
                      <button onClick={() => setEditingDraft(true)} className="flex-1 bg-bg border border-border text-text rounded-lg py-1.5 text-[10px] font-medium flex items-center justify-center gap-1">
                        <Pencil size={10} /> Editar
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Error */}
            {srError && effectiveMode !== "media-recorder" && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-2 mb-2">
                <p className="text-xs text-red-400">{srError}</p>
                {mrSupported && (
                  <button
                    onClick={() => {
                      setMode("media-recorder");
                      setSrFailed(true);
                      reset();
                    }}
                    className="text-[10px] text-cyan-400 hover:underline mt-1"
                  >
                    Cambiar a modo Whisper
                  </button>
                )}
              </div>
            )}

            {/* Botones de acción rápida */}
            <div className="flex gap-2 mb-3">
              <button
                onClick={pedirResumen}
                disabled={state !== "idle"}
                className="flex-1 bg-bg border border-border rounded-lg py-2 text-xs text-muted hover:text-text disabled:opacity-40 transition-colors"
              >
                ¿Cómo voy?
              </button>
            </div>

            {/* Botón micrófono grande */}
            <div className="flex justify-center">
              <button
                onClick={handleMic}
                className={`w-14 h-14 rounded-full ${colorBoton} text-white flex items-center justify-center shadow-lg transition-all hover:scale-105`}
              >
                {state === "listening" ? <Square size={20} /> :
                 state === "processing" ? <Loader2 size={20} className="animate-spin" /> :
                 state === "speaking" ? <Volume2 size={20} /> :
                 <Mic size={22} />}
              </button>
            </div>
          </div>
        )}

        {/* Botón flotante para abrir/cerrar */}
        <button
          onClick={() => setOpen(!open)}
          className={`w-12 h-12 rounded-full ${open ? "bg-card border border-border" : colorBoton} text-white flex items-center justify-center shadow-lg transition-all hover:scale-105`}
        >
          {open ? <X size={20} /> : <Mic size={20} />}
        </button>
      </div>
    </>
  );
}
