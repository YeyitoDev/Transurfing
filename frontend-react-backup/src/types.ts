export interface Subtarea {
  id: string;
  titulo: string;
  completada: boolean;
}

export interface ChatMessage {
  id: string;
  rol: "user" | "assistant" | "system";
  texto: string;
  creado_en: string;
}

export interface ChatSession {
  id: string;
  nombre: string;
  creado_en: string;
  mensajes: ChatMessage[];
}

export interface Skill {
  id: string;
  nombre: string;
  descripcion: string;
  instrucciones: string;
  creado_en: string;
}

export interface Knowledge {
  id: string;
  nombre: string;
  tipo: "texto" | "url" | "archivo";
  contenido: string;
  creado_en: string;
}

export interface Agente {
  id: string;
  nombre: string;
  descripcion: string;
  modelo: string;
  system_prompt: string;
  skills: string[];
  knowledge: string[];
  creado_en: string;
}

export interface Tarea {
  id: string;
  titulo: string;
  descripcion: string;
  prioridad: "alta" | "media" | "baja";
  fecha_limite: string | null;
  etiqueta: string;
  repetible: boolean;
  horas: string[];
  dias_semana: string[];
  objetivo: string;
  documento: string;
  proxima_alta_valor: string;
  chat_sesiones: ChatSession[];
  github_repo: string;
  github_branch: string;
  github_pr_url: string;
  github_pr_number: number | null;
  github_status: string;
  github_agent_log: Record<string, unknown>;
  completada_manual: boolean;
  completada_en: string | null;
  creada_en: string;
  subtareas: Subtarea[];
  subtareas_total: number;
  subtareas_completadas: number;
  progreso: number;
  estado: "pendiente" | "completada";
}

export interface GitHubRepo {
  full_name: string;
  name: string;
  owner: string;
  default_branch: string;
  url: string;
}

export interface Recordatorio {
  id: string;
  titulo: string;
  fecha_hora: string;
  tarea_id: string;
  subtarea_id: string | null;
  estado: "pendiente" | "completado";
  tarea_titulo: string | null;
  subtarea_titulo: string | null;
  proximo: boolean;
}

export type WSMessage =
  | { type: "tareas_changed" }
  | { type: "recordatorios_changed" };

export type TabKey = "pendientes" | "completadas" | "alarmas" | "kanban" | "calendario";
export type EtiquetaKey = "todas" | "emprendimiento" | "tarea" | "habito" | "investigacion" | "idea";

export interface AgenteTareaDestacada {
  id: string;
  titulo: string;
  prioridad: string;
  descripcion: string;
  fecha_limite: string | null;
  vencida: boolean;
}

export interface AgenteTareaEstancada {
  id: string;
  titulo: string;
  descripcion: string;
  dias: number;
  progreso: number;
  etiqueta: string;
  prioridad: string;
}

export interface AgenteIdea {
  tarea_id: string;
  titulo: string;
  progreso: number;
  sugerencia: string;
}

export interface AgenteNoticia {
  tarea_id: string;
  titulo: string;
  temas: string[];
}

export interface AgenteResumen {
  titulo: string;
  mensaje: string;
  tareas: AgenteTareaDestacada[];
  total: number;
  vencidas: number;
  alta: number;
  media: number;
  baja: number;
  en_progreso: number;
  sin_empezar: number;
  estancadas: AgenteTareaEstancada[];
  ideas: AgenteIdea[];
  noticias: AgenteNoticia[];
  preguntas: string[];
}

export interface AgenteCheckin {
  titulo: string;
  mensaje: string;
  preguntas: string[];
  total: number;
  vencidas: number;
}

export interface TareaDraft {
  titulo: string;
  descripcion: string;
  etiqueta: string;
  prioridad: "alta" | "media" | "baja";
  horas: string[];
  dias_semana: string[];
  repetible: boolean;
  objetivo: string;
  fecha_limite?: string | null;
}

export interface AgentePlanResultado {
  accion: string;
  mensaje: string;
  plan: {
    semanas: number;
    frecuencia: string;
    primer_paso: string;
  };
  tareas: TareaDraft[];
}

export interface AgenteBuscarResultado {
  accion: string;
  mensaje: string;
  recursos: { titulo: string; tipo: string; url: string; relevancia: string }[];
}

export interface AgenteIdeaResultado {
  accion: string;
  mensaje?: string;
  tarea?: Tarea;
}

export interface VozResultado {
  accion: "confirmar_tarea" | "crear_tarea" | "resumen" | "priorizar" | "consultar" | "no_entendido" | "error";
  mensaje: string;
  tarea_creada: Tarea | null;
  draft: TareaDraft | null;
  tarea_actualizada?: Tarea;
}

export interface MemoriaResultado {
  id: string;
  text: string;
  source: string;
  source_id: string | null;
  created_at: string;
  distance: number;
}

export interface AgentePreguntaResultado {
  respuesta: string;
  fuentes: MemoriaResultado[];
  modelo: string;
}
