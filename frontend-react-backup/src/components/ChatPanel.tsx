import { useState } from "react";
import { Send, Plus, MessageSquare, Sparkles, Loader2, CheckSquare } from "lucide-react";
import type { Tarea, ChatSession } from "../types";
import { api } from "../api";

interface Props {
  tarea: Tarea;
  onChange: (t: Tarea) => void;
}

export function ChatPanel({ tarea, onChange }: Props) {
  const sesiones = tarea.chat_sesiones || [];
  const [activeId, setActiveId] = useState<string>(sesiones[0]?.id || "");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeSession = sesiones.find((s) => s.id === activeId) || (sesiones[0] as ChatSession | undefined);

  const createSession = async () => {
    setLoading(true);
    try {
      const res = await api.crearChatSesion(tarea.id, `Sesión ${sesiones.length + 1}`);
      onChange(res.tarea);
      const newId = res.tarea.chat_sesiones[res.tarea.chat_sesiones.length - 1]?.id || "";
      setActiveId(newId);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !activeSession) return;
    const text = input.trim();
    setInput("");
    setLoading(true);
    setError(null);
    console.log("[ChatPanel] Enviando mensaje:", { tareaId: tarea.id, sesionId: activeSession.id, texto: text });
    try {
      const res = await api.enviarChatMensaje(tarea.id, activeSession.id, text);
      console.log("[ChatPanel] Respuesta recibida:", res);
      onChange(res.tarea);
    } catch (e: any) {
      console.error("[ChatPanel] Error enviando mensaje:", e);
      setError(e?.message || "No se pudo enviar el mensaje.");
    } finally {
      setLoading(false);
    }
  };

  const acceptSubtasks = async () => {
    // La creación de subtareas ya es automática en el backend; este botón puede usarse para refrescar.
    onChange(tarea);
  };

  return (
    <div className="bg-card2 border border-border rounded-2xl overflow-hidden flex flex-col h-[420px] lg:h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-accent" />
          <span className="text-sm font-semibold text-text">Chat del agente</span>
        </div>
        <button
          onClick={createSession}
          disabled={loading}
          className="flex items-center gap-1 text-[10px] font-medium bg-accent text-white rounded-lg px-2.5 py-1.5 disabled:opacity-50"
        >
          <Plus size={10} /> Nueva sesión
        </button>
      </div>

      {/* Selector de sesiones */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border overflow-x-auto">
        {sesiones.length === 0 ? (
          <span className="text-[10px] text-muted">No hay sesiones. Crea una para empezar.</span>
        ) : (
          sesiones.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveId(s.id)}
              className={`text-[10px] font-medium px-2.5 py-1 rounded-lg whitespace-nowrap border transition-colors ${
                activeId === s.id
                  ? "bg-accent text-white border-accent"
                  : "bg-card border-border text-muted hover:text-text"
              }`}
            >
              {s.nombre}
            </button>
          ))
        )}
      </div>

      {/* Mensajes */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {activeSession ? (
          activeSession.mensajes.map((m) => (
            <div key={m.id} className={`flex ${m.rol === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] text-xs rounded-xl px-3 py-2 leading-relaxed ${
                  m.rol === "user"
                    ? "bg-accent text-white"
                    : "bg-card border border-border text-text"
                }`}
              >
                {m.texto}
              </div>
            </div>
          ))
        ) : (
          <div className="text-center text-[11px] text-muted py-8">
            Crea una sesión para conversar con el agente sobre esta tarea.
          </div>
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-card border border-border rounded-xl px-3 py-2 flex items-center gap-2">
              <Loader2 size={12} className="animate-spin text-accent" />
              <span className="text-[10px] text-muted">Jarvis está escribiendo...</span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-border">
        {error && (
          <div className="mb-2 text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex items-center gap-2">
          <input
            className="flex-1 bg-bg border border-border rounded-xl px-3 py-2 text-xs text-text placeholder-muted"
            placeholder="Pide ayuda para generar subtareas..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            disabled={!activeSession || loading}
          />
          <button
            onClick={sendMessage}
            disabled={!activeSession || loading || !input.trim()}
            className="bg-accent text-white rounded-xl px-3 py-2 disabled:opacity-50"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
        <div className="flex items-center gap-3 mt-2">
          <div className="flex items-center gap-1 text-[10px] text-accent">
            <Sparkles size={10} />
            {tarea.proxima_alta_valor || "Sin acción prioritaria definida aún"}
          </div>
          <button onClick={acceptSubtasks} className="ml-auto text-[10px] text-muted hover:text-text flex items-center gap-1">
            <CheckSquare size={10} /> Subtareas actualizadas
          </button>
        </div>
      </div>
    </div>
  );
}
