import { useState, useEffect } from "react";
import { X, Save, Trash2, Rocket, CheckSquare, Heart, Search, Repeat, Clock, Plus, Lightbulb } from "lucide-react";
import { api } from "../api";
import type { Tarea } from "../types";

const TIPOS = [
  { key: "emprendimiento", label: "Emprendimiento", icon: Rocket, color: "indigo" },
  { key: "tarea", label: "Tarea", icon: CheckSquare, color: "slate" },
  { key: "habito", label: "Hábito", icon: Heart, color: "pink" },
  { key: "investigacion", label: "Investigación", icon: Search, color: "cyan" },
  { key: "idea", label: "Idea", icon: Lightbulb, color: "amber" },
];

const PRIORIDADES = [
  { key: "alta", label: "Alta", color: "red" },
  { key: "media", label: "Media", color: "yellow" },
  { key: "baja", label: "Baja", color: "green" },
];

const DIAS = [
  { key: "lun", label: "L" },
  { key: "mar", label: "M" },
  { key: "mie", label: "X" },
  { key: "jue", label: "J" },
  { key: "vie", label: "V" },
  { key: "sab", label: "S" },
  { key: "dom", label: "D" },
];

interface Props {
  tarea: Tarea;
  onClose: () => void;
  onSaved: (t: Tarea) => void;
  onDeleted: (id: string) => void;
}

