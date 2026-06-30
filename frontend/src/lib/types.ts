export interface SubtareaIteracion {
	timestamp: string;
	resultado: string;
	plan: string;
	score: number;
	resumen: string;
	feedback: string;
}

export interface Subtarea {
	id: string;
	titulo: string;
	completada: boolean;
	estado: 'pendiente' | 'en_progreso' | 'bloqueada' | 'completada';
	descripcion: string;
	prompt: string;
	resultado: string;
	repo: string;
	branch: string;
	archivo: string;
	commit_pendiente: boolean;
	commit_sha?: string | null;
	commit_en?: string | null;
	plan?: string;
	revision?: string;
	resumen?: string;
	score?: number;
	iteraciones?: SubtareaIteracion[];
}

export interface ChatMessage {
	id: string;
	rol: 'user' | 'assistant' | 'system';
	texto: string;
	creado_en: string;
}

export interface ChatSession {
	id: string;
	nombre: string;
	creado_en: string;
	mensajes: ChatMessage[];
}

export interface ChatAdjunto {
	nombre: string;
	tipo: string;
	contenido: string;
}

export interface ModeloAgente {
	id: string;
	nombre: string;
	proveedor: string;
	descripcion: string;
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
	tipo: 'texto' | 'url' | 'archivo';
	contenido: string;
	creado_en: string;
}

export interface ChangelogEntry {
	id: string;
	fecha: string;
	version: string;
	seccion: string;
	impacto: 'bajo' | 'medio' | 'alto' | 'critico';
	cambios: string[];
	casos_qa: string[];
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
	prioridad: 'alta' | 'media' | 'baja';
	fecha_limite: string | null;
	etiqueta: string;
	repetible: boolean;
	horas: string[];
	dias_semana: string[];
	objetivo: string;
	documento: string;
	proxima_alta_valor: string;
	chat_sesiones: ChatSession[];
	canvas: TareaCanvas | null;
	github_repo: string;
	github_branch: string;
	github_pr_url: string;
	github_pr_number: number | null;
	github_status: string;
	github_agent_log: Record<string, unknown>;
	completada_manual: boolean;
	completada_en: string | null;
	creada_en: string;
	numero: number;
	icono?: string;
	color?: string;
	habito_log: string[];
	subtareas: Subtarea[];
	subtareas_total: number;
	subtareas_completadas: number;
	progreso: number;
	estado: 'pendiente' | 'completada';
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
	estado: 'pendiente' | 'completado';
	tarea_titulo: string | null;
	subtarea_titulo: string | null;
	proximo: boolean;
}

export type WSMessage =
	| { type: 'tareas_changed' }
	| { type: 'recordatorios_changed' };

export type EtiquetaKey = 'todas' | 'emprendimiento' | 'tarea' | 'habito' | 'investigacion' | 'idea';

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
	prioridad: 'alta' | 'media' | 'baja';
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
	accion: 'confirmar_tarea' | 'agregar_subtarea' | 'crear_tarea' | 'resumen' | 'priorizar' | 'consultar' | 'no_entendido' | 'error';
	mensaje: string;
	tarea_creada: Tarea | null;
	draft: TareaDraft | null;
	tarea_actualizada?: Tarea;
	tarea_numero?: number | null;
	subtarea_titulo?: string | null;
}

export interface ChatGlobalMessage {
	role: 'user' | 'assistant';
	content: string;
	accion?: string;
	date?: string;
	opciones?: string[];
}

export interface ChatGlobalResultado {
	accion: 'conversar' | 'crear_tarea' | 'actualizar_tarea' | 'agregar_subtareas' | 'eliminar_tarea' | 'ejecutar_subtarea' | 'commitear_subtarea' | 'sincronizar_subtareas' | 'eliminar_subtarea' | 'crear_recordatorio' | 'actualizar_recordatorio' | 'eliminar_recordatorio' | 'error';
	mensaje: string;
	tarea?: Tarea | null;
	tarea_numero?: number | null;
	subtarea_id?: string | null;
	subtareas?: string[];
	cambios?: Record<string, unknown>;
	recordatorio?: Recordatorio | null;
	opciones?: string[];
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

export interface CanvasBloque {
	id: string;
	tipo: 'texto' | 'idea' | 'codigo' | 'json' | 'curl' | 'imagen' | 'tabla' | 'diagrama';
	x: number;
	y: number;
	width: number;
	height: number;
	texto?: string;
	contenido?: any;
	importante?: boolean;
	recordatorio?: { at: number; repeat?: string; done?: boolean } | null;
	kanban?: 'todo' | 'doing' | 'done' | null;
	kanbanOrder?: number;
}

export interface CanvasLink {
	id: string;
	a: string;
	b: string;
}

export interface CanvasLogEntry {
	id: string;
	ts: number;
	action: string;
	detail?: string;
}

export interface TareaCanvas {
	bloques: CanvasBloque[];
	links: CanvasLink[];
	log?: CanvasLogEntry[];
	view?: { zoom: number };
}

export interface CanvasInterpretacion {
	ok: boolean;
	error?: string;
	interpretacion: string;
	oportunidades: string[];
	ideas: string[];
	riesgos: string[];
}
