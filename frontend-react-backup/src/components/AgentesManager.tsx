import { useEffect, useState } from "react";
import { X, Plus, Bot, Cpu, BookOpen, Sparkles, Trash2, Play, CheckSquare, Loader2 } from "lucide-react";
import type { Agente, Skill, Knowledge, Tarea } from "../types";
import { api } from "../api";

interface Props {
  tarea?: Tarea;
  onClose: () => void;
}

const MODELOS = [
  "llama-3.3-70b-versatile",
  "llama-3.1-70b-versatile",
  "llama-3.1-8b-instant",
  "mixtral-8x7b-32768",
  "gemma-7b-it",
  "gpt-4o",
  "gpt-4o-mini",
  "qwen3.5-plus",
];

export function AgentesManager({ tarea, onClose }: Props) {
  const [tab, setTab] = useState<"agentes" | "skills" | "knowledge">("agentes");
  const [agentes, setAgentes] = useState<Agente[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [loading, setLoading] = useState(true);

  // Form agente
  const [editAgente, setEditAgente] = useState<Agente | null>(null);
  const [nombreAgente, setNombreAgente] = useState("");
  const [descAgente, setDescAgente] = useState("");
  const [modeloAgente, setModeloAgente] = useState(MODELOS[0]);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [skillsAgente, setSkillsAgente] = useState<string[]>([]);
  const [knowledgeAgente, setKnowledgeAgente] = useState<string[]>([]);

  // Form skill/knowledge
  const [editSkill, setEditSkill] = useState<Skill | null>(null);
  const [nombreSkill, setNombreSkill] = useState("");
  const [descSkill, setDescSkill] = useState("");
  const [instruccionesSkill, setInstruccionesSkill] = useState("");
  const [editKnowledge, setEditKnowledge] = useState<Knowledge | null>(null);
  const [nombreKnowledge, setNombreKnowledge] = useState("");
  const [tipoKnowledge, setTipoKnowledge] = useState("texto");
  const [contenidoKnowledge, setContenidoKnowledge] = useState("");

  // Ejecución
  const [promptEjecucion, setPromptEjecucion] = useState("");
  const [agenteSeleccionado, setAgenteSeleccionado] = useState<string[]>([]);
  const [ejecutando, setEjecutando] = useState(false);
  const [resultados, setResultados] = useState<{ agente_id: string; agente_nombre: string; respuesta?: string; error?: string }[]>([]);

  const cargar = async () => {
    try {
      const res = await api.listarAgentes();
      setAgentes(res.agentes);
      setSkills(res.skills);
      setKnowledge(res.knowledge);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const resetAgenteForm = () => {
    setEditAgente(null);
    setNombreAgente("");
    setDescAgente("");
    setModeloAgente(MODELOS[0]);
    setSystemPrompt("");
    setSkillsAgente([]);
    setKnowledgeAgente([]);
  };

  const guardarAgente = async () => {
    if (!nombreAgente.trim()) return;
    const data = {
      nombre: nombreAgente,
      descripcion: descAgente,
      modelo: modeloAgente,
      system_prompt: systemPrompt,
      skills: skillsAgente,
      knowledge: knowledgeAgente,
    };
    if (editAgente) {
      await api.actualizarAgente(editAgente.id, data);
    } else {
      await api.crearAgente(data);
    }
    resetAgenteForm();
    await cargar();
  };

  const editarAgente = (a: Agente) => {
    setEditAgente(a);
    setNombreAgente(a.nombre);
    setDescAgente(a.descripcion);
    setModeloAgente(a.modelo);
    setSystemPrompt(a.system_prompt);
    setSkillsAgente(a.skills);
    setKnowledgeAgente(a.knowledge);
  };

  const eliminarAgente = async (id: string) => {
    if (!confirm("¿Eliminar este agente?")) return;
    await api.eliminarAgente(id);
    await cargar();
  };

  const toggleSkillAgente = (id: string) => {
    setSkillsAgente((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const toggleKnowledgeAgente = (id: string) => {
    setKnowledgeAgente((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const guardarSkill = async () => {
    if (!nombreSkill.trim()) return;
    const data = { nombre: nombreSkill, descripcion: descSkill, instrucciones: instruccionesSkill };
    if (editSkill) {
      await api.actualizarSkill(editSkill.id, data);
    } else {
      await api.crearSkill(data);
    }
    setEditSkill(null);
    setNombreSkill("");
    setDescSkill("");
    setInstruccionesSkill("");
    await cargar();
  };

  const editarSkill = (s: Skill) => {
    setEditSkill(s);
    setNombreSkill(s.nombre);
    setDescSkill(s.descripcion);
    setInstruccionesSkill(s.instrucciones);
  };

  const eliminarSkill = async (id: string) => {
    if (!confirm("¿Eliminar este skill?")) return;
    await api.eliminarSkill(id);
    await cargar();
  };

  const guardarKnowledge = async () => {
    if (!nombreKnowledge.trim()) return;
    const data = { nombre: nombreKnowledge, tipo: tipoKnowledge, contenido: contenidoKnowledge };
    if (editKnowledge) {
      await api.actualizarKnowledge(editKnowledge.id, data);
    } else {
      await api.crearKnowledge(data);
    }
    setEditKnowledge(null);
    setNombreKnowledge("");
    setTipoKnowledge("texto");
    setContenidoKnowledge("");
    await cargar();
  };

  const editarKnowledge = (k: Knowledge) => {
    setEditKnowledge(k);
    setNombreKnowledge(k.nombre);
    setTipoKnowledge(k.tipo);
    setContenidoKnowledge(k.contenido);
  };

  const eliminarKnowledge = async (id: string) => {
    if (!confirm("¿Eliminar este knowledge?")) return;
    await api.eliminarKnowledge(id);
    await cargar();
  };

  const ejecutar = async () => {
    if (!promptEjecucion.trim() || agenteSeleccionado.length === 0) return;
    setEjecutando(true);
    setResultados([]);
    try {
      const res = await api.ejecutarAgentesParalelo(agenteSeleccionado, promptEjecucion + (tarea ? `\n\nContexto tarea: ${tarea.titulo}` : ""));
      setResultados(res.resultados);
    } catch (e) {
      console.error(e);
    } finally {
      setEjecutando(false);
    }
  };

  const toggleAgenteSeleccion = (id: string) => {
    setAgenteSeleccionado((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 animate-fade-in p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-accent" />
            <span className="text-sm font-semibold">Agentes especializados</span>
            {tarea && <span className="text-[10px] text-muted ml-2">para: {tarea.titulo}</span>}
          </div>
          <button onClick={onClose} className="text-muted hover:text-text"><X size={20} /></button>
        </div>

        <div className="flex items-center gap-2 px-5 py-2 border-b border-border">
          {(["agentes", "skills", "knowledge"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-[11px] font-medium px-3 py-1.5 rounded-lg transition-colors ${tab === t ? "bg-accent text-white" : "text-muted hover:text-text hover:bg-card2"}`}
            >
              {t === "agentes" && <><Bot size={12} className="inline mr-1" /> Agentes</>}
              {t === "skills" && <><Sparkles size={12} className="inline mr-1" /> Skills</>}
              {t === "knowledge" && <><BookOpen size={12} className="inline mr-1" /> Knowledge</>}
            </button>
          ))}
        </div>

        <div className="overflow-y-auto flex-1 p-5">
          {loading ? (
            <div className="text-center text-muted py-10"><Loader2 size={20} className="animate-spin mx-auto" /></div>
          ) : tab === "agentes" ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Lista + ejecución */}
              <div className="space-y-3">
                <div className="text-xs font-semibold text-text flex items-center gap-1.5">
                  <Bot size={14} /> Agentes disponibles
                </div>
                {agentes.length === 0 && <p className="text-[11px] text-muted">No hay agentes creados.</p>}
                {agentes.map((a) => (
                  <div key={a.id} className="bg-card2 border border-border rounded-xl p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="text-sm font-semibold text-text">{a.nombre}</div>
                        <div className="text-[10px] text-muted flex items-center gap-1 mt-0.5">
                          <Cpu size={10} /> {a.modelo}
                        </div>
                        {a.descripcion && <p className="text-[11px] text-muted mt-1">{a.descripcion}</p>}
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        <button onClick={() => editarAgente(a)} className="p-1.5 text-muted hover:text-blue-400"><Plus size={12} /></button>
                        <button onClick={() => eliminarAgente(a.id)} className="p-1.5 text-muted hover:text-red"><Trash2 size={12} /></button>
                      </div>
                    </div>
                    <label className="flex items-center gap-1.5 mt-2 text-[10px] text-muted cursor-pointer">
                      <input
                        type="checkbox"
                        checked={agenteSeleccionado.includes(a.id)}
                        onChange={() => toggleAgenteSeleccion(a.id)}
                        className="accent-accent"
                      />
                      Seleccionar para ejecución
                    </label>
                  </div>
                ))}

                {/* Ejecución */}
                <div className="bg-accent/5 border border-accent/20 rounded-xl p-3 mt-4">
                  <div className="text-xs font-semibold text-text mb-2 flex items-center gap-1.5">
                    <Play size={14} className="text-accent" /> Ejecutar agentes
                  </div>
                  <textarea
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted mb-2"
                    rows={3}
                    placeholder="Escribe aquí la tarea o pregunta para los agentes seleccionados..."
                    value={promptEjecucion}
                    onChange={(e) => setPromptEjecucion(e.target.value)}
                  />
                  <button
                    onClick={ejecutar}
                    disabled={ejecutando || agenteSeleccionado.length === 0 || !promptEjecucion.trim()}
                    className="w-full bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {ejecutando ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    {ejecutando ? "Ejecutando..." : `Ejecutar ${agenteSeleccionado.length} agente(s)`}
                  </button>
                  {resultados.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {resultados.map((r) => (
                        <div key={r.agente_id} className="bg-bg border border-border rounded-lg p-2">
                          <div className="text-[10px] font-semibold text-accent mb-1">{r.agente_nombre}</div>
                          {r.error ? (
                            <div className="text-[10px] text-red-400">{r.error}</div>
                          ) : (
                            <div className="text-[11px] text-muted whitespace-pre-wrap">{r.respuesta}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Form agente */}
              <div className="bg-card2 border border-border rounded-xl p-3 h-fit">
                <div className="text-xs font-semibold text-text mb-3">
                  {editAgente ? "Editar agente" : "Crear agente"}
                </div>
                <div className="space-y-2.5">
                  <input
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted"
                    placeholder="Nombre del agente"
                    value={nombreAgente}
                    onChange={(e) => setNombreAgente(e.target.value)}
                  />
                  <input
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted"
                    placeholder="Descripción"
                    value={descAgente}
                    onChange={(e) => setDescAgente(e.target.value)}
                  />
                  <div className="flex items-center gap-2">
                    <Cpu size={12} className="text-muted" />
                    <select
                      className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text"
                      value={modeloAgente}
                      onChange={(e) => setModeloAgente(e.target.value)}
                    >
                      {MODELOS.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <textarea
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted"
                    rows={4}
                    placeholder="System prompt / instrucciones base del agente"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                  />
                  <div>
                    <div className="text-[10px] text-muted mb-1">Skills</div>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => toggleSkillAgente(s.id)}
                          className={`text-[10px] px-2 py-1 rounded-lg border ${skillsAgente.includes(s.id) ? "bg-accent text-white border-accent" : "bg-bg border-border text-muted"}`}
                        >
                          {s.nombre}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted mb-1">Knowledge</div>
                    <div className="flex flex-wrap gap-1.5">
                      {knowledge.map((k) => (
                        <button
                          key={k.id}
                          onClick={() => toggleKnowledgeAgente(k.id)}
                          className={`text-[10px] px-2 py-1 rounded-lg border ${knowledgeAgente.includes(k.id) ? "bg-accent text-white border-accent" : "bg-bg border-border text-muted"}`}
                        >
                          {k.nombre}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button onClick={guardarAgente} className="flex-1 bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium">
                      {editAgente ? "Actualizar" : "Crear"}
                    </button>
                    {editAgente && (
                      <button onClick={resetAgenteForm} className="px-3 py-2 text-xs text-muted hover:text-text border border-border rounded-lg">
                        Cancelar
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : tab === "skills" ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-3">
                <div className="text-xs font-semibold text-text flex items-center gap-1.5"><Sparkles size={14} /> Skills</div>
                {skills.length === 0 && <p className="text-[11px] text-muted">No hay skills.</p>}
                {skills.map((s) => (
                  <div key={s.id} className="bg-card2 border border-border rounded-xl p-3">
                    <div className="text-sm font-semibold text-text">{s.nombre}</div>
                    <p className="text-[11px] text-muted mt-1">{s.descripcion}</p>
                    <p className="text-[10px] text-muted mt-1.5 line-clamp-3">{s.instrucciones}</p>
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => editarSkill(s)} className="text-[10px] text-blue-400 hover:text-blue-300">Editar</button>
                      <button onClick={() => eliminarSkill(s.id)} className="text-[10px] text-red-400 hover:text-red-300">Eliminar</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-card2 border border-border rounded-xl p-3 h-fit">
                <div className="text-xs font-semibold text-text mb-3">{editSkill ? "Editar skill" : "Crear skill"}</div>
                <div className="space-y-2.5">
                  <input className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" placeholder="Nombre" value={nombreSkill} onChange={(e) => setNombreSkill(e.target.value)} />
                  <input className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" placeholder="Descripción" value={descSkill} onChange={(e) => setDescSkill(e.target.value)} />
                  <textarea className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" rows={5} placeholder="Instrucciones que el agente usará cuando tenga este skill" value={instruccionesSkill} onChange={(e) => setInstruccionesSkill(e.target.value)} />
                  <div className="flex gap-2">
                    <button onClick={guardarSkill} className="flex-1 bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium">{editSkill ? "Actualizar" : "Crear"}</button>
                    {editSkill && <button onClick={() => { setEditSkill(null); setNombreSkill(""); setDescSkill(""); setInstruccionesSkill(""); }} className="px-3 py-2 text-xs text-muted hover:text-text border border-border rounded-lg">Cancelar</button>}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="space-y-3">
                <div className="text-xs font-semibold text-text flex items-center gap-1.5"><BookOpen size={14} /> Knowledge</div>
                {knowledge.length === 0 && <p className="text-[11px] text-muted">No hay knowledge.</p>}
                {knowledge.map((k) => (
                  <div key={k.id} className="bg-card2 border border-border rounded-xl p-3">
                    <div className="text-sm font-semibold text-text">{k.nombre}</div>
                    <span className="text-[10px] text-muted bg-card px-2 py-0.5 rounded-full">{k.tipo}</span>
                    <p className="text-[10px] text-muted mt-1.5 line-clamp-3">{k.contenido}</p>
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => editarKnowledge(k)} className="text-[10px] text-blue-400 hover:text-blue-300">Editar</button>
                      <button onClick={() => eliminarKnowledge(k.id)} className="text-[10px] text-red-400 hover:text-red-300">Eliminar</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-card2 border border-border rounded-xl p-3 h-fit">
                <div className="text-xs font-semibold text-text mb-3">{editKnowledge ? "Editar knowledge" : "Crear knowledge"}</div>
                <div className="space-y-2.5">
                  <input className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" placeholder="Nombre" value={nombreKnowledge} onChange={(e) => setNombreKnowledge(e.target.value)} />
                  <select className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text" value={tipoKnowledge} onChange={(e) => setTipoKnowledge(e.target.value)}>
                    <option value="texto">Texto</option>
                    <option value="url">URL</option>
                    <option value="archivo">Archivo</option>
                  </select>
                  <textarea className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" rows={5} placeholder="Contenido, URL o referencia" value={contenidoKnowledge} onChange={(e) => setContenidoKnowledge(e.target.value)} />
                  <div className="flex gap-2">
                    <button onClick={guardarKnowledge} className="flex-1 bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium">{editKnowledge ? "Actualizar" : "Crear"}</button>
                    {editKnowledge && <button onClick={() => { setEditKnowledge(null); setNombreKnowledge(""); setTipoKnowledge("texto"); setContenidoKnowledge(""); }} className="px-3 py-2 text-xs text-muted hover:text-text border border-border rounded-lg">Cancelar</button>}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
