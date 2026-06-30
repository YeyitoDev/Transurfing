import { useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, CheckCircle2, ListTodo, Columns3, Inbox, Settings, Bot, Github } from "lucide-react";
import type { TabKey, EtiquetaKey, Tarea, Subtarea } from "./types";
import { useSync, useNotifications } from "./hooks/useSync";
import { useTheme } from "./hooks/useTheme";
import { BottomNav } from "./components/BottomNav";
import { TaskForm } from "./components/TaskForm";
import { TaskCard } from "./components/TaskCard";
import { FilterBar } from "./components/FilterBar";
import { AlarmList } from "./components/AlarmList";
import { KanbanBoard } from "./components/KanbanBoard";
import { ReminderModal } from "./components/ReminderModal";
import { AgenteRecordatorio } from "./components/AgenteRecordatorio";
import { VoiceBot } from "./components/VoiceBot";
import { TaskEditModal } from "./components/TaskEditModal";
import { TaskDetailModal } from "./components/TaskDetailModal";
import { CalendarView } from "./components/CalendarView";
import { ThemeSettings } from "./components/ThemeSettings";
import { AgentesManager } from "./components/AgentesManager";
import { GitHubSettings } from "./components/GitHubSettings";

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function App() {
  const { tareas, recordatorios, loading, cargarRecordatorios, setTareas } = useSync();
  const { enabled: notifEnabled, requestPermission } = useNotifications(recordatorios);
  const [tab, setTab] = useState<TabKey>("pendientes");
  const [filtro, setFiltro] = useState<EtiquetaKey>("todas");
  const [reminderTarget, setReminderTarget] = useState<{ tarea?: Tarea; subtarea?: Subtarea } | null>(null);
  const [editTarget, setEditTarget] = useState<Tarea | null>(null);
  const [detailTarget, setDetailTarget] = useState<Tarea | null>(null);
  const [showAgentes, setShowAgentes] = useState(false);
  const [showTheme, setShowTheme] = useState(false);
  const [showGitHub, setShowGitHub] = useState(false);
  useTheme();

  const onTaskChange = useCallback(
    (tarea: Tarea | null, deletedId?: string) => {
      setTareas((prev) =>
        deletedId ? prev.filter((t) => t.id !== deletedId) : prev.map((t) => (tarea && t.id === tarea.id ? tarea : t))
      );
    },
    [setTareas]
  );

  const tareasFiltradas = filtro === "todas" ? tareas : tareas.filter((t) => t.etiqueta === filtro);
  const pendientes = tareasFiltradas.filter((t) => t.estado !== "completada");
  const completadas = tareasFiltradas.filter((t) => t.estado === "completada");
  const proximas = tareas.filter((t) => t.estado !== "completada" && t.fecha_limite && t.fecha_limite <= hoyISO());

  const pendientesCount = tareas.filter((t) => t.estado !== "completada").length;
  const completadasCount = tareas.filter((t) => t.estado === "completada").length;

  return (
    <div className="min-h-screen bg-bg text-text pb-20">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        {/* Header */}
        <header className="text-center pt-8 pb-4 relative">
          <div className="absolute right-0 top-8 flex items-center gap-1">
            <button
              onClick={() => setShowGitHub(true)}
              className="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors"
              aria-label="Configuración GitHub"
            >
              <Github size={20} />
            </button>
            <button
              onClick={() => setShowAgentes(true)}
              className="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors"
              aria-label="Agentes especializados"
            >
              <Bot size={20} />
            </button>
            <button
              onClick={() => setShowTheme(true)}
              className="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors"
              aria-label="Personalizar colores"
            >
              <Settings size={20} />
            </button>
          </div>
          <h1 className="text-2xl font-bold">Mis Tareas</h1>
          <p className="text-sm text-muted mt-1.5">
            {pendientesCount} pendientes · {completadasCount} completadas · {recordatorios.length} alarmas
            {proximas.length > 0 && (
              <span className="ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">
                {proximas.length} próximas
              </span>
            )}
          </p>
        </header>

        {/* Notification permission banner */}
        {!notifEnabled && (
          <div className="mb-4 bg-card2 border border-border rounded-xl px-4 py-3 flex items-center justify-between text-sm text-muted max-w-2xl mx-auto">
            <span className="flex items-center gap-2">
              <Bell size={16} />
              Activa notificaciones para recordatorios
            </span>
            <button className="bg-accent text-white rounded-lg px-3 py-1.5 text-xs font-medium" onClick={requestPermission}>
              Activar
            </button>
          </div>
        )}

        {/* Task form */}
        <div className="mb-4 max-w-2xl mx-auto">
          <TaskForm onCreated={(t) => setTareas((prev: Tarea[]) => [t, ...prev])} />
        </div>

        {/* Filter chips */}
        <div className="mb-3 max-w-2xl mx-auto">
          <FilterBar value={filtro} onChange={setFiltro} />
        </div>

        {/* Content */}
        <div className="max-w-5xl mx-auto">
          {loading ? (
            <div className="text-center text-muted py-16">Cargando...</div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.15 }}
              >
                {tab === "pendientes" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {pendientes.length === 0 ? (
                      <div className="col-span-full">
                        <EmptyState icon={ListTodo} text="No tienes tareas pendientes" />
                      </div>
                    ) : (
                      pendientes.map((t) => (
                        <TaskCard key={t.id} tarea={t} onChange={onTaskChange} onOpenReminder={setReminderTarget} onEdit={setEditTarget} onOpenDetail={setDetailTarget} />
                      ))
                    )}
                  </div>
                )}

                {tab === "completadas" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {completadas.length === 0 ? (
                      <div className="col-span-full">
                        <EmptyState icon={CheckCircle2} text="Aún no tienes tareas completadas" />
                      </div>
                    ) : (
                      completadas.map((t) => (
                        <TaskCard key={t.id} tarea={t} onChange={onTaskChange} onOpenReminder={setReminderTarget} onEdit={setEditTarget} onOpenDetail={setDetailTarget} />
                      ))
                    )}
                  </div>
                )}

                {tab === "calendario" && (
                  <CalendarView tareas={tareasFiltradas} onChange={onTaskChange} onOpenReminder={setReminderTarget} onEdit={setEditTarget} />
                )}

                {tab === "alarmas" && (
                  <div className="max-w-2xl mx-auto">
                    <AlarmList recordatorios={recordatorios} onChange={cargarRecordatorios} />
                  </div>
                )}

                {tab === "kanban" && (
                  <KanbanBoard tareas={tareasFiltradas} onChange={onTaskChange} onOpenReminder={setReminderTarget} />
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>

      {/* Agente recordatorio (botón flotante + modal) */}
      <AgenteRecordatorio onTareaCreada={(t) => setTareas((prev: Tarea[]) => [t, ...prev])} />

      {/* Bot de voz */}
      <VoiceBot onTareaCreada={(t) => setTareas((prev: Tarea[]) => [t, ...prev])} />

      {/* Bottom navigation */}
      <BottomNav tab={tab} onChange={setTab} />

      {/* Agentes especializados */}
      {showAgentes && <AgentesManager onClose={() => setShowAgentes(false)} />}

      {/* GitHub settings */}
      {showGitHub && <GitHubSettings onClose={() => setShowGitHub(false)} />}

      {/* Theme settings */}
      {showTheme && <ThemeSettings onClose={() => setShowTheme(false)} />}

      {/* Reminder modal */}
      {reminderTarget && (
        <ReminderModal
          target={reminderTarget}
          onClose={() => setReminderTarget(null)}
          onChange={cargarRecordatorios}
        />
      )}

      {/* Edit modal */}
      {editTarget && (
        <TaskEditModal
          tarea={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={(t) => { onTaskChange(t); setEditTarget(null); }}
          onDeleted={(id) => { onTaskChange(null, id); setEditTarget(null); }}
        />
      )}

      {/* Detail modal */}
      {detailTarget && (
        <TaskDetailModal
          tarea={tareas.find((t) => t.id === detailTarget.id) || detailTarget}
          onClose={() => setDetailTarget(null)}
          onChange={onTaskChange}
          onOpenReminder={setReminderTarget}
          onEdit={setEditTarget}
          onDeleted={(id) => { onTaskChange(null, id); setDetailTarget(null); }}
        />
      )}
    </div>
  );
}

function EmptyState({ icon: Icon, text }: { icon: typeof ListTodo; text: string }) {
  return (
    <div className="text-center text-muted py-16">
      <Icon size={40} className="mx-auto mb-3 opacity-40" />
      <p className="text-sm">{text}</p>
    </div>
  );
}
