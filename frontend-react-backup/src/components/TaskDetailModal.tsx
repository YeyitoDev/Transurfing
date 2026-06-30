import { useState } from "react";
import { X, Bell, Pencil, Trash2, Calendar, Clock, Repeat, CheckSquare, Plus, Sparkles, FileText, Loader2 } from "lucide-react";
import type { Tarea, Subtarea } from "../types";
import { api } from "../api";
import { ProgressBar } from "./ProgressBar";
import { DocumentoModal } from "./DocumentoModal";
import { ChatPanel } from "./ChatPanel";
import { GitHubTaskPanel } from "./GitHubTaskPanel";

const ETIQUETA_LABEL: Record<string, string> = {
  emprendimiento: "Emprendimiento",
  tarea: "Tarea",
  habito: "Hábito",
  investigacion: "Investigación",
  idea: "Idea",
};

const PRIORIDAD_LABEL: Record<string, string> = {
  alta: "Alta",
  media: "Media",
  baja: "Baja",
};

interface Props {
  tarea: Tarea;
  onClose: () => void;
  onChange: (t: Tarea | null, deletedId?: string) => void;
  onOpenReminder: (target: { tarea?: Tarea; subtarea?: Subtarea }) => void;
  onEdit: (t: Tarea) => void;
  onDeleted: (id: string) => void;
}

