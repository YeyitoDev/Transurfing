import { useState } from "react";
import { Bell, Trash2, Rocket, CheckSquare, Heart, Calendar, Search, Clock, Pencil, Lightbulb, FileText, Expand, Sparkles, Github, Code2 } from "lucide-react";
import type { Tarea } from "../types";
import { api } from "../api";
import { ProgressBar } from "./ProgressBar";
import { DocumentoModal } from "./DocumentoModal";

const ETIQUETA_CONFIG: Record<string, { label: string; icon: typeof Rocket; color: string; bg: string; text: string; border: string }> = {
  emprendimiento: { label: "Emprendimiento", icon: Rocket, color: "indigo", bg: "bg-indigo-500/15", text: "text-indigo-300", border: "border-l-indigo-500" },
  tarea: { label: "Tarea", icon: CheckSquare, color: "slate", bg: "bg-slate-500/15", text: "text-slate-300", border: "border-l-slate-400" },
  habito: { label: "Hábito", icon: Heart, color: "pink", bg: "bg-pink-500/15", text: "text-pink-300", border: "border-l-pink-500" },
  investigacion: { label: "Investigación", icon: Search, color: "cyan", bg: "bg-cyan-500/15", text: "text-cyan-300", border: "border-l-cyan-500" },
  idea: { label: "Idea", icon: Lightbulb, color: "amber", bg: "bg-amber-500/15", text: "text-amber-300", border: "border-l-amber-500" },
};

const PRIORIDAD_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  alta: { label: "Alta", bg: "bg-red-500/15", text: "text-red-400", dot: "bg-red-500" },
  media: { label: "Media", bg: "bg-amber-500/15", text: "text-amber-400", dot: "bg-amber-500" },
  baja: { label: "Baja", bg: "bg-green-500/15", text: "text-green-400", dot: "bg-green-500" },
};

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

