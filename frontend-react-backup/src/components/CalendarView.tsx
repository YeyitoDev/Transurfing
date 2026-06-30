import { useState, useMemo } from "react";
import { ChevronLeft, ChevronRight, Calendar as CalIcon, LayoutGrid, Rows3 } from "lucide-react";
import type { Tarea } from "../types";
import { TaskCard } from "./TaskCard";

const DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const DIAS_SEMANA_LARGO = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

interface Props {
  tareas: Tarea[];
  onChange: (t: Tarea | null, deletedId?: string) => void;
  onOpenReminder: (target: { tarea?: Tarea; subtarea?: import("../types").Subtarea }) => void;
  onEdit: (t: Tarea) => void;
}

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

function getTareasDeFecha(tareas: Tarea[], fecha: string): Tarea[] {
  return tareas.filter((t) => {
    if (t.fecha_limite === fecha) return true;
    if (t.creada_en === fecha) return true;
    if (t.estado === "completada" && t.completada_en === fecha) return true;
    return false;
  });
}

function colorPorEtiqueta(etiqueta: string): string {
  const map: Record<string, string> = {
    habito: "bg-emerald-500",
    emprendimiento: "bg-violet-500",
    investigacion: "bg-cyan-500",
    tarea: "bg-blue-500",
    default: "bg-slate-400",
  };
  return map[etiqueta] || map.default;
}

function colorPorPrioridad(prioridad: string): string {
  const map: Record<string, string> = {
    alta: "bg-red-500",
    media: "bg-amber-500",
    baja: "bg-green-500",
  };
  return map[prioridad] || "bg-slate-400";
}

function formatoFecha(fecha: string) {
  const d = new Date(fecha + "T00:00:00");
  return d.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
}

