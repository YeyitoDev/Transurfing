import { useState } from "react";
import { X } from "lucide-react";
import type { Tarea, Subtarea } from "../types";
import { api } from "../api";

function ahoraISO() {
  return new Date().toISOString().slice(0, 16);
}

export function ReminderModal({
  target,
  onClose,
  onChange,
}: {
  target: { tarea?: Tarea; subtarea?: Subtarea };
  onClose: () => void;
  onChange: () => void;
}) {
  const isSub = !!target.subtarea;
  const tarea = target.tarea!;
  const defaultTitle = isSub ? `Subtarea: ${target.subtarea!.titulo}` : `Tarea: ${tarea.titulo}`;
  const [titulo, setTitulo] = useState(defaultTitle);
  const [fechaHora, setFechaHora] = useState(ahoraISO());

  const guardar = async () => {
    try {
      await api.crearRecordatorio({
        titulo,
        fecha_hora: fechaHora,
        tarea_id: tarea.id,
        subtarea_id: isSub ? target.subtarea!.id : null,
      });
      onChange();
      onClose();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 animate-fade-in" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-t-2xl sm:rounded-2xl p-6 w-full max-w-md animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Nuevo recordatorio</h3>
          <button className="p-1 text-muted hover:text-text" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <div className="text-sm text-muted mb-3">
          {isSub ? `Subtarea: ${target.subtarea!.titulo}` : `Tarea: ${tarea.titulo}`}
        </div>
        <input
          className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text mb-3"
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
        />
        <input
          type="datetime-local"
          className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text mb-4 [color-scheme:dark]"
          value={fechaHora}
          onChange={(e) => setFechaHora(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <button className="px-4 py-2 rounded-xl border border-border text-muted hover:text-text transition-colors" onClick={onClose}>
            Cancelar
          </button>
          <button className="px-4 py-2 rounded-xl bg-accent text-white font-medium hover:opacity-90 transition-opacity" onClick={guardar}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