export function TaskCard({
  tarea,
  onChange,
  onOpenReminder,
  onEdit,
  onOpenDetail,
  compact,
}: {
  tarea: Tarea;
  onChange: (t: Tarea | null, deletedId?: string) => void;
  onOpenReminder: (target: { tarea?: Tarea }) => void;
  onEdit?: (t: Tarea) => void;
  onOpenDetail?: (t: Tarea) => void;
  compact?: boolean;
}) {
  const [docOpen, setDocOpen] = useState(false);
  const done = tarea.estado === "completada";
  const tieneInforme = !!tarea.documento;
  const vencida = tarea.fecha_limite && tarea.fecha_limite < hoyISO() && !done;
  const enProgreso = tarea.progreso > 0 && tarea.progreso < 100;

  const etq = ETIQUETA_CONFIG[tarea.etiqueta] || ETIQUETA_CONFIG.tarea;
  const pri = PRIORIDAD_CONFIG[tarea.prioridad] || PRIORIDAD_CONFIG.media;
  const EtqIcon = etq.icon;

  const toggleManual = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const optimistic = { ...tarea, completada_manual: !done, estado: (!done ? "completada" : "pendiente") as Tarea["estado"] };
    onChange(optimistic);
    try {
      const t = await api.actualizarTarea(tarea.id, { completada_manual: !done });
      onChange(t);
    } catch {
      onChange(tarea);
    }
  };

  const delTask = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("¿Eliminar esta tarea?")) return;
    onChange(null, tarea.id);
    try {
      await api.eliminarTarea(tarea.id);
    } catch {
      onChange(tarea);
    }
  };

  const statusBadge = done
    ? { label: "Completada", bg: "bg-green-500/20", text: "text-green-400" }
    : vencida
    ? { label: "Vencida", bg: "bg-red-500/20", text: "text-red-400" }
    : enProgreso
    ? { label: "En progreso", bg: "bg-blue-500/20", text: "text-blue-400" }
    : { label: "Pendiente", bg: "bg-zinc-500/20", text: "text-zinc-400" };

  return (
    <div className={`h-[180px] flex flex-col bg-card border border-border ${etq.border} border-l-4 rounded-2xl overflow-hidden transition-all hover:shadow-lg hover:scale-[1.01] ${done ? "opacity-50" : ""} ${vencida ? "ring-1 ring-red-500/30" : ""}`}>
      <div className="flex-1 flex flex-col p-4 cursor-pointer" onClick={() => onOpenDetail?.(tarea)}>
        {/* Header */}
        <div className="flex items-start gap-3 min-h-0">
          <div
            className={`w-6 h-6 min-w-6 mt-0.5 rounded-lg border-2 flex items-center justify-center text-xs transition-all ${done ? "bg-green border-green text-white" : "border-border hover:border-accent"}`}
            onClick={toggleManual}
            title={done ? "Marcar pendiente" : "Marcar completada"}
          >
            {done ? "✓" : ""}
          </div>

          <div className="flex-1 min-w-0">
            <div className={`text-sm font-semibold leading-snug line-clamp-2 ${done ? "line-through" : ""}`}>{tarea.titulo}</div>
            {tarea.descripcion && !compact && (
              <p className="text-xs text-muted mt-1 line-clamp-2">{tarea.descripcion}</p>
            )}
          </div>
        </div>

        {/* Meta badges */}
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${etq.bg} ${etq.text}`}>
            <EtqIcon size={10} />
            {etq.label}
          </span>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${pri.bg} ${pri.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${pri.dot}`} />
            {pri.label}
          </span>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${statusBadge.bg} ${statusBadge.text}`}>
            {statusBadge.label}
          </span>
          {tarea.github_repo && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 bg-slate-500/15 text-slate-300">
              <Github size={10} />
              {tarea.github_repo}
            </span>
          )}
        </div>

        {/* Footer info */}
        <div className="mt-auto pt-3">
          {tarea.proxima_alta_valor && (
            <div className="flex items-start gap-1.5 text-[10px] text-accent mb-2 line-clamp-1" title={tarea.proxima_alta_valor}>
              <Sparkles size={10} className="mt-0.5 shrink-0" />
              <span>{tarea.proxima_alta_valor}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-[10px] text-muted mb-2">
            {tarea.fecha_limite && (
              <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full ${vencida ? "bg-red-500/15 text-red-400" : "bg-card2"}`}>
                <Calendar size={10} />
                {tarea.fecha_limite}
              </span>
            )}
            {tarea.horas && tarea.horas.length > 0 && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-pink-500/15 text-pink-300">
                <Clock size={10} />
                {tarea.horas.join(", ")}
              </span>
            )}
            {tarea.subtareas_total > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-card2">
                {tarea.subtareas_completadas}/{tarea.subtareas_total} subtareas
              </span>
            )}
          </div>

          <div className="flex items-center justify-between gap-3">
            <ProgressBar pct={tarea.progreso} />
            <div className="flex items-center gap-1">
              {tieneInforme && (
                <button
                  className="p-1.5 rounded-lg text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 transition-colors"
                  onClick={(e) => { e.stopPropagation(); setDocOpen(true); }}
                  title="Ver informe detallado"
                >
                  <FileText size={15} />
                </button>
              )}
              <button
                className="p-1.5 rounded-lg text-muted hover:text-accent hover:bg-accent/10 transition-colors"
                onClick={(e) => { e.stopPropagation(); onOpenReminder({ tarea }); }}
              >
                <Bell size={15} />
              </button>
              {onEdit && (
                <button
                  className="p-1.5 rounded-lg text-muted hover:text-blue-400 hover:bg-blue-400/10 transition-colors"
                  onClick={(e) => { e.stopPropagation(); onEdit(tarea); }}
                >
                  <Pencil size={15} />
                </button>
              )}
              <button
                className="p-1.5 rounded-lg text-muted hover:text-red hover:bg-red-500/10 transition-colors"
                onClick={delTask}
              >
                <Trash2 size={15} />
              </button>
              {tarea.github_repo && (
                <button
                  className="p-1.5 rounded-lg text-accent hover:text-text hover:bg-accent/10 transition-colors"
                  onClick={(e) => { e.stopPropagation(); onOpenDetail?.(tarea); }}
                  title="GitHub"
                >
                  <Code2 size={15} />
                </button>
              )}
              <button
                className="p-1.5 rounded-lg text-muted hover:text-text hover:bg-card2 transition-colors"
                onClick={(e) => { e.stopPropagation(); onOpenDetail?.(tarea); }}
                title="Ver detalle"
              >
                <Expand size={15} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {docOpen && (
        <DocumentoModal titulo={tarea.titulo} contenido={tarea.documento} onClose={() => setDocOpen(false)} />
      )}
    </div>
  );
}
