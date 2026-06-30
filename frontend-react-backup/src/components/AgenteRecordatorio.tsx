import { useState, useEffect, useCallback, useRef } from "react";
import { Bot, X, AlertCircle, TrendingUp, Lightbulb, Newspaper, ChevronDown, ChevronUp, MessageCircle, Volume2, Bell, BellOff, Send, Mic, Loader2, Check, Pencil, Calendar, Tag, AlignLeft, Clock, Repeat, Users, Brain, Save, Search } from "lucide-react";
import type { AgenteResumen, AgenteCheckin, TareaDraft, Tarea, MemoriaResultado } from "../types";
import { api } from "../api";
import { useSpeechSynthesis, useSpeechRecognition } from "../hooks/useVoice";
import { AgentesEspecializados } from "./AgentesEspecializados";

type Seccion = "status" | "estancadas" | "ideas" | "noticias" | "checkin" | "agentes" | "memoria";

type ChatMsg = { role: "agent" | "user"; text: string; time: string; draft?: TareaDraft; draftId?: string };

export function AgenteRecordatorio({ onTareaCreada }: { onTareaCreada: (t: Tarea) => void }) {
  const [resumen, setResumen] = useState<AgenteResumen | null>(null);
  const [checkin, setCheckin] = useState<AgenteCheckin | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [seccion, setSeccion] = useState<Seccion>("status");
  const [notifEnabled, setNotifEnabled] = useState(false);
  const { speak, speaking } = useSpeechSynthesis();
  const { state: vozState, start, stop, supported } = useSpeechRecognition();
  const checkinNotified = useRef(false);
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<TareaDraft | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const draftCounter = useRef(0);

  // Memoria vectorial
  const [memoriaPregunta, setMemoriaPregunta] = useState("");
  const [memoriaRespuesta, setMemoriaRespuesta] = useState("");
  const [memoriaFuentes, setMemoriaFuentes] = useState<MemoriaResultado[]>([]);
  const [memoriaLoading, setMemoriaLoading] = useState(false);
  const [memoriaGuardarTexto, setMemoriaGuardarTexto] = useState("");
  const [memoriaGuardarLoading, setMemoriaGuardarLoading] = useState(false);
  const [memoriaStats, setMemoriaStats] = useState<{ total_registros: number; ruta: string } | null>(null);

  const escuchando = vozState === "listening";
  const procesandoVoz = vozState === "processing";

  const cargar = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([api.agenteRecordatorio(), api.agenteCheckin()]);
      setResumen(r);
      setCheckin(c);

      // Mensajes iniciales del chat
      const now = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
      const nuevos: ChatMsg[] = [];
      if (c) {
        nuevos.push({ role: "agent", text: `${c.mensaje} ${c.preguntas[0] || ""}`, time: now });
      }
      if (r) {
        nuevos.push({ role: "agent", text: `${r.titulo}. Tienes ${r.total} pendientes, ${r.vencidas} vencidas.`, time: now });
      }
      setChat((prev) => (prev.length === 0 ? nuevos : prev));

      // Notificación proactiva una vez por sesión
      if ("Notification" in window && Notification.permission === "granted" && c && !checkinNotified.current) {
        checkinNotified.current = true;
        new Notification(c.titulo, {
          body: c.mensaje,
          tag: "agente-checkin",
          requireInteraction: false,
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if ("Notification" in window) {
      setNotifEnabled(Notification.permission === "granted");
    }
    cargar();
    const id = setInterval(cargar, 60000);
    return () => clearInterval(id);
  }, [cargar]);

  const pedirPermisoNotificaciones = async () => {
    if (!("Notification" in window)) return;
    const perm = await Notification.requestPermission();
    setNotifEnabled(perm === "granted");
  };

  const hablar = (texto: string) => {
    speak(texto);
  };

  const cargarStatsMemoria = useCallback(async () => {
    try {
      const stats = await api.statsMemoria();
      setMemoriaStats(stats);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const preguntarMemoria = useCallback(async (pregunta: string) => {
    if (!pregunta.trim()) return;
    setMemoriaLoading(true);
    setMemoriaRespuesta("");
    setMemoriaFuentes([]);
    try {
      const res = await api.agentePreguntar(pregunta.trim(), 5);
      setMemoriaRespuesta(res.respuesta);
      setMemoriaFuentes(res.fuentes);
    } catch (e) {
      console.error(e);
      setMemoriaRespuesta("No pude consultar la memoria. Revisa que el backend tenga acceso a embeddings.");
    } finally {
      setMemoriaLoading(false);
    }
  }, []);

  const guardarMemoria = useCallback(async () => {
    if (!memoriaGuardarTexto.trim()) return;
    setMemoriaGuardarLoading(true);
    try {
      await api.crearMemoria(memoriaGuardarTexto.trim(), "manual");
      setMemoriaGuardarTexto("");
      await cargarStatsMemoria();
    } catch (e) {
      console.error(e);
    } finally {
      setMemoriaGuardarLoading(false);
    }
  }, [memoriaGuardarTexto, cargarStatsMemoria]);

  const syncTareasMemoria = useCallback(async () => {
    setMemoriaGuardarLoading(true);
    try {
      await api.syncTareasMemoria();
      await cargarStatsMemoria();
    } catch (e) {
      console.error(e);
    } finally {
      setMemoriaGuardarLoading(false);
    }
  }, [cargarStatsMemoria]);

  const enviarChat = useCallback(async (texto: string) => {
    if (!texto.trim()) return;
    const now = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    setChat((prev) => [...prev, { role: "user", text: texto.trim(), time: now }]);
    setChatInput("");
    setChatLoading(true);
    try {
      const res = await api.vozProcesar(texto.trim());
      const respuesta = res.mensaje || "No entendí bien, ¿puedes repetirlo?";
      const draftId = res.draft ? `draft-${++draftCounter.current}` : undefined;
      setChat((prev) => [...prev, {
        role: "agent",
        text: respuesta,
        time: new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }),
        draft: res.draft || undefined,
        draftId,
      }]);
      if (res.draft && res.draft.titulo) {
        hablar(`Voy a crear un borrador: ${res.draft.titulo}. Revísalo y confirma si está correcto.`);
      }
    } catch (e) {
      console.error(e);
      setChat((prev) => [...prev, { role: "agent", text: "Ocurrió un error al procesar tu mensaje.", time: new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }, []);

  const confirmarDraft = useCallback(async (draft: TareaDraft) => {
    try {
      const res = await api.vozConfirmar(draft);
      if (res.tarea_creada) {
        setChat((prev) => [...prev, { role: "agent", text: `✅ Tarea creada: **${res.tarea_creada?.titulo}**`, time: new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) }]);
        hablar(`Tarea creada: ${res.tarea_creada?.titulo}`);
      } else {
        setChat((prev) => [...prev, { role: "agent", text: "No pude crear la tarea. Intenta de nuevo.", time: new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) }]);
      }
    } catch (e) {
      console.error(e);
      setChat((prev) => [...prev, { role: "agent", text: "Ocurrió un error al confirmar la tarea.", time: new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) }]);
    }
  }, []);

  const empezarEditarDraft = useCallback((draftId: string, draft: TareaDraft) => {
    setEditingDraftId(draftId);
    setEditDraft({ ...draft });
  }, []);

  const guardarDraftEditado = useCallback(() => {
    if (!editingDraftId || !editDraft) return;
    setChat((prev) => prev.map((m) => m.draftId === editingDraftId ? { ...m, draft: editDraft } : m));
    setEditingDraftId(null);
    setEditDraft(null);
  }, [editingDraftId, editDraft]);

  const cancelarEdicionDraft = useCallback(() => {
    setEditingDraftId(null);
    setEditDraft(null);
  }, []);

  const toggleChatVoz = useCallback(() => {
    if (escuchando) {
      stop();
    } else {
      start((texto) => enviarChat(texto));
    }
  }, [escuchando, start, stop, enviarChat]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  useEffect(() => {
    if (seccion === "memoria" && open) {
      cargarStatsMemoria();
    }
  }, [seccion, open, cargarStatsMemoria]);

  if (loading || !resumen) return null;

  const tienePendientes = resumen.total > 0;
  const tieneEstancadas = resumen.estancadas.length > 0;
  const tieneIdeas = resumen.ideas.length > 0;
  const tieneNoticias = resumen.noticias.length > 0;

  const secciones: { key: Seccion; label: string; icon: typeof Bot; count: number; color: string }[] = [
    { key: "status", label: "Status", icon: TrendingUp, count: resumen.total, color: "text-blue-400" },
    { key: "estancadas", label: "Estancadas", icon: AlertCircle, count: resumen.estancadas.length, color: "text-red-400" },
    { key: "ideas", label: "Ideas", icon: Lightbulb, count: resumen.ideas.length, color: "text-amber-400" },
    { key: "noticias", label: "Noticias", icon: Newspaper, count: resumen.noticias.length, color: "text-cyan-400" },
    { key: "checkin", label: "Check-in", icon: MessageCircle, count: checkin?.preguntas.length || 0, color: "text-accent" },
    { key: "agentes", label: "Agentes", icon: Users, count: 0, color: "text-purple-400" },
    { key: "memoria", label: "Memoria", icon: Brain, count: 0, color: "text-emerald-400" },
  ];

  return (
    <>
      {/* Panel superior izquierdo */}
      <div className="fixed top-4 left-4 z-40 max-w-xs sm:max-w-sm">
        {/* Botón del agente */}
        <button
          onClick={() => setOpen(!open)}
          className={`flex items-center gap-2 px-3 py-2 rounded-xl shadow-lg border transition-all hover:scale-105 ${
            resumen.vencidas > 0
              ? "bg-red-500/20 border-red-500/50 text-red-300"
              : tienePendientes
              ? "bg-card border-accent/50 text-accent"
              : "bg-green-500/20 border-green-500/50 text-green-300"
          }`}
        >
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
            resumen.vencidas > 0 ? "bg-red-500/30" : tienePendientes ? "bg-accent/30" : "bg-green-500/30"
          }`}>
            <Bot size={16} />
          </div>
          <div className="text-left">
            <div className="text-xs font-semibold">Agente</div>
            <div className="text-[10px] opacity-80">{resumen.titulo}</div>
          </div>
          {resumen.vencidas > 0 && (
            <span className="ml-1 w-5 h-5 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              {resumen.vencidas}
            </span>
          )}
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {/* Panel expandible */}
        {open && (
          <div className="mt-2 bg-card border border-border rounded-2xl shadow-xl overflow-hidden animate-slide-up">
            {/* Header con acciones */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-bg/50">
              <span className="text-[10px] text-muted font-medium uppercase tracking-wide">Jarvis</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => checkin && hablar(`${checkin.mensaje}. ${checkin.preguntas.join(" ")}`)}
                  disabled={speaking || !checkin}
                  className={`p-1.5 rounded-lg transition-colors ${speaking ? "text-accent animate-pulse" : "text-muted hover:text-accent"}`}
                  title="Escuchar mensaje"
                >
                  <Volume2 size={14} />
                </button>
                <button
                  onClick={pedirPermisoNotificaciones}
                  className={`p-1.5 rounded-lg transition-colors ${notifEnabled ? "text-accent" : "text-muted hover:text-accent"}`}
                  title={notifEnabled ? "Notificaciones activas" : "Activar notificaciones"}
                >
                  {notifEnabled ? <Bell size={14} /> : <BellOff size={14} />}
                </button>
              </div>
            </div>

            {/* Tabs de secciones */}
            <div className="flex border-b border-border">
              {secciones.map(({ key, label, icon: Icon, count, color }) => (
                <button
                  key={key}
                  onClick={() => setSeccion(key)}
                  className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-1 transition-colors relative ${
                    seccion === key ? "bg-bg" : "hover:bg-bg/50"
                  }`}
                >
                  <Icon size={14} className={seccion === key ? color : "text-muted"} />
                  <span className={`text-[9px] font-medium ${seccion === key ? color : "text-muted"}`}>{label}</span>
                  {count > 0 && (
                    <span className={`text-[8px] px-1 rounded-full ${seccion === key ? color + " bg-current/10" : "text-muted"}`}>
                      {count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Contenido de la sección */}
            <div className="p-3 max-h-[60vh] overflow-y-auto">
              {/* STATUS */}
              {seccion === "status" && (
                <div className="space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-bg rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-blue-400">{resumen.total}</div>
                      <div className="text-[9px] text-muted">Pendientes</div>
                    </div>
                    <div className="bg-bg rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-amber-400">{resumen.en_progreso}</div>
                      <div className="text-[9px] text-muted">En progreso</div>
                    </div>
                    <div className="bg-bg rounded-lg p-2 text-center">
                      <div className="text-lg font-bold text-red-400">{resumen.vencidas}</div>
                      <div className="text-[9px] text-muted">Vencidas</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
                      <div className="text-sm font-bold text-red-400">{resumen.alta}</div>
                      <div className="text-[9px] text-muted">Alta</div>
                    </div>
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 text-center">
                      <div className="text-sm font-bold text-amber-400">{resumen.media}</div>
                      <div className="text-[9px] text-muted">Media</div>
                    </div>
                    <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-2 text-center">
                      <div className="text-sm font-bold text-green-400">{resumen.baja}</div>
                      <div className="text-[9px] text-muted">Baja</div>
                    </div>
                  </div>
                  {resumen.tareas.length > 0 && (
                    <div className="pt-2">
                      <h4 className="text-[10px] font-semibold text-muted uppercase tracking-wide mb-1.5">Prioritarias</h4>
                      {resumen.tareas.map((t) => (
                        <div key={t.id} className={`flex items-center gap-2 py-1.5 px-2 rounded-lg mb-1 ${t.vencida ? "bg-red-500/5" : ""}`}>
                          {t.vencida && <AlertCircle size={12} className="text-red-400 min-w-3" />}
                          <span className="text-xs flex-1 truncate">{t.titulo}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                            t.prioridad === "alta" ? "bg-red-500/15 text-red-400" :
                            t.prioridad === "media" ? "bg-amber-500/15 text-amber-400" :
                            "bg-green-500/15 text-green-400"
                          }`}>{t.prioridad}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ESTANCADAS */}
              {seccion === "estancadas" && (
                <div className="space-y-2">
                  {tieneEstancadas ? (
                    resumen.estancadas.map((t) => (
                      <div key={t.id} className="bg-red-500/5 border border-red-500/20 rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <AlertCircle size={14} className="text-red-400" />
                          <span className="text-xs font-semibold flex-1 truncate">{t.titulo}</span>
                          <span className="text-[10px] font-bold text-red-400">{t.dias}d</span>
                        </div>
                        {t.descripcion && <p className="text-[10px] text-muted mb-1">{t.descripcion}</p>}
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-bg rounded-full h-1.5 overflow-hidden">
                            <div className="bg-red-500 h-full rounded-full" style={{ width: `${t.progreso}%` }} />
                          </div>
                          <span className="text-[10px] text-muted">{t.progreso}%</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-6">
                      <div className="text-2xl mb-1">✅</div>
                      <p className="text-xs text-muted">No tienes tareas estancadas</p>
                    </div>
                  )}
                </div>
              )}

              {/* IDEAS */}
              {seccion === "ideas" && (
                <div className="space-y-2">
                  {tieneIdeas ? (
                    resumen.ideas.map((idea) => (
                      <div key={idea.tarea_id} className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-1">
                          <Lightbulb size={14} className="text-amber-400" />
                          <span className="text-xs font-semibold flex-1 truncate">{idea.titulo}</span>
                          <span className="text-[10px] text-amber-400">{idea.progreso}%</span>
                        </div>
                        <p className="text-[10px] text-muted">{idea.sugerencia}</p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-6">
                      <Lightbulb size={24} className="mx-auto mb-2 text-muted opacity-40" />
                      <p className="text-xs text-muted">No tienes proyectos de emprendimiento activos</p>
                    </div>
                  )}
                </div>
              )}

              {/* CHECK-IN / CHAT */}
              {seccion === "checkin" && checkin && (
                <div className="space-y-3">
                  {/* Burbujas de chat */}
                  <div className="bg-bg rounded-xl p-2 max-h-[40vh] overflow-y-auto space-y-2">
                    {chat.length === 0 && (
                      <div className="text-center text-xs text-muted py-4">
                        <MessageCircle size={20} className="mx-auto mb-1 opacity-40" />
                        <p>Empieza a chatear con el agente</p>
                      </div>
                    )}
                    {chat.map((m, i) => {
                      const isEditing = m.draftId && m.draftId === editingDraftId && editDraft;
                      return (
                        <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                          <div className={`max-w-[90%] ${m.role === "user" ? "bg-accent text-white rounded-br-md" : "bg-card border border-border text-text rounded-bl-md"} rounded-2xl px-3 py-2 text-xs leading-relaxed`}>
                            <p>{m.text}</p>
                            <span className={`block text-[9px] mt-1 ${m.role === "user" ? "text-white/70" : "text-muted"}`}>{m.time}</span>

                            {/* Tarjeta de borrador de tarea */}
                            {m.draft && (
                              <div className="mt-2 bg-bg border border-accent/20 rounded-xl p-2.5 space-y-2">
                                {isEditing ? (
                                  <div className="space-y-2">
                                    <div>
                                      <label className="text-[9px] text-muted uppercase">Título</label>
                                      <input
                                        className="w-full bg-card border border-border rounded-lg px-2 py-1 text-xs text-text"
                                        value={editDraft?.titulo || ""}
                                        onChange={(e) => setEditDraft((prev) => prev ? { ...prev, titulo: e.target.value } : null)}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-[9px] text-muted uppercase">Descripción</label>
                                      <textarea
                                        className="w-full bg-card border border-border rounded-lg px-2 py-1 text-xs text-text resize-none"
                                        rows={2}
                                        value={editDraft?.descripcion || ""}
                                        onChange={(e) => setEditDraft((prev) => prev ? { ...prev, descripcion: e.target.value } : null)}
                                      />
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                      <div>
                                        <label className="text-[9px] text-muted uppercase">Tipo</label>
                                        <select
                                          className="w-full bg-card border border-border rounded-lg px-2 py-1 text-xs text-text"
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
                                          className="w-full bg-card border border-border rounded-lg px-2 py-1 text-xs text-text"
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
                                      <button onClick={cancelarEdicionDraft} className="flex-1 bg-card border border-border text-muted rounded-lg py-1.5 text-[10px] font-medium">
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
                                        <div className="text-sm font-medium text-text">{m.draft.titulo}</div>
                                      </div>
                                    </div>
                                    {m.draft.descripcion && (
                                      <div className="flex items-start gap-2">
                                        <AlignLeft size={12} className="text-muted mt-0.5" />
                                        <div className="text-[10px] text-muted">{m.draft.descripcion}</div>
                                      </div>
                                    )}
                                    <div className="flex flex-wrap gap-2">
                                      <span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[9px] font-medium capitalize">{m.draft.etiqueta}</span>
                                      <span className="px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-300 text-[9px] font-medium capitalize">{m.draft.prioridad}</span>
                                      {m.draft.horas.length > 0 && (
                                        <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 text-[9px] font-medium flex items-center gap-1">
                                          <Clock size={8} /> {m.draft.horas.join(", ")}
                                        </span>
                                      )}
                                      {m.draft.repetible && (
                                        <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-300 text-[9px] font-medium flex items-center gap-1">
                                          <Repeat size={8} /> {m.draft.dias_semana.join(", ") || "repetible"}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex gap-2">
                                      <button onClick={() => confirmarDraft(m.draft!)} className="flex-1 bg-accent text-white rounded-lg py-1.5 text-[10px] font-medium flex items-center justify-center gap-1">
                                        <Check size={10} /> Crear
                                      </button>
                                      <button onClick={() => empezarEditarDraft(m.draftId!, m.draft!)} className="flex-1 bg-card border border-border text-text rounded-lg py-1.5 text-[10px] font-medium flex items-center justify-center gap-1">
                                        <Pencil size={10} /> Editar
                                      </button>
                                    </div>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                    {chatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-card border border-border rounded-2xl rounded-bl-md px-3 py-2 text-xs text-muted flex items-center gap-2">
                          <Loader2 size={12} className="animate-spin" />
                          Pensando...
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Input de chat */}
                  <div className="relative">
                    <input
                      className="w-full bg-bg border border-border rounded-xl pl-3 pr-20 py-2.5 text-xs text-text placeholder-muted"
                      placeholder="Escribe o habla con el agente..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && enviarChat(chatInput)}
                    />
                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                      <button
                        onClick={toggleChatVoz}
                        disabled={!supported || procesandoVoz}
                        className={`p-1.5 rounded-lg transition-colors ${
                          escuchando ? "bg-green-500 text-white animate-pulse" : "text-muted hover:text-accent"
                        }`}
                        title={escuchando ? "Detener" : "Hablar"}
                      >
                        {procesandoVoz ? <Loader2 size={14} className="animate-spin" /> : <Mic size={14} />}
                      </button>
                      <button
                        onClick={() => enviarChat(chatInput)}
                        disabled={!chatInput.trim() || chatLoading}
                        className="p-1.5 rounded-lg text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
                      >
                        <Send size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Preguntas rápidas */}
                  <div>
                    <h4 className="text-[10px] font-semibold text-muted uppercase tracking-wide mb-2">Preguntas para ti</h4>
                    <div className="space-y-2">
                      {checkin.preguntas.map((p, i) => (
                        <button
                          key={i}
                          onClick={() => { enviarChat(p); hablar(p); }}
                          className="w-full flex items-center gap-2 text-left px-3 py-2 rounded-xl bg-bg hover:bg-accent/10 transition-colors group"
                        >
                          <MessageCircle size={12} className="text-accent min-w-3" />
                          <span className="text-xs text-text flex-1">{p}</span>
                          <Volume2 size={12} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* NOTICIAS */}
              {seccion === "noticias" && (
                <div className="space-y-2">
                  {tieneNoticias ? (
                    resumen.noticias.map((n) => (
                      <div key={n.tarea_id} className="bg-cyan-500/5 border border-cyan-500/20 rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-1.5">
                          <Newspaper size={14} className="text-cyan-400" />
                          <span className="text-xs font-semibold flex-1 truncate">{n.titulo}</span>
                        </div>
                        {n.temas.map((tema, i) => (
                          <div key={i} className="text-[10px] text-muted flex items-start gap-1 mb-1">
                            <span className="text-cyan-400 mt-0.5">→</span>
                            <span>{tema}</span>
                          </div>
                        ))}
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-6">
                      <Newspaper size={24} className="mx-auto mb-2 text-muted opacity-40" />
                      <p className="text-xs text-muted">No tienes tareas de investigación activas</p>
                    </div>
                  )}
                </div>
              )}

              {/* AGENTES ESPECIALIZADOS */}
              {seccion === "agentes" && (
                <AgentesEspecializados onTareaCreada={onTareaCreada} />
              )}

              {/* MEMORIA VECTORIAL */}
              {seccion === "memoria" && (
                <div className="space-y-3">
                  {/* Preguntar al agente */}
                  <div className="bg-bg rounded-xl p-3 space-y-2">
                    <h4 className="text-[10px] font-semibold text-muted uppercase tracking-wide flex items-center gap-1">
                      <Brain size={12} className="text-emerald-400" /> Preguntar sobre mi conocimiento
                    </h4>
                    <div className="relative">
                      <input
                        className="w-full bg-card border border-border rounded-xl pl-3 pr-20 py-2.5 text-xs text-text placeholder-muted"
                        placeholder="¿Qué proyectos tengo pendientes? ¿Cuáles son mis objetivos?"
                        value={memoriaPregunta}
                        onChange={(e) => setMemoriaPregunta(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && preguntarMemoria(memoriaPregunta)}
                      />
                      <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                        <button
                          onClick={() => preguntarMemoria(memoriaPregunta)}
                          disabled={!memoriaPregunta.trim() || memoriaLoading}
                          className="p-1.5 rounded-lg text-emerald-400 hover:bg-emerald-400/10 transition-colors disabled:opacity-50"
                          title="Preguntar"
                        >
                          {memoriaLoading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                        </button>
                      </div>
                    </div>
                    {memoriaRespuesta && (
                      <div className="bg-card border border-border rounded-xl p-3 text-xs leading-relaxed space-y-2">
                        <p>{memoriaRespuesta}</p>
                        {memoriaFuentes.length > 0 && (
                          <div className="pt-2 border-t border-border">
                            <span className="text-[9px] text-muted uppercase">Fuentes</span>
                            <div className="mt-1 space-y-1">
                              {memoriaFuentes.map((f, i) => (
                                <div key={i} className="text-[10px] text-muted truncate" title={f.text}>
                                  [{i + 1}] {f.source}: {f.text}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Guardar anotación */}
                  <div className="bg-bg rounded-xl p-3 space-y-2">
                    <h4 className="text-[10px] font-semibold text-muted uppercase tracking-wide flex items-center gap-1">
                      <Save size={12} className="text-accent" /> Guardar anotación
                    </h4>
                    <textarea
                      className="w-full bg-card border border-border rounded-xl px-3 py-2 text-xs text-text placeholder-muted resize-none"
                      rows={3}
                      placeholder="Escribe aquí una nota, idea o información que quieras recordar..."
                      value={memoriaGuardarTexto}
                      onChange={(e) => setMemoriaGuardarTexto(e.target.value)}
                    />
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-muted">
                        {memoriaStats ? `${memoriaStats.total_registros} fragmentos indexados` : "Cargando..."}
                      </span>
                      <div className="flex gap-2">
                        <button
                          onClick={syncTareasMemoria}
                          disabled={memoriaGuardarLoading}
                          className="px-2 py-1.5 rounded-lg bg-card border border-border text-[10px] text-muted hover:text-text transition-colors"
                        >
                          Sync tareas
                        </button>
                        <button
                          onClick={guardarMemoria}
                          disabled={!memoriaGuardarTexto.trim() || memoriaGuardarLoading}
                          className="px-3 py-1.5 rounded-lg bg-accent text-white text-[10px] font-medium flex items-center gap-1 disabled:opacity-50"
                        >
                          {memoriaGuardarLoading ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                          Guardar
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <button
              className="w-full bg-bg border-t border-border py-2 text-[10px] text-muted hover:text-text transition-colors"
              onClick={() => setOpen(false)}
            >
              Cerrar
            </button>
          </div>
        )}
      </div>
    </>
  );
}
