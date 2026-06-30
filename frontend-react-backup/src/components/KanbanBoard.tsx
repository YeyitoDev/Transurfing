import type { Tarea, Subtarea } from "../types";
import { TaskCard } from "./TaskCard";

export function KanbanBoard({
  tareas,
  onChange,
  onOpenReminder,
}: {
  tareas: Tarea[];
  onChange: (t: Tarea | null, deletedId?: string) => void;
  onOpenReminder: (target: { tarea?: Tarea; subtarea?: Subtarea }) => void;
}) {
  const cols = [
    { key: "pendiente", label: "Pendientes" },
    { key: "en_progreso", label: "En progreso" },
    { key: "completada", label: "Completadas" },
  ];

  const porCol: Record<string, Tarea[]> = {
    pendiente: tareas.filter((t) => t.progreso === 0 && t.estado !== "completada"),
    en_progreso: tareas.filter((t) => t.progreso > 0 && t.progreso < 100),
    completada: tareas.filter((t) => t.estado === "completada"),
  };

  return (
    <div className="flex gap-3 overflow-x-auto pb-3 -mx-4 px-4">
      {cols.map((col) => (
        <div key={col.key} className="min-w-[260px] w-[260px] bg-card border border-border rounded-2xl p-3 flex flex-col gap-2">
          <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">
            {col.label} ({porCol[col.key].length})
          </h3>
          {porCol[col.key].map((t) => (
            <TaskCard key={t.id} tarea={t} onChange={onChange} onOpenReminder={onOpenReminder} compact />
          ))}
          {porCol[col.key].length === 0 && (
            <div className="text-center text-muted text-xs py-8">Sin tareas</div>
          )}
        </div>
      ))}
    </div>
  );
}