export function CalendarView({ tareas, onChange, onOpenReminder, onEdit }: Props) {
  const [currentMonth, setCurrentMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState<string>(hoyISO());
  const [vista, setVista] = useState<"mes" | "semana">("mes");

  const hoy = hoyISO();

  const diasGrid = useMemo(() => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const primerDia = new Date(year, month, 1);
    const ultimoDia = new Date(year, month + 1, 0);
    let primerDiaSemana = primerDia.getDay() - 1;
    if (primerDiaSemana < 0) primerDiaSemana = 6;
    const dias: (string | null)[] = [];
    for (let i = 0; i < primerDiaSemana; i++) dias.push(null);
    for (let d = 1; d <= ultimoDia.getDate(); d++) {
      const fecha = new Date(year, month, d).toISOString().slice(0, 10);
      dias.push(fecha);
    }
    return dias;
  }, [currentMonth]);

  const semanaActual = useMemo(() => {
    const d = new Date(selectedDate + "T00:00:00");
    const day = d.getDay(); // 0=dom, 1=lun
    const lunes = new Date(d);
    lunes.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    const dias: string[] = [];
    for (let i = 0; i < 7; i++) {
      const f = new Date(lunes);
      f.setDate(lunes.getDate() + i);
      dias.push(f.toISOString().slice(0, 10));
    }
    return dias;
  }, [selectedDate]);

  const tareasPorFecha = useMemo(() => {
    const map: Record<string, Tarea[]> = {};
    tareas.forEach((t) => {
      const fechas = [t.fecha_limite, t.creada_en, t.completada_en].filter(Boolean) as string[];
      fechas.forEach((f) => {
        if (!map[f]) map[f] = [];
        if (!map[f].find((x) => x.id === t.id)) map[f].push(t);
      });
    });
    return map;
  }, [tareas]);

  const tareasSeleccionadas = getTareasDeFecha(tareas, selectedDate);

  const mesAnterior = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  const mesSiguiente = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  const irHoy = () => {
    const now = new Date();
    setCurrentMonth(new Date(now.getFullYear(), now.getMonth(), 1));
    setSelectedDate(hoy);
  };
  const semanaAnterior = () => {
    const d = new Date(selectedDate + "T00:00:00");
    d.setDate(d.getDate() - 7);
    setSelectedDate(d.toISOString().slice(0, 10));
  };
  const semanaSiguiente = () => {
    const d = new Date(selectedDate + "T00:00:00");
    d.setDate(d.getDate() + 7);
    setSelectedDate(d.toISOString().slice(0, 10));
  };

  const navegarAnterior = vista === "mes" ? mesAnterior : semanaAnterior;
  const navegarSiguiente = vista === "mes" ? mesSiguiente : semanaSiguiente;

  const renderBadge = (t: Tarea) => {
    const color = colorPorEtiqueta(t.etiqueta);
    const prioridad = colorPorPrioridad(t.prioridad);
    return (
      <div className={`flex items-center gap-1.5 px-1.5 py-1 rounded-md text-[10px] leading-tight bg-white/5 border border-white/10 ${t.estado === "completada" ? "opacity-50 line-through" : ""}`}>
        <div className={`w-1.5 h-1.5 rounded-full ${color}`} />
        <span className="flex-1 truncate text-text">{t.titulo}</span>
        <div className={`w-1 h-1 rounded-full ${prioridad}`} />
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header estilo Apple Calendar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">
            {vista === "mes"
              ? `${MESES[currentMonth.getMonth()]} ${currentMonth.getFullYear()}`
              : `Semana del ${formatoFecha(semanaActual[0])}`}
          </h3>
          <div className="flex items-center bg-card border border-border rounded-lg p-0.5">
            <button onClick={() => setVista("mes")} className={`p-1.5 rounded-md transition-colors ${vista === "mes" ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
              <LayoutGrid size={14} />
            </button>
            <button onClick={() => setVista("semana")} className={`p-1.5 rounded-md transition-colors ${vista === "semana" ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
              <Rows3 size={14} />
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={navegarAnterior} className="p-2 rounded-lg bg-card border border-border text-muted hover:text-text transition-colors">
            <ChevronLeft size={18} />
          </button>
          <button onClick={irHoy} className="px-3 py-1.5 rounded-lg bg-card border border-border text-xs font-medium text-text hover:border-accent transition-colors">
            Hoy
          </button>
          <button onClick={navegarSiguiente} className="p-2 rounded-lg bg-card border border-border text-muted hover:text-text transition-colors">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {vista === "mes" ? (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          {/* Días de la semana */}
          <div className="grid grid-cols-7 border-b border-border">
            {DIAS_SEMANA.map((d) => (
              <div key={d} className="text-center text-[11px] font-medium text-muted py-2">
                {d}
              </div>
            ))}
          </div>

          {/* Grid mensual */}
          <div className="grid grid-cols-7 auto-rows-fr">
            {diasGrid.map((fecha, i) => {
              if (!fecha) return <div key={i} className="min-h-[96px] border-b border-r border-border bg-bg/30" />;
              const dia = parseInt(fecha.slice(8));
              const esHoy = fecha === hoy;
              const esSeleccionada = fecha === selectedDate;
              const lista = tareasPorFecha[fecha] || [];
              const tieneVencidas = lista.some((t) => t.fecha_limite === fecha && t.estado !== "completada" && fecha < hoy);

              return (
                <button
                  key={i}
                  onClick={() => setSelectedDate(fecha)}
                  className={`min-h-[96px] border-b border-r border-border p-1.5 text-left transition-colors relative ${
                    esSeleccionada ? "bg-accent/10" : "hover:bg-bg/50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`w-6 h-6 flex items-center justify-center text-[11px] font-medium rounded-full ${
                      esHoy ? "bg-accent text-white" : esSeleccionada ? "text-accent" : "text-text"
                    }`}>
                      {dia}
                    </span>
                    {tieneVencidas && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
                  </div>
                  <div className="space-y-1">
                    {lista.slice(0, 3).map((t) => (
                      <div key={t.id}>{renderBadge(t)}</div>
                    ))}
                    {lista.length > 3 && (
                      <div className="text-[9px] text-muted pl-1">+{lista.length - 3} más</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="grid grid-cols-7 auto-rows-fr min-h-[320px]">
            {semanaActual.map((fecha, i) => {
              const esHoy = fecha === hoy;
              const esSeleccionada = fecha === selectedDate;
              const lista = tareasPorFecha[fecha] || [];
              return (
                <button
                  key={fecha}
                  onClick={() => setSelectedDate(fecha)}
                  className={`border-r border-border p-2 text-left transition-colors flex flex-col gap-2 ${esSeleccionada ? "bg-accent/10" : "hover:bg-bg/50"}`}
                >
                  <div className="text-center">
                    <div className="text-[10px] text-muted uppercase">{DIAS_SEMANA[i]}</div>
                    <div className={`w-7 h-7 mx-auto flex items-center justify-center text-sm font-semibold rounded-full mt-0.5 ${esHoy ? "bg-accent text-white" : "text-text"}`}>
                      {parseInt(fecha.slice(8))}
                    </div>
                  </div>
                  <div className="space-y-1 flex-1">
                    {lista.length === 0 && <div className="text-[10px] text-muted/60 text-center mt-4">Sin tareas</div>}
                    {lista.map((t) => (
                      <div key={t.id}>{renderBadge(t)}</div>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Tareas del día seleccionado */}
      <div className="mt-4">
        <div className="flex items-center gap-2 mb-3">
          <CalIcon size={16} className="text-accent" />
          <h4 className="text-sm font-semibold">{formatoFecha(selectedDate)}</h4>
          <span className="text-xs text-muted">({tareasSeleccionadas.length} tarea{tareasSeleccionadas.length !== 1 ? "s" : ""})</span>
        </div>

        {tareasSeleccionadas.length === 0 ? (
          <div className="text-center text-muted py-8 bg-card border border-border rounded-2xl">
            <CalIcon size={32} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">No hay tareas para esta fecha</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {tareasSeleccionadas.map((t) => (
              <TaskCard key={t.id} tarea={t} onChange={onChange} onOpenReminder={onOpenReminder} onEdit={onEdit} compact />
            ))}
          </div>
        )}
      </div>

      {/* Leyenda de colores */}
      <div className="mt-4 flex flex-wrap gap-3 text-[10px] text-muted">
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" />Hábito</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-500" />Emprendimiento</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-500" />Investigación</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" />Tarea</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />Alta</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" />Media</div>
        <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Baja</div>
      </div>
    </div>
  );
}
