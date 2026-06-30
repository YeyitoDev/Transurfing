import { Check, Trash2, Bell } from "lucide-react";
import type { Recordatorio } from "../types";
import { api } from "../api";

export function AlarmList({
  recordatorios,
  onChange,
}: {
  recordatorios: Recordatorio[];
  onChange: () => void;
}) {
  const completar = async (r: Recordatorio) => {
    try {
      await api.actualizarRecordatorio(r.id, { estado: "completado" });
      onChange();
    } catch (e) {
      console.error(e);
    }
  };

  const eliminar = async (r: Recordatorio) => {
    if (!confirm("¿Eliminar recordatorio?")) return;
    try {
      await api.eliminarRecordatorio(r.id);
      onChange();
    } catch (e) {
      console.error(e);
    }
  };

  if (recordatorios.length === 0) {
    return (
      <div className="text-center text-muted py-16">
        <Bell size={40} className="mx-auto mb-3 opacity-40" />
        <p className="text-sm">Sin alarmas activas</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {recordatorios.map((r) => (
        <div
          key={r.id}
          className={`bg-card border rounded-xl p-4 flex items-center gap-3 ${
            r.proximo ? "border-red-500/50 bg-red-500/5" : "border-border"
          }`}
        >
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold">{r.titulo}</div>
            <div className="text-xs text-muted mt-1">
              {r.fecha_hora.replace("T", " ")}
              {r.tarea_titulo && ` · ${r.tarea_titulo}`}
              {r.subtarea_titulo && ` / ${r.subtarea_titulo}`}
            </div>
          </div>
          {r.proximo && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">
              AHORA
            </span>
          )}
          <button
            className="p-2 rounded-lg text-muted hover:text-green transition-colors"
            onClick={() => completar(r)}
          >
            <Check size={18} />
          </button>
          <button
            className="p-2 rounded-lg text-muted hover:text-red transition-colors"
            onClick={() => eliminar(r)}
          >
            <Trash2 size={18} />
          </button>
        </div>
      ))}
    </div>
  );
}