export function TaskDetailModal({ tarea, onClose, onChange, onOpenReminder, onEdit, onDeleted }: Props) {
  const [nuevaSub, setNuevaSub] = useState("");
  const [resumen, setResumen] = useState("");
  const [resumenLoading, setResumenLoading] = useState(false);
  const [docOpen, setDocOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggleSub = async (sub: Subtarea) => {
    const optimisticSubs = tarea.subtareas.map((s) =>
      s.id === sub.id ? { ...s, completada: !s.completada } : s
    );
    const completadas = optimisticSubs.filter((s) => s.completada).length;
    const total = optimisticSubs.length;
    const progreso = total > 0 ? Math.round((completadas / total) * 100 * 10) / 10 : (tarea.completada_manual ? 100 : 0);
    const estado = total > 0 && completadas === total ? "completada" : "pendiente";
    onChange({ ...tarea, subtareas: optimisticSubs, subtareas_completadas: completadas, subtareas_total: total, progreso, estado });
    try {
      const t = await api.actualizarSubtarea(sub.id, { completada: !sub.completada });
      onChange(t);
    } catch {
      onChange(tarea);
    }
  };

  const addSub = async () => {
    if (!nuevaSub.trim()) return;
    setLoading(true);
    try {
      const t = await api.agregarSubtarea(tarea.id, nuevaSub);
      onChange(t);
      setNuevaSub("");
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const delSub = async (sub: Subtarea) => {
    try {
      const t = await api.eliminarSubtarea(sub.id);
      onChange(t);
    } catch (e) {
      console.error(e);
    }
  };

  const eliminar = async () => {
    if (!confirm("¿Eliminar esta tarea?")) return;
    onDeleted(tarea.id);
    onClose();
    try {
      await api.eliminarTarea(tarea.id);
    } catch {
      // revertir
    }
  };

  const generarResumen = async () => {
    setResumenLoading(true);
    setResumen("");
    try {
      const res = await api.resumenTarea(tarea.id);
      setResumen(res.resumen);
    } catch (e) {
      console.error(e);
      setResumen("No pude generar el resumen.");
    } finally {
      setResumenLoading(false);
    }
  };

  const done = tarea.estado === "completada";
  const tieneInforme = !!tarea.documento;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 animate-fade-in p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl w-full max-w-2xl md:max-w-4xl lg:max-w-6xl xl:max-w-[1400px] max-h-[92vh] flex flex-col animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="text-sm font-semibold">Detalle de tarea</div>
          <button onClick={onClose} className="text-muted hover:text-text">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          {/* Header */}
          <div className="flex items-start gap-3 mb-4">
            <div
              className={`w-6 h-6 min-w-6 rounded-lg border-2 flex items-center justify-center text-xs transition-all ${done ? "bg-green border-green text-white" : "border-border"}`}
            >
              {done ? "✓" : ""}
            </div>
            <div className="flex-1">
              <h2 className={`text-lg font-semibold leading-snug ${done ? "line-through text-muted" : "text-text"}`}>
                {tarea.titulo}
              </h2>
              {tarea.descripcion && (
                <p className="text-sm text-muted mt-1.5">{tarea.descripcion}</p>
              )}
            </div>
          </div>

          {/* Badges */}
          <div className="flex flex-wrap gap-2 mb-4">
            <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border">
              {ETIQUETA_LABEL[tarea.etiqueta] || tarea.etiqueta}
            </span>
            <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border">
              Prioridad {PRIORIDAD_LABEL[tarea.prioridad]}
            </span>
            {tarea.repetible && (
              <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-green-500/15 text-green-400 border border-green-500/20">
                Tarea repetible
              </span>
            )}
            {tarea.fecha_limite && (
              <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border flex items-center gap-1">
                <Calendar size={10} /> {tarea.fecha_limite}
              </span>
            )}
            {tarea.horas && tarea.horas.length > 0 && (
              <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-pink-500/15 text-pink-300 border border-pink-500/20 flex items-center gap-1">
                <Clock size={10} /> {tarea.horas.join(", ")}
              </span>
            )}
            {tarea.dias_semana && tarea.dias_semana.length > 0 && (
              <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20">
                {tarea.dias_semana.map((d) => d.toUpperCase()).join(" ")}
              </span>
            )}
            {tarea.objetivo && (
              <span className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-accent border border-border">
                Objetivo: {tarea.objetivo}
              </span>
            )}
          </div>

          {/* Progress */}
          <div className="bg-card2 border border-border rounded-xl p-3 mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-text">Progreso</span>
              <span className="text-xs font-medium text-muted">{Math.round(tarea.progreso)}%</span>
            </div>
            <ProgressBar pct={tarea.progreso} />
            <div className="text-[10px] text-muted mt-2">
              {tarea.subtareas_completadas} de {tarea.subtareas_total} subtareas completadas
            </div>
          </div>

          {/* Multi-column layout for subtasks + chat + GitHub on large screens */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 mb-4 min-h-[420px]">
            {/* Left column: Subtareas + Resumen */}
            <div className="flex flex-col gap-4">
              {/* Subtareas */}
              <div className="bg-card2 border border-border rounded-xl p-3">
                <div className="text-xs font-semibold text-text mb-2 flex items-center gap-1.5">
                  <CheckSquare size={14} /> Subtareas
                </div>
                {tarea.subtareas.length === 0 ? (
                  <p className="text-[11px] text-muted">No hay subtareas.</p>
                ) : (
                  <div className="space-y-1.5 max-h-[240px] overflow-y-auto pr-1">
                    {tarea.subtareas.map((sub) => (
                      <div key={sub.id} className={`flex items-center gap-3 p-2 rounded-lg bg-bg border border-border ${sub.completada ? "opacity-50" : ""}`}>
                        <div
                          className={`w-5 h-5 min-w-5 rounded-md border-2 flex items-center justify-center text-[10px] cursor-pointer transition-all ${sub.completada ? "bg-green border-green text-white" : "border-border hover:border-accent"}`}
                          onClick={() => toggleSub(sub)}
                        >
                          {sub.completada ? "✓" : ""}
                        </div>
                        <span className={`flex-1 text-sm ${sub.completada ? "line-through text-muted" : "text-text"}`}>{sub.titulo}</span>
                        <button className="p-1 text-muted hover:text-accent" onClick={() => onOpenReminder({ tarea, subtarea: sub })}>
                          <Bell size={12} />
                        </button>
                        <button className="p-1 text-muted hover:text-red" onClick={() => delSub(sub)}>
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2 mt-2">
                  <input
                    className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted"
                    placeholder="Nueva subtarea..."
                    value={nuevaSub}
                    onChange={(e) => setNuevaSub(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addSub()}
                  />
                  <button
                    className="bg-accent text-white rounded-lg px-3 text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
                    onClick={addSub}
                    disabled={loading || !nuevaSub.trim()}
                  >
                    <Plus size={16} />
                  </button>
                </div>
              </div>

              {/* Resumen con IA */}
              <div className="bg-accent/5 border border-accent/20 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-text flex items-center gap-1.5">
                    <Sparkles size={14} className="text-accent" /> Resumen del agente
                  </div>
                  <button
                    onClick={generarResumen}
                    disabled={resumenLoading}
                    className="text-[10px] bg-accent text-white rounded-lg px-2.5 py-1.5 flex items-center gap-1 disabled:opacity-50"
                  >
                    {resumenLoading ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                    {resumenLoading ? "Generando..." : "Resumen"}
                  </button>
                </div>
                {resumen ? (
                  <div className="text-sm text-muted bg-bg border border-border rounded-lg p-3">{resumen}</div>
                ) : (
                  <p className="text-[11px] text-muted">
                    Pulsa "Resumen" para que Jarvis te diga qué pasos seguir, qué riesgos hay y qué priorizar.
                  </p>
                )}
              </div>
            </div>

            {/* Middle column: Chat */}
            <div>
              <ChatPanel tarea={tarea} onChange={onChange} />
            </div>

            {/* Right column: GitHub */}
            <div>
              <GitHubTaskPanel tarea={tarea} onChange={onChange} />
            </div>
          </div>

          {/* Informe (si existe) */}
          {tieneInforme && (
            <button
              onClick={() => setDocOpen(true)}
              className="w-full mt-4 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-xl p-2.5 text-xs font-medium flex items-center justify-center gap-2 hover:bg-amber-500/15"
            >
              <FileText size={14} /> Ver informe detallado de la idea
            </button>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-border">
          <button
            onClick={() => onOpenReminder({ tarea })}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-card2 text-text border border-border hover:border-accent transition-colors"
          >
            <Bell size={14} /> Recordatorio
          </button>
          <button
            onClick={() => { onEdit(tarea); onClose(); }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-card2 text-text border border-border hover:border-blue-400 transition-colors"
          >
            <Pencil size={14} /> Editar
          </button>
          <button
            onClick={eliminar}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
          >
            <Trash2 size={14} /> Eliminar
          </button>
          <button
            onClick={onClose}
            className="ml-auto px-4 py-2 rounded-lg text-xs font-medium bg-bg border border-border text-muted hover:text-text transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>

      {docOpen && (
        <DocumentoModal titulo={tarea.titulo} contenido={tarea.documento} onClose={() => setDocOpen(false)} />
      )}
    </div>
  );
}
