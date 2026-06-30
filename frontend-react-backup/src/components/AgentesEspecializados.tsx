import { useState, useCallback, useEffect, useRef } from "react";
import { Target, Search, Sparkles, BookOpen, Briefcase, GraduationCap, Lightbulb, Plus, Loader2, ExternalLink, Check, Mic, FileText, FlaskConical } from "lucide-react";
import type { Tarea, TareaDraft, AgentePlanResultado, AgenteBuscarResultado } from "../types";
import { api } from "../api";
import { useSpeechRecognition } from "../hooks/useVoice";
import { DocumentoModal } from "./DocumentoModal";

interface Props {
  onTareaCreada: (t: Tarea) => void;
}

const OBJETIVOS_COMUNES = [
  { icon: GraduationCap, label: "Maestría / Estudio", ejemplo: "Preparar admisión a maestría en IA" },
  { icon: Briefcase, label: "Nuevo trabajo", ejemplo: "Prepararme para entrevista de trabajo en backend" },
  { icon: Lightbulb, label: "Proyecto / Idea", ejemplo: "Lanzar landing page para TREAS" },
  { icon: BookOpen, label: "Investigación", ejemplo: "Aprender sobre agentes LLM" },
];

export function AgentesEspecializados({ onTareaCreada }: Props) {
  const [objetivo, setObjetivo] = useState("");
  const [semanas, setSemanas] = useState(4);
  const [plan, setPlan] = useState<AgentePlanResultado | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [temaBuscar, setTemaBuscar] = useState("");
  const [busqueda, setBusqueda] = useState<AgenteBuscarResultado | null>(null);
  const [buscarLoading, setBuscarLoading] = useState(false);
  const [creadas, setCreadas] = useState<Set<number>>(new Set());

  // Validación de ideas con investigación profunda
  const [ideaPrompt, setIdeaPrompt] = useState("");
  const [ideaLoading, setIdeaLoading] = useState(false);
  const [ideaCreada, setIdeaCreada] = useState<Tarea | null>(null);
  const [ideaError, setIdeaError] = useState<string | null>(null);
  const [verInforme, setVerInforme] = useState(false);
  const ideaRef = useRef<HTMLTextAreaElement>(null);
  const { state: vozState, start, stop, supported } = useSpeechRecognition();
  const escuchando = vozState === "listening";

  // Auto-crecer del textarea
  useEffect(() => {
    const el = ideaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 240) + "px";
    }
  }, [ideaPrompt]);

  const validarIdea = useCallback(async () => {
    if (!ideaPrompt.trim() || ideaLoading) return;
    setIdeaLoading(true);
    setIdeaCreada(null);
    setIdeaError(null);
    try {
      const res = await api.agenteIdea(ideaPrompt.trim());
      if (res.accion === "idea_creada" && res.tarea) {
        onTareaCreada(res.tarea);
        setIdeaCreada(res.tarea);
        setIdeaPrompt("");
      } else {
        setIdeaError(res.mensaje || "No pude generar el informe. Intenta reformular la idea.");
      }
    } catch (e) {
      console.error(e);
      setIdeaError("Ocurrió un error generando el informe.");
    } finally {
      setIdeaLoading(false);
    }
  }, [ideaPrompt, ideaLoading, onTareaCreada]);

  const toggleMicIdea = useCallback(() => {
    if (escuchando) {
      stop();
      return;
    }
    start((texto) => {
      setIdeaPrompt((prev) => (prev ? prev + " " : "") + texto);
    });
  }, [escuchando, start, stop]);

  const generarPlan = useCallback(async () => {
    if (!objetivo.trim()) return;
    setPlanLoading(true);
    setPlan(null);
    setCreadas(new Set());
    try {
      const res = await api.agentePlan(objetivo.trim(), semanas);
      setPlan(res);
    } catch (e) {
      console.error(e);
    } finally {
      setPlanLoading(false);
    }
  }, [objetivo, semanas]);

  const buscar = useCallback(async () => {
    if (!temaBuscar.trim()) return;
    setBuscarLoading(true);
    setBusqueda(null);
    try {
      const res = await api.agenteBuscar(temaBuscar.trim());
      setBusqueda(res);
    } catch (e) {
      console.error(e);
    } finally {
      setBuscarLoading(false);
    }
  }, [temaBuscar]);

  const crearTareaDelPlan = useCallback(async (draft: TareaDraft, idx: number) => {
    try {
      const res = await api.vozConfirmar(draft);
      if (res.tarea_creada) {
        onTareaCreada(res.tarea_creada);
        setCreadas((prev) => new Set(prev).add(idx));
      }
    } catch (e) {
      console.error(e);
    }
  }, [onTareaCreada]);

  // Agrupar tareas por objetivo usando las que ya existen en el sistema
  // (esto se muestra como contexto, aunque aquí no recibimos tareas externas)

  return (
    <div className="space-y-4">
      {/* Validar idea con investigación profunda */}
      <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <FlaskConical size={14} className="text-amber-400" />
          <span className="text-xs font-semibold text-text">Validar una idea (investigación profunda)</span>
        </div>
        <p className="text-[10px] text-muted mb-2">
          Describe tu idea con todo el detalle que quieras (puedes dictarla). Los agentes generarán un informe con beneficios, salidas profesionales, plan, cronograma, mapas conceptuales, fuentes y análisis monetario. Se guardará como una tarea tipo <span className="text-amber-300 font-medium">Idea</span>.
        </p>
        <div className="relative">
          <textarea
            ref={ideaRef}
            className="w-full bg-bg border border-border rounded-lg pl-3 pr-10 py-2 text-xs text-text placeholder-muted resize-none min-h-[72px]"
            placeholder={escuchando ? "Escuchando... habla tu idea" : "Ej: Quiero un plan para estudiar la maestría en matemática en la PUCP, beneficios, salidas profesionales, plan de postulación, y si me conviene física. Incluye análisis monetario."}
            value={ideaPrompt}
            onChange={(e) => setIdeaPrompt(e.target.value)}
          />
          {supported && (
            <button
              onClick={toggleMicIdea}
              disabled={ideaLoading}
              className={`absolute right-2 top-2 p-1.5 rounded-lg transition-all ${escuchando ? "bg-green-500 text-white animate-pulse" : "bg-card border border-border text-muted hover:text-accent"}`}
              title={escuchando ? "Detener dictado" : "Dictar idea"}
            >
              <Mic size={14} />
            </button>
          )}
        </div>
        <button
          onClick={validarIdea}
          disabled={!ideaPrompt.trim() || ideaLoading}
          className="w-full mt-2 bg-amber-500/90 text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
        >
          {ideaLoading ? <Loader2 size={12} className="animate-spin" /> : <FlaskConical size={12} />}
          {ideaLoading ? "Investigando... (puede tardar)" : "Analizar y validar idea"}
        </button>
        {ideaError && (
          <div className="mt-2 px-2.5 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-[10px] text-red-300">{ideaError}</div>
        )}
        {ideaCreada && (
          <div className="mt-2 bg-bg border border-amber-500/30 rounded-lg p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <Check size={12} className="text-green-400" />
              <span className="text-[11px] font-medium text-text">{ideaCreada.titulo}</span>
            </div>
            <p className="text-[10px] text-muted mb-2">{ideaCreada.descripcion}</p>
            <button
              onClick={() => setVerInforme(true)}
              className="flex items-center gap-1 text-[10px] text-amber-300 hover:text-amber-200"
            >
              <FileText size={12} /> Ver informe detallado
            </button>
          </div>
        )}
      </div>

      {/* Generar plan para un objetivo */}
      <div className="bg-accent/5 border border-accent/20 rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <Target size={14} className="text-accent" />
          <span className="text-xs font-semibold text-text">Crear plan con agente especializado</span>
        </div>
        <p className="text-[10px] text-muted mb-2">
          Dile a Jarvis qué objetivo quieres lograr (preparación, proyecto, aprendizaje) y generará tareas concretas.
        </p>
        <input
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted mb-2"
          placeholder="Ej: Preparar admisión a maestría en IA"
          value={objetivo}
          onChange={(e) => setObjetivo(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generarPlan()}
        />
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] text-muted">Semanas:</span>
          <select
            className="bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
            value={semanas}
            onChange={(e) => setSemanas(Number(e.target.value))}
          >
            {[2, 4, 6, 8, 12].map((s) => (
              <option key={s} value={s}>{s} semanas</option>
            ))}
          </select>
        </div>
        <button
          onClick={generarPlan}
          disabled={!objetivo.trim() || planLoading}
          className="w-full bg-accent text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
        >
          {planLoading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          Generar plan
        </button>
      </div>

      {/* Resultado del plan */}
      {plan && (
        <div className="bg-card border border-border rounded-xl p-3 space-y-3">
          <div className="text-xs font-medium text-text">{plan.mensaje}</div>
          {plan.plan && (
            <div className="bg-bg rounded-lg p-2 text-[10px] text-muted space-y-1">
              <div className="flex justify-between"><span>Duración:</span> <span className="text-text">{plan.plan.semanas} semanas</span></div>
              <div className="flex justify-between"><span>Frecuencia:</span> <span className="text-text capitalize">{plan.plan.frecuencia}</span></div>
              <div className="flex justify-between"><span>Primer paso:</span> <span className="text-text">{plan.plan.primer_paso}</span></div>
            </div>
          )}
          <div className="space-y-2">
            <div className="text-[10px] font-semibold text-muted uppercase">Tareas sugeridas</div>
            {plan.tareas.map((t, i) => (
              <div key={i} className="bg-bg rounded-lg p-2.5 border border-border">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="text-xs font-medium text-text">{t.titulo}</div>
                    {t.descripcion && <div className="text-[10px] text-muted mt-0.5">{t.descripcion}</div>}
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      <span className="px-1.5 py-0.5 rounded-full bg-accent/10 text-accent text-[9px] font-medium capitalize">{t.etiqueta}</span>
                      <span className="px-1.5 py-0.5 rounded-full bg-yellow-500/10 text-yellow-300 text-[9px] font-medium capitalize">{t.prioridad}</span>
                      {t.objetivo && <span className="px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-300 text-[9px] font-medium">{t.objetivo}</span>}
                    </div>
                  </div>
                  <button
                    onClick={() => crearTareaDelPlan(t, i)}
                    disabled={creadas.has(i)}
                    className={`p-1.5 rounded-lg transition-colors ${creadas.has(i) ? "bg-green-500/20 text-green-300" : "bg-accent/10 text-accent hover:bg-accent/20"}`}
                    title={creadas.has(i) ? "Creada" : "Añadir a tareas"}
                  >
                    {creadas.has(i) ? <Check size={14} /> : <Plus size={14} />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Buscar novedades */}
      <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-xl p-3">
        <div className="flex items-center gap-2 mb-2">
          <Search size={14} className="text-cyan-400" />
          <span className="text-xs font-semibold text-text">Investigar novedades</span>
        </div>
        <p className="text-[10px] text-muted mb-2">
          Pregunta a Jarvis sobre novedades o recursos relevantes para un tema que estés estudiando.
        </p>
        <input
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted mb-2"
          placeholder="Ej: Agentes LLM, React 19, FastAPI..."
          value={temaBuscar}
          onChange={(e) => setTemaBuscar(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && buscar()}
        />
        <button
          onClick={buscar}
          disabled={!temaBuscar.trim() || buscarLoading}
          className="w-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
        >
          {buscarLoading ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
          Buscar novedades
        </button>
      </div>

      {/* Resultado de búsqueda */}
      {busqueda && (
        <div className="bg-card border border-border rounded-xl p-3 space-y-3">
          <div className="text-xs font-medium text-text">{busqueda.mensaje}</div>
          <div className="space-y-2">
            {busqueda.recursos.map((r, i) => (
              <a
                key={i}
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-bg rounded-lg p-2.5 border border-border hover:border-cyan-500/30 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <ExternalLink size={12} className="text-cyan-400 mt-0.5 min-w-3" />
                  <div className="flex-1">
                    <div className="text-xs font-medium text-text">{r.titulo}</div>
                    <div className="text-[10px] text-cyan-300/80 capitalize mb-0.5">{r.tipo}</div>
                    <div className="text-[10px] text-muted">{r.relevancia}</div>
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Modal informe de la idea creada */}
      {verInforme && ideaCreada && (
        <DocumentoModal titulo={ideaCreada.titulo} contenido={ideaCreada.documento} onClose={() => setVerInforme(false)} />
      )}

      {/* Objetivos comunes */}
      <div>
        <div className="text-[10px] font-semibold text-muted uppercase mb-2">Ejemplos de objetivos</div>
        <div className="grid grid-cols-2 gap-2">
          {OBJETIVOS_COMUNES.map(({ icon: Icon, label, ejemplo }) => (
            <button
              key={label}
              onClick={() => { setObjetivo(ejemplo); }}
              className="text-left bg-bg border border-border rounded-lg p-2 hover:border-accent/30 transition-colors"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <Icon size={12} className="text-accent" />
                <span className="text-[10px] font-medium text-text">{label}</span>
              </div>
              <div className="text-[9px] text-muted truncate">{ejemplo}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
