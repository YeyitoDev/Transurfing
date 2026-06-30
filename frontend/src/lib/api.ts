import type {
	Tarea,
	Recordatorio,
	AgenteResumen,
	AgenteCheckin,
	VozResultado,
	TareaDraft,
	AgentePlanResultado,
	AgenteBuscarResultado,
	AgenteIdeaResultado,
	AgentePreguntaResultado,
	MemoriaResultado,
	Agente,
	Skill,
	Knowledge,
	GitHubRepo,
	ChangelogEntry,
	ChatGlobalResultado,
	ChatGlobalMessage,
	TareaCanvas,
	CanvasInterpretacion
} from './types';

const API = '/api';

async function req<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = typeof localStorage !== 'undefined' ? localStorage.getItem('api_token') : null;
	if (token) headers['X-API-Token'] = token;
	const opts: RequestInit = { method, headers };
	if (body) opts.body = JSON.stringify(body);
	console.log(`[api] ${method} ${API + path}`, body);
	const res = await fetch(API + path, opts);
	console.log(`[api] ${method} ${API + path} -> status ${res.status}`);
	if (!res.ok) {
		const text = await res.text().catch(() => '');
		console.error(`[api] ${method} ${API + path} error body:`, text);
		throw new Error(`Error ${res.status}: ${text}`);
	}
	if (res.status === 204) return null as T;
	const data = await res.json();
	console.log(`[api] ${method} ${API + path} -> data:`, data);
	return data;
}

function setToken(token: string) {
	try {
		localStorage.setItem('api_token', token);
	} catch {
		/* ignore */
	}
}
function clearToken() {
	try {
		localStorage.removeItem('api_token');
	} catch {
		/* ignore */
	}
}
function getToken(): string | null {
	return typeof localStorage !== 'undefined' ? localStorage.getItem('api_token') : null;
}