export function TaskEditModal({ tarea, onClose, onSaved, onDeleted }: Props) {
  const [titulo, setTitulo] = useState(tarea.titulo);
  const [descripcion, setDescripcion] = useState(tarea.descripcion || "");
  const [prioridad, setPrioridad] = useState<Tarea["prioridad"]>(tarea.prioridad);
  const [etiqueta, setEtiqueta] = useState<string>(tarea.etiqueta);
  const [repetible, setRepetible] = useState(tarea.repetible);
  const [fechaLimite, setFechaLimite] = useState(tarea.fecha_limite || "");
  const [horas, setHoras] = useState<string[]>(tarea.horas || []);
  const [nuevaHora, setNuevaHora] = useState("");
  const [diasSemana, setDiasSemana] = useState<string[]>(tarea.dias_semana || []);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const esHabito = etiqueta === "habito";

  const toggleDia = (dia: string) => {
    setDiasSemana((prev) => prev.includes(dia) ? prev.filter((d) => d !== dia) : [...prev, dia]);
  };

  const addHora = () => {
    if (nuevaHora && !horas.includes(nuevaHora)) {
      setHoras([...horas, nuevaHora].sort());
      setNuevaHora("");
    }
  };

  const removeHora = (h: string) => {
    setHoras(horas.filter((x) => x !== h));
  };

  const guardar = async () => {
    if (!titulo.trim()) return;
    setSaving(true);
    try {
      const t = await api.actualizarTarea(tarea.id, {
        titulo,
        descripcion,
        prioridad,
        etiqueta,
        repetible: esHabito ? true : repetible,
        fecha_limite: fechaLimite || null,
        horas: esHabito ? horas : [],
        dias_semana: esHabito ? diasSemana : [],
      });
      onSaved(t);
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const eliminar = async () => {
    if (!confirm("¿Eliminar esta tarea?")) return;
    setDeleting(true);
    try {
      await api.eliminarTarea(tarea.id);
      onDeleted(tarea.id);
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fade-in p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl p-5 w-full max-w-lg max-h-[90vh] overflow-y-auto animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold">Editar tarea</h3>
          <button onClick={onClose} className="text-muted hover:text-text">
            <X size={20} />
          </button>
        </div>

        {/* Título */}
        <div className="mb-3">
          <label className="text-xs text-muted font-medium mb-1.5 block">Título</label>
          <input
            className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
          />
        </div>

        {/* Descripción */}
        <div className="mb-3">
          <label className="text-xs text-muted font-medium mb-1.5 block">Descripción</label>
          <textarea
            className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text resize-none"
            rows={3}
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />
        </div>

        {/* Tipo */}
        <div className="mb-3">
          <label className="text-xs text-muted font-medium mb-1.5 block">Tipo</label>
          <div className="flex gap-2 flex-wrap">
            {TIPOS.map(({ key, label, icon: Icon, color }) => (
              <button
                key={key}
                onClick={() => setEtiqueta(key)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                  etiqueta === key
                    ? `bg-${color}-500/20 border-${color}-500/50 text-${color}-300`
                    : "bg-bg border-border text-muted hover:text-text"
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Prioridad */}
        <div className="mb-3">
          <label className="text-xs text-muted font-medium mb-1.5 block">Prioridad</label>
          <div className="flex gap-2">
            {PRIORIDADES.map(({ key, label, color }) => (
              <button
                key={key}
                onClick={() => setPrioridad(key as Tarea["prioridad"])}
                className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
                  prioridad === key
                    ? `bg-${color}-500/20 border-${color}-500/50 text-${color}-300`
                    : "bg-bg border-border text-muted hover:text-text"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Fecha límite */}
        <div className="mb-3">
          <label className="text-xs text-muted font-medium mb-1.5 block">Fecha límite</label>
          <input
            type="date"
            className="bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-text [color-scheme:dark]"
            value={fechaLimite}
            onChange={(e) => setFechaLimite(e.target.value)}
          />
        </div>

        {/* Configuración de hábito */}
        {esHabito && (
          <div className="mb-3 bg-pink-500/5 border border-pink-500/20 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-3">
              <Repeat size={14} className="text-pink-300" />
              <span className="text-xs font-semibold text-pink-300">Configuración de hábito</span>
            </div>

            <label className="text-xs text-muted mb-1.5 block">Días a repetir</label>
            <div className="flex gap-1.5 mb-3">
              {DIAS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => toggleDia(key)}
                  className={`w-8 h-8 rounded-lg text-xs font-bold border transition-all ${
                    diasSemana.includes(key)
                      ? "bg-pink-500/30 border-pink-500/50 text-pink-200"
                      : "bg-bg border-border text-muted hover:text-text"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <label className="text-xs text-muted mb-1.5 block flex items-center gap-1">
              <Clock size={12} /> Horas de recordatorio
            </label>
            <div className="flex gap-2 mb-2">
              <input
                type="time"
                className="bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text [color-scheme:dark]"
                value={nuevaHora}
                onChange={(e) => setNuevaHora(e.target.value)}
              />
              <button
                className="bg-pink-500/20 border border-pink-500/30 text-pink-300 rounded-lg px-3 text-sm hover:bg-pink-500/30 transition-colors"
                onClick={addHora}
              >
                <Plus size={16} />
              </button>
            </div>
            {horas.length > 0 && (
              <div className="flex gap-1.5 flex-wrap">
                {horas.map((h) => (
                  <span key={h} className="flex items-center gap-1 bg-pink-500/15 text-pink-300 text-xs px-2 py-1 rounded-full">
                    <Clock size={10} />
                    {h}
                    <button onClick={() => removeHora(h)} className="hover:text-red transition-colors">
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Repetible (no hábito) */}
        {!esHabito && (
          <div className="flex items-center justify-between mb-4">
            <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-accent"
                checked={repetible}
                onChange={(e) => setRepetible(e.target.checked)}
              />
              <Repeat size={14} />
              Tarea repetible diaria
            </label>
          </div>
        )}

        {/* Botones */}
        <div className="flex gap-2 pt-2 border-t border-border">
          <button
            onClick={eliminar}
            disabled={deleting}
            className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm font-medium bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
          >
            <Trash2 size={16} />
            Eliminar
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl text-sm font-medium bg-bg border border-border text-muted hover:text-text transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={saving || !titulo.trim()}
            className="ml-auto flex items-center gap-1.5 bg-accent text-white rounded-xl px-5 py-2.5 text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>
    </div>
  );
}
