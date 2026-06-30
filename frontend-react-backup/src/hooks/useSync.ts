import { useState, useEffect, useCallback, useRef } from "react";
import type { Tarea, Recordatorio, WSMessage } from "../types";
import { api } from "../api";
import { WebSocketClient } from "../ws";

const wsClient = new WebSocketClient();

export function useSync() {
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [recordatorios, setRecordatorios] = useState<Recordatorio[]>([]);
  const [loading, setLoading] = useState(true);

  const cargarTareas = useCallback(async () => {
    try {
      const t = await api.listarTareas();
      setTareas(t);
    } catch (e) {
      console.error("Error cargando tareas:", e);
    }
  }, []);

  const cargarRecordatorios = useCallback(async () => {
    try {
      const r = await api.listarRecordatorios();
      setRecordatorios(r);
    } catch (e) {
      console.error("Error cargando recordatorios:", e);
    }
  }, []);

  const cargarTodo = useCallback(async () => {
    setLoading(true);
    await Promise.all([cargarTareas(), cargarRecordatorios()]);
    setLoading(false);
  }, [cargarTareas, cargarRecordatorios]);

  // Carga inicial
  useEffect(() => {
    cargarTodo();
  }, [cargarTodo]);

  // WebSocket: refrescar al recibir notificación
  useEffect(() => {
    wsClient.connect();
    const unsub = wsClient.onMessage((msg: WSMessage) => {
      if (msg.type === "tareas_changed") cargarTareas();
      if (msg.type === "recordatorios_changed") cargarRecordatorios();
    });

    // Fallback: polling cada 15 seg por si WS falla
    const pollId = setInterval(() => {
      if (!wsClient || document.visibilityState === "visible") {
        cargarTareas();
        cargarRecordatorios();
      }
    }, 15000);

    return () => {
      unsub();
      clearInterval(pollId);
    };
  }, [cargarTareas, cargarRecordatorios]);

  return { tareas, recordatorios, loading, cargarTareas, cargarRecordatorios, setTareas, setRecordatorios };
}

export function useNotifications(recordatorios: Recordatorio[]) {
  const [enabled, setEnabled] = useState(false);
  const notifiedIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if ("Notification" in window) {
      setEnabled(Notification.permission === "granted");
    }
  }, []);

  const requestPermission = useCallback(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then((perm) => setEnabled(perm === "granted"));
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const check = () => {
      const ahora = new Date().toISOString().slice(0, 16);
      recordatorios.forEach((r) => {
        if (r.estado !== "completado" && r.fecha_hora <= ahora && !notifiedIds.current.has(r.id)) {
          notifiedIds.current.add(r.id);
          const n = new Notification("⏰ Recordatorio", {
            body: r.titulo + (r.tarea_titulo ? ` — ${r.tarea_titulo}` : ""),
            tag: r.id,
            requireInteraction: true,
          });
          n.onclick = () => {
            window.focus();
            n.close();
          };
        }
      });
    };
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, [recordatorios, enabled]);

  return { enabled, requestPermission };
}