export const api = {
	listarTareas: () => req<Tarea[]>('/tareas'),
	obtenerTarea: (id: string) => req<Tarea>(`/tareas/${id}`),
	crearTarea: (data: {
		titulo: string;
		descripcion: string;
		prioridad: string;
		fecha_limite: string | null;
		etiqueta: string;
		repetible: boolean;
		horas: string[];
		dias_semana: string[];
		objetivo: string;
		icono?: string;
		color?: string;
	}) => req<Tarea>('/tareas', 'POST', data),
	actualizarTarea: (
		id: string,
		data: Partial<{
			titulo: string;
			descripcion: string;
			prioridad: string;
			fecha_limite: string | null;
			completada_manual: boolean;
			en_progreso_manual: boolean;
			etiqueta: string;
			repetible: boolean;
			horas: string[];
			dias_semana: string[];
			objetivo: string;
			icono: string;
			color: string;
		}>
	) => req<Tarea>(`/tareas/${id}`, 'PATCH', data),
	eliminarTarea: (id: string) => req(`/tareas/${id}`, 'DELETE'),

	agregarSubtarea: (
		tareaId: string,
		titulo: string,
		options?: { descripcion?: string; estado?: string; prompt?: string; repo?: string; archivo?: string }
	) => req<Tarea>(`/tareas/${tareaId}/subtareas`, 'POST', { titulo, ...options }),
	agregarSubtareaPorNumero: (
		numero: number,
		titulo: string,
		options?: { descripcion?: string; estado?: string; prompt?: string; repo?: string; archivo?: string }
	) => req<Tarea>(`/tareas/numero/${numero}/subtareas`, 'POST', { titulo, ...options }),
	actualizarSubtarea: (
		id: string,
		data: Partial<{
			titulo: string;
			completada: boolean;
			descripcion: string;
			estado: string;
			prompt: string;
			resultado: string;
			repo: string;
			archivo: string;
			commit_pendiente: boolean;
			commit_sha: string;
		}>
	) => req<Tarea>(`/subtareas/${id}`, 'PATCH', data),
	eliminarSubtarea: (id: string) => req<Tarea>(`/subtareas/${id}`, 'DELETE'),
	ejecutarSubtarea: (tareaId: string, subtareaId: string, modelo?: string) =>
		req<{
			ok: boolean;
			resultado?: string;
			plan?: string;
			revision?: { score: number; aprobado: boolean; resumen: string; feedback: string };
			error?: string;
		}>(`/tareas/${tareaId}/subtareas/${subtareaId}/ejecutar`, 'POST', { modelo }),
	iterarSubtarea: (tareaId: string, subtareaId: string, instrucciones?: string, modelo?: string) =>
		req<{
			ok: boolean;
			resultado?: string;
			plan?: string;
			revision?: { score: number; aprobado: boolean; resumen: string; feedback: string };
			error?: string;
		}>(`/tareas/${tareaId}/subtareas/${subtareaId}/iterar`, 'POST', { instrucciones, modelo }),
	ejecutarTodasSubtareas: (tareaId: string, modelo?: string) =>
		req<{ ok: boolean; mensaje?: string; ejecutadas?: any[]; fallidas?: any[] }>(
			`/tareas/${tareaId}/subtareas/ejecutar-todas`,
			'POST',
			{ modelo }
		),
	progresoSubtarea: (tareaId: string, subtareaId: string) =>
		req<{ paso: string; detalle: string; estado: string; timestamp?: string }>(
			`/tareas/${tareaId}/subtareas/${subtareaId}/progreso`,
			'GET'
		),
	commitearSubtarea: (tareaId: string, subtareaId: string) =>
		req<{ ok: boolean; sha?: string; error?: string; pendiente?: boolean }>(
			`/tareas/${tareaId}/subtareas/${subtareaId}/commit`,
			'POST'
		),
	sincronizarSubtareas: (tareaId: string) =>
		req<{ ok: boolean; mensaje?: string; commits?: any[]; pendientes?: any[] }>(
			`/tareas/${tareaId}/subtareas/sincronizar`,
			'POST'
		),
	obtenerCanvas: (tareaId: string) => req<{ canvas: TareaCanvas | null }>(`/tareas/${tareaId}/canvas`, 'GET'),
	guardarCanvas: (tareaId: string, canvas: TareaCanvas) =>
		req<Tarea>(`/tareas/${tareaId}/canvas`, 'POST', { canvas }),
	interpretarCanvas: (tareaId: string, modelo?: string) =>
		req<CanvasInterpretacion>(`/tareas/${tareaId}/canvas/interpretar`, 'POST', { modelo }),

	listarRecordatorios: () => req<Recordatorio[]>('/recordatorios'),
	crearRecordatorio: (data: { titulo: string; fecha_hora: string; tarea_id: string; subtarea_id: string | null }) =>
		req<Recordatorio>('/recordatorios', 'POST', data),
	actualizarRecordatorio: (id: string, data: Partial<{ titulo: string; fecha_hora: string; estado: string }>) =>
		req<Recordatorio>(`/recordatorios/${id}`, 'PATCH', data),
	eliminarRecordatorio: (id: string) => req(`/recordatorios/${id}`, 'DELETE'),

	agenteRecordatorio: () => req<AgenteResumen>('/agente/recordatorio'),
	agenteCheckin: () => req<AgenteCheckin>('/agente/checkin'),

	listarAgentes: () => req<{ agentes: Agente[]; skills: Skill[]; knowledge: Knowledge[] }>('/agentes'),
	crearAgente: (data: {
		nombre: string;
		descripcion: string;
		modelo: string;
		system_prompt: string;
		skills: string[];
		knowledge: string[];
	}) => req<{ agente: Agente }>('/agentes', 'POST', data),
	actualizarAgente: (
		id: string,
		data: Partial<{
			nombre: string;
			descripcion: string;
			modelo: string;
			system_prompt: string;
			skills: string[];
			knowledge: string[];
		}>
	) => req<{ agente: Agente }>(`/agentes/${id}`, 'PATCH', data),
	eliminarAgente: (id: string) => req(`/agentes/${id}`, 'DELETE'),
	ejecutarAgente: (id: string, prompt: string, tareaId?: string) =>
		req<{ respuesta: string }>(`/agentes/${id}/ejecutar`, 'POST', { prompt, tarea_id: tareaId }),
	ejecutarAgentesParalelo: (agenteIds: string[], prompt: string) =>
		req<{ resultados: { agente_id: string; agente_nombre: string; respuesta?: string; error?: string }[] }>(
			'/agentes/ejecutar-paralelo',
			'POST',
			{ agente_ids: agenteIds, prompt }
		),

	crearSkill: (data: { nombre: string; descripcion: string; instrucciones: string }) =>
		req<{ skill: Skill }>('/skills', 'POST', data),
	actualizarSkill: (id: string, data: { nombre: string; descripcion: string; instrucciones: string }) =>
		req<{ skill: Skill }>(`/skills/${id}`, 'PATCH', data),
	eliminarSkill: (id: string) => req(`/skills/${id}`, 'DELETE'),
	crearKnowledge: (data: { nombre: string; tipo: string; contenido: string }) =>
		req<{ knowledge: Knowledge }>('/knowledge', 'POST', data),
	actualizarKnowledge: (id: string, data: { nombre: string; tipo: string; contenido: string }) =>
		req<{ knowledge: Knowledge }>(`/knowledge/${id}`, 'PATCH', data),
	eliminarKnowledge: (id: string) => req(`/knowledge/${id}`, 'DELETE'),
	agentePlan: (objetivo: string, semanas = 4) => req<AgentePlanResultado>('/agente/plan', 'POST', { objetivo, semanas }),
	agenteBuscar: (tema: string) => req<AgenteBuscarResultado>('/agente/buscar', 'POST', { tema }),
	agenteIdea: (prompt: string) => req<AgenteIdeaResultado>('/agente/idea', 'POST', { prompt }),
	resumenTarea: (id: string) => req<{ resumen: string }>('/agente/resumen-tarea', 'POST', { tarea_id: id }),
	crearChatSesion: (tareaId: string, nombre: string) =>
		req<{ tarea: Tarea }>(`/tareas/${tareaId}/chat-sesiones`, 'POST', { tarea_id: tareaId, nombre }),
	enviarChatMensaje: (
		tareaId: string,
		sesionId: string,
		texto: string,
		options?: { modelo?: string; archivos?: { nombre: string; tipo: string; contenido: string }[] }
	) =>
		req<{ tarea: Tarea; respuesta: string }>(`/tareas/${tareaId}/chat-mensajes`, 'POST', {
			tarea_id: tareaId,
			sesion_id: sesionId,
			texto,
			modelo: options?.modelo,
			archivos: options?.archivos
		}),
	listarModelos: () => req<{ default: string; modelos: import('./types').ModeloAgente[] }>('/modelos'),
	actualizarProximaAltaValor: (tareaId: string, texto: string) =>
		req<{ tarea: Tarea }>(`/tareas/${tareaId}/proxima-alta-valor`, 'POST', {
			tarea_id: tareaId,
			sesion_id: 'manual',
			texto
		}),
	agentePreguntar: (pregunta: string, k = 5) =>
		req<AgentePreguntaResultado>('/agente/preguntar', 'POST', { pregunta, k }),

	getGitHubConfig: () => req<{ username: string; configured: boolean; oauth_available: boolean }>('/github/config'),
	getGitHubDiagnostico: () => req<{ tareas_url: string; oauth_configurado: boolean; callback_url: string; frontend_url: string; github_configurado: boolean; github_username: string; mensaje: string; problemas: string[] }>('/github/diagnostico'),
	testGitHubCallback: () => req<{ ok: boolean; callback_url: string; mensaje: string }>('/github/callback-test'),
	startGitHubOAuth: () => req<{ url: string; redirect_uri: string }>('/github/oauth'),
	setGitHubConfig: (pat: string, username = '') =>
		req<{ ok: boolean; username: string; scopes: string[] }>('/github/config', 'POST', { pat, username }),
	listGitHubRepos: () => req<{ repos: GitHubRepo[] }>('/github/repos'),
	createGitHubRepo: (name: string, opts?: { private?: boolean; description?: string }) =>
		req<{ ok: boolean; repo: GitHubRepo }>('/github/repos', 'POST', {
			name,
			private: opts?.private ?? true,
			description: opts?.description ?? ''
		}),
	linkGitHubRepo: (tareaId: string, repo: string) =>
		req<{ tarea: Tarea }>(`/tareas/${tareaId}/github`, 'POST', { repo }),
	unlinkGitHubRepo: (tareaId: string) => req<{ tarea: Tarea }>(`/tareas/${tareaId}/github`, 'DELETE'),

	getChangelog: () => req<{ content: string }>('/changelog'),
	getChangelogEntries: () => req<{ entries: ChangelogEntry[] }>('/changelog/entries'),
	addChangelogEntry: (version: string, seccion: string, cambios: string[], casos_qa: string[], fecha?: string, impacto?: string) =>
		req<{ ok: boolean; content: string }>('/changelog', 'POST', { version, seccion, cambios, casos_qa, fecha, impacto }),
	generateChangelog: (cambios: string, version = 'Unreleased', seccion = 'General', impacto = 'medio') =>
		req<{ ok: boolean; content: string; raw?: string }>('/changelog/generate', 'POST', { cambios, version, seccion, impacto }),
	ensureChangelogSkill: () => req<{ skill: any }>('/changelog/skill', 'POST'),

	agenteDesarrollar: (tareaId: string, prompt = '') =>
		req<{
			ok: boolean;
			repo: string;
			branch: string;
			pr: { url: string; number: number };
			archivos: string[];
			resumen: string;
			pros: string[];
			contras: string[];
			error?: string;
		}>(`/tareas/${tareaId}/agente-desarrollar`, 'POST', { prompt }),
	getGitHubStatus: (tareaId: string) =>
		req<{ tarea: Tarea; pr_status: { url: string; state: string; merged: boolean } | null }>(`/tareas/${tareaId}/github-status`),
	mergeGitHubPR: (tareaId: string) => req<{ merged: boolean; sha?: string }>(`/tareas/${tareaId}/github-merge`, 'POST'),

	crearMemoria: (texto: string, fuente = 'manual', metadata?: Record<string, unknown>) =>
		req<{ ok: boolean; ids: string[]; mensaje: string }>('/memorias', 'POST', { texto, fuente, metadata }),
	buscarMemoria: (consulta: string, k = 5, fuente?: string) =>
		req<{ consulta: string; resultados: MemoriaResultado[] }>('/memorias/buscar', 'POST', { consulta, k, fuente }),
	syncTareasMemoria: () => req<{ ok: boolean; tareas_indexadas: number }>('/memorias/sync-tareas', 'POST'),
	statsMemoria: () => req<{ total_registros: number; ruta: string }>('/memorias/stats'),

	vozProcesar: (texto: string) => req<VozResultado>('/voz/procesar', 'POST', { texto }),
	vozConfirmar: (draft: TareaDraft) => req<VozResultado>('/voz/confirmar', 'POST', { draft }),
	vozActualizar: (tareaId: string, cambios: Partial<Tarea>) =>
		req<VozResultado>('/voz/actualizar', 'POST', { tarea_id: tareaId, cambios }),
	vozResumen: () => req<{ mensaje: string }>('/voz/resumen'),
	vozConfig: () =>
		req<{ groq: boolean; local_whisper: boolean; speech_api: boolean; tts_premium: boolean }>('/voz/config'),
	vozTranscribir: async (audioBlob: Blob) => {
		const headers: Record<string, string> = {};
		const token = getToken();
		if (token) headers['X-API-Token'] = token;
		const res = await fetch(API + '/voz/transcribir', {
			method: 'POST',
			headers,
			body: audioBlob
		});
		if (!res.ok) throw new Error(`Error ${res.status}`);
		return res.json() as Promise<{ texto: string }>;
	},

	chatGlobal: (
		texto: string,
		options?: { modelo?: string; archivos?: { nombre: string; tipo: string; contenido: string }[] }
	) => req<ChatGlobalResultado>('/chat-global', 'POST', { texto, modelo: options?.modelo, archivos: options?.archivos }),
	chatGlobalHistorial: () => req<{ historial: ChatGlobalMessage[] }>('/chat-global'),
	chatGlobalLimpiar: () => req('/chat-global', 'DELETE'),

	authStatus: () => req<{ required: boolean }>('/auth/status'),
	authCheck: () => req<{ ok: boolean }>('/auth/check'),
	setToken,
	clearToken,
	getToken
};
