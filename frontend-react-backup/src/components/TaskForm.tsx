import { useState, useCallback } from "react";
import { Plus, Repeat, Rocket, CheckSquare, Heart, ChevronDown, Search, Clock, X, Mic, Loader2, Lightbulb } from "lucide-react";
import { api } from "../api";
import { useSpeechRecognition } from "../hooks/useVoice";
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

export function TaskForm({ onCreated }: { onCreated: (t: Tarea) => void }) {
  const [titulo, setTitulo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [prioridad, setPrioridad] = useState("media");
  const [etiqueta, setEtiqueta] = useState("tarea");
  const [objetivo, setObjetivo] = useState("");
  const [repetible, setRepetible] = useState(false);
  const [expandido, setExpandido] = useState(false);
  const [horas, setHoras] = useState<string[]>([]);
  const [nuevaHora, setNuevaHora] = useState("");
  const [diasSemana, setDiasSemana] = useState<string[]>([]);
  const [vozError, setVozError] = useState<string | null>(null);
  const { state: vozState, start, stop, supported, error: vozErrorHook } = useSpeechRecognition();

  const esHabito = etiqueta === "habito";
  const escuchando = vozState === "listening";
  const procesando = vozState === "processing";

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

  const procesarVoz = useCallback(async (texto: string) => {
    try {
      setVozError(null);
      const res = await api.vozProcesar(texto);
      if (res.draft) {
        // Confirmar automáticamente para mantener el flujo rápido desde el input
        const confirm = await api.vozConfirmar(res.draft);
        if (confirm.tarea_creada) {
          onCreated(confirm.tarea_creada);
          setTitulo("");
          setDescripcion("");
          setPrioridad("media");
          setEtiqueta("tarea");
          setObjetivo("");
          setRepetible(false);
          setHoras([]);
          setDiasSemana([]);
          setExpandido(false);
        }
      } else if (res.tarea_creada) {
        onCreated(res.tarea_creada);
        setTitulo("");
        setDescripcion("");
        setPrioridad("media");
        setEtiqueta("tarea");
        setObjetivo("");
        setRepetible(false);
        setHoras([]);
        setDiasSemana([]);
        setExpandido(false);
      } else if (res.mensaje) {
        setVozError(res.mensaje);
      }
    } catch (e) {
      console.error(e);
      setVozError("No pude entender el mensaje de voz. Intenta de nuevo.");
    }
  }, [onCreated]);

  const toggleMicrofono = useCallback(() => {
    if (escuchando) {
      stop();
      return;
    }
    if (procesando) return;
    setVozError(null);
    start(procesarVoz);
  }, [escuchando, procesando, start, stop, procesarVoz]);

  const crear = async () => {
    if (!titulo.trim()) return;
    const finalRepetible = esHabito ? true : repetible;
    const finalHoras = esHabito ? horas : [];
    const finalDias = esHabito ? diasSemana : [];
    try {
      const t = await api.crearTarea({
        titulo,
        descripcion,
        prioridad,
        fecha_limite: null,
        etiqueta,
        repetible: finalRepetible,
        horas: finalHoras,
        dias_semana: finalDias,
        objetivo: objetivo.trim(),
      });
      onCreated(t);
      setTitulo("");
      setDescripcion("");
      setPrioridad("media");
      setEtiqueta("tarea");
      setObjetivo("");
      setRepetible(false);
      setHoras([]);
      setDiasSemana([]);
      setExpandido(false);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-lg">
      <div className="relative mb-3">
        <input
          className="w-full bg-bg border border-border rounded-xl pl-4 pr-12 py-3.5 text-base text-text placeholder-muted"
          placeholder={escuchando ? "Escuchando..." : "¿Qué necesitas hacer?"}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && crear()}
          onFocus={() => setExpandido(true)}
        />
        <button
          onClick={toggleMicrofono}
          disabled={!supported || procesando}
          className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${
            escuchando
              ? "bg-green-500 text-white shadow-lg shadow-green-500/30 animate-pulse"
              : procesando
              ? "bg-amber-500 text-white"
              : "bg-card border border-border text-muted hover:text-accent"
          }`}
          title={escuchando ? "Detener y procesar" : "Hablar para crear tarea"}
        >
          {procesando ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} />}
        </button>
      </div>

      {(vozError || vozErrorHook) && (
        <div className="mb-3 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 flex items-start gap-2">
          <span className="mt-0.5">⚠️</span>
          <span>{vozError || vozErrorHook}</span>
        </div>
      )}

      {expandido && (
        <>
          <textarea
            className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted mb-3 resize-none"
            placeholder="Descripción (opcional)..."
            rows={2}
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />

          <input
            className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted mb-3"
            placeholder="Objetivo / área / proyecto (opcional). Ej: Preparación maestría IA, TREAS, Fitness..."
            value={objetivo}
            onChange={(e) => setObjetivo(e.target.value)}
          />

          {/* Tipo de tarea */}
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
                  onClick={() => setPrioridad(key)}
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

          {/* Configuración de hábito */}
          {esHabito && (
            <div className="mb-3 bg-pink-500/5 border border-pink-500/20 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-3">
                <Repeat size={14} className="text-pink-300" />
                <span className="text-xs font-semibold text-pink-300">Configuración de hábito</span>
              </div>

              {/* Días de la semana */}
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

              {/* Horas */}
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

          {/* Repetible (solo si no es hábito) */}
          {!esHabito && (
            <div className="flex items-center justify-between mb-3">
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
        </>
      )}

      <div className="flex items-center justify-between gap-2">
        {expandido && (
          <button
            className="text-xs text-muted hover:text-text transition-colors"
            onClick={() => setExpandido(false)}
          >
            <ChevronDown size={16} className="inline" /> Menos
          </button>
        )}
        <button
          className="ml-auto bg-accent text-white rounded-xl px-5 py-2.5 text-sm font-semibold hover:opacity-90 transition-opacity flex items-center gap-1.5"
          onClick={crear}
        >
          <Plus size={18} />
          Crear tarea
        </button>
      </div>
    </div>
  );
}
