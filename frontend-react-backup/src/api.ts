import type { Tarea, Recordatorio, AgenteResumen, AgenteCheckin, VozResultado, TareaDraft, AgentePlanResultado, AgenteBuscarResultado, AgenteIdeaResultado, AgentePreguntaResultado, MemoriaResultado, Agente, Skill, Knowledge, GitHubRepo } from "./types";

const API = "/api";

async function req<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  console.log(`[api] ${method} ${API + path}`, body);
  const res = await fetch(API + path, opts);
  console.log(`[api] ${method} ${API + path} -> status ${res.status}`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error(`[api] ${method} ${API + path} error body:`, text);
    throw new Error(`Error ${res.status}: ${text}`);
  }
  if (res.status === 204) return null as T;
  const data = await res.json();
  console.log(`[api] ${method} ${API + path} -> data:`, data);
  return data;
}

export const api = {
  // Tareas
  listarTareas: () => req<Tarea[]>("/tareas"),
  crearTarea: (data: { titulo: string; descripcion: string; prioridad: string; fecha_limite: string | null; etiqueta: string; repetible: boolean; horas: string[]; dias_semana: string[]; objetivo: string }) =>
    req<Tarea>("/tareas", "POST", data),
  actualizarTarea: (id: string, data: Partial<{ titulo: string; descripcion: string; prioridad: string; fecha_limite: string | null; completada_manual: boolean; etiqueta: string; repetible: boolean; horas: string[]; dias_semana: string[]; objetivo: string }>) =>
    req<Tarea>(`/tareas/${id}`, "PATCH", data),
  eliminarTarea: (id: string) => req(`/tareas/${id}`, "DELETE"),

  // Subtareas
  agregarSubtarea: (tareaId: string, titulo: string) =>
    req<Tarea>(`/tareas/${tareaId}/subtareas`, "POST", { titulo }),
  actualizarSubtarea: (id: string, data: Partial<{ titulo: string; completada: boolean }>) =>
    req<Tarea>(`/subtareas/${id}`, "PATCH", data),
  eliminarSubtarea: (id: string) => req<Tarea>(`/subtareas/${id}`, "DELETE"),

  // Recordatorios
  listarRecordatorios: () => req<Recordatorio[]>("/recordatorios"),
  crearRecordatorio: (data: { titulo: string; fecha_hora: string; tarea_id: string; subtarea_id: string | null }) =>
    req<Recordatorio>("/recordatorios", "POST", data),
  actualizarRecordatorio: (id: string, data: Partial<{ titulo: string; fecha_hora: string; estado: string }>) =>
    req<Recordatorio>(`/recordatorios/${id}`, "PATCH", data),
  eliminarRecordatorio: (id: string) => req(`/recordatorios/${id}`, "DELETE"),

  // Agente
  agenteRecordatorio: () => req<AgenteResumen>("/agente/recordatorio"),
  agenteCheckin: () => req<AgenteCheckin>("/agente/checkin"),

  // Agentes especializados
  listarAgentes: () => req<{ agentes: Agente[]; skills: Skill[]; knowledge: Knowledge[] }>("/agentes"),
  crearAgente: (data: { nombre: string; descripcion: string; modelo: string; system_prompt: string; skills: string[]; knowledge: string[] }) =>
    req<{ agente: Agente }>("/agentes", "POST", data),
  actualizarAgente: (id: string, data: Partial<{ nombre: string; descripcion: string; modelo: string; system_prompt: string; skills: string[]; knowledge: string[] }>) =>
    req<{ agente: Agente }>(`/agentes/${id}`, "PATCH", data),
  eliminarAgente: (id: string) => req(`/agentes/${id}`, "DELETE"),
  ejecutarAgente: (id: string, prompt: string, tareaId?: string) => req<{ respuesta: string }>(`/agentes/${id}/ejecutar`, "POST", { prompt, tarea_id: tareaId }),
  ejecutarAgentesParalelo: (agenteIds: string[], prompt: string) => req<{ resultados: { agente_id: string; agente_nombre: string; respuesta?: string; error?: string }[] }>("/agentes/ejecutar-paralelo", "POST", { agente_ids: agenteIds, prompt }),

  // Skills y knowledge
  crearSkill: (data: { nombre: string; descripcion: string; instrucciones: string }) => req<{ skill: Skill }>("/skills", "POST", data),
  actualizarSkill: (id: string, data: { nombre: string; descripcion: string; instrucciones: string }) => req<{ skill: Skill }>(`/skills/${id}`, "PATCH", data),
  eliminarSkill: (id: string) => req(`/skills/${id}`, "DELETE"),
  crearKnowledge: (data: { nombre: string; tipo: string; contenido: string }) => req<{ knowledge: Knowledge }>("/knowledge", "POST", data),
  actualizarKnowledge: (id: string, data: { nombre: string; tipo: string; contenido: string }) => req<{ knowledge: Knowledge }>(`/knowledge/${id}`, "PATCH", data),
  eliminarKnowledge: (id: string) => req(`/knowledge/${id}`, "DELETE"),
  agentePlan: (objetivo: string, semanas: number = 4) => req<AgentePlanResultado>("/agente/plan", "POST", { objetivo, semanas }),
  agenteBuscar: (tema: string) => req<AgenteBuscarResultado>("/agente/buscar", "POST", { tema }),
  agenteIdea: (prompt: string) => req<AgenteIdeaResultado>("/agente/idea", "POST", { prompt }),
  resumenTarea: (id: string) => req<{ resumen: string }>("/agente/resumen-tarea", "POST", { tarea_id: id }),
  crearChatSesion: (tareaId: string, nombre: string) => req<{ tarea: Tarea }>(`/tareas/${tareaId}/chat-sesiones`, "POST", { tarea_id: tareaId, nombre }),
  enviarChatMensaje: (tareaId: string, sesionId: string, texto: string) => req<{ tarea: Tarea; respuesta: string }>(`/tareas/${tareaId}/chat-mensajes`, "POST", { tarea_id: tareaId, sesion_id: sesionId, texto }),
  actualizarProximaAltaValor: (tareaId: string, texto: string) => req<{ tarea: Tarea }>(`/tareas/${tareaId}/proxima-alta-valor`, "POST", { tarea_id: tareaId, sesion_id: "manual", texto }),
  agentePreguntar: (pregunta: string, k: number = 5) => req<AgentePreguntaResultado>("/agente/preguntar", "POST", { pregunta, k }),

  // GitHub
  getGitHubConfig: () => req<{ username: string; configured: boolean }>("/github/config"),
  setGitHubConfig: (pat: string, username: string = "") =>
    req<{ ok: boolean; username: string; scopes: string[] }>("/github/config", "POST", { pat, username }),
  listGitHubRepos: () => req<{ repos: GitHubRepo[] }>("/github/repos"),
  linkGitHubRepo: (tareaId: string, repo: string) => req<{ tarea: Tarea }>(`/tareas/${tareaId}/github`, "POST", { repo }),
  unlinkGitHubRepo: (tareaId: string) => req<{ tarea: Tarea }>(`/tareas/${tareaId}/github`, "DELETE"),
  agenteDesarrollar: (tareaId: string, prompt: string = "") =>
    req<{ ok: boolean; repo: string; branch: string; pr: { url: string; number: number }; archivos: string[]; resumen: string; pros: string[]; contras: string[]; error?: string }>(`/tareas/${tareaId}/agente-desarrollar`, "POST", { prompt }),
  getGitHubStatus: (tareaId: string) =>
    req<{ tarea: Tarea; pr_status: { url: string; state: string; merged: boolean } | null }>(`/tareas/${tareaId}/github-status`),
  mergeGitHubPR: (tareaId: string) => req<{ merged: boolean; sha?: string }>(`/tareas/${tareaId}/github-merge`, "POST"),

  // Memoria vectorial
  crearMemoria: (texto: string, fuente: string = "manual", metadata?: Record<string, unknown>) =>
    req<{ ok: boolean; ids: string[]; mensaje: string }>("/memorias", "POST", { texto, fuente, metadata }),
  buscarMemoria: (consulta: string, k: number = 5, fuente?: string) =>
    req<{ consulta: string; resultados: MemoriaResultado[] }>("/memorias/buscar", "POST", { consulta, k, fuente }),
  syncTareasMemoria: () => req<{ ok: boolean; tareas_indexadas: number }>("/memorias/sync-tareas", "POST"),
  statsMemoria: () => req<{ total_registros: number; ruta: string }>("/memorias/stats"),

  // Voz
  vozProcesar: (texto: string) => req<VozResultado>("/voz/procesar", "POST", { texto }),
  vozConfirmar: (draft: TareaDraft) => req<VozResultado>("/voz/confirmar", "POST", { draft }),
  vozActualizar: (tareaId: string, cambios: Partial<Tarea>) => req<VozResultado>("/voz/actualizar", "POST", { tarea_id: tareaId, cambios }),
  vozResumen: () => req<{ mensaje: string }>("/voz/resumen"),
  vozConfig: () => req<{ groq: boolean; local_whisper: boolean; speech_api: boolean; tts_premium: boolean }>("/voz/config"),
  vozTranscribir: async (audioBlob: Blob) => {
    const res = await fetch(API + "/voz/transcribir", {
      method: "POST",
      body: audioBlob,
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json() as Promise<{ texto: string }>;
  },
};
