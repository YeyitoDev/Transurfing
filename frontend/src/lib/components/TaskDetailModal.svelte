<script lang="ts">
	import { X, Bell, Pencil, Trash2, Calendar, Clock, Repeat, CheckSquare, Plus, Sparkles, FileText, Loader2, Heart, Rocket, TrendingUp, Target, Users, Bot, GitCommit, RefreshCw, UploadCloud, AlertCircle, Workflow } from 'lucide-svelte';
	import { marked } from 'marked';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import { detailModalStore, modalStore } from './modalStore';
	import ProgressBar from './ProgressBar.svelte';
	import ChatPanel from './ChatPanel.svelte';
	import GitHubTaskPanel from './GitHubTaskPanel.svelte';
	import VisualCanvas from './VisualCanvas.svelte';
	import type { Tarea, Subtarea } from '../types';

	const ETIQUETA_LABEL: Record<string, string> = {
		emprendimiento: 'Emprendimiento',
		tarea: 'Tarea',
		habito: 'Hábito',
		investigacion: 'Investigación',
		idea: 'Idea'
	};

	const PRIORIDAD_LABEL: Record<string, string> = { alta: 'Alta', media: 'Media', baja: 'Baja' };

	let tarea = $derived($detailModalStore);
	let nuevaSub = $state('');
	let nuevaSubDesc = $state('');
	let nuevaSubPrompt = $state('');
	let nuevaSubArchivo = $state('');
	let nuevaSubEstado = $state<'pendiente' | 'en_progreso' | 'bloqueada' | 'completada'>('pendiente');
	let resumen = $state('');
	let resumenLoading = $state(false);
	let loading = $state(false);
	let docOpen = $state(false);
	let subExpandida = $state<string | null>(null);
	let ejecutandoSub = $state<string | null>(null);
	let commiteandoSub = $state<string | null>(null);
	let ejecutandoTodas = $state(false);
	let sincronizando = $state(false);
	let mensajeError = $state<string | null>(null);
	let progresoSub = $state<Record<string, { paso: string; detalle: string; estado: string; timestamp?: string }>>({});
	let iterandoSub = $state<string | null>(null);
	let instruccionesIterar = $state<Record<string, string>>({});
	let verHistorial = $state<string | null>(null);
	let visualCanvasOpen = $state(false);

	const PIPELINE_PASOS: { id: string; label: string }[] = [
		{ id: 'planificando', label: 'Planifica' },
		{ id: 'ejecutando', label: 'Ejecuta' },
		{ id: 'revisando', label: 'Revisa' },
		{ id: 'guardando', label: 'Guarda' },
		{ id: 'completado', label: 'Listo' }
	];

	function pasoIndice(paso?: string): number {
		if (!paso) return -1;
		const orden = ['validando', 'planificando', 'ejecutando', 'revisando', 'guardando', 'completado'];
		return orden.indexOf(paso);
	}

	function scoreColor(score?: number): string {
		if (score == null) return 'text-slate-400';
		if (score >= 80) return 'text-green-400';
		if (score >= 60) return 'text-amber-400';
		return 'text-red-400';
	}

	function mostrarError(msg: string) {
		mensajeError = msg;
		setTimeout(() => (mensajeError = null), 6000);
	}

	async function consultarProgreso(sub: Subtarea) {
		if (!tarea) return;
		try {
			const p = await api.progresoSubtarea(tarea.id, sub.id);
			progresoSub = { ...progresoSub, [sub.id]: p };
		} catch (e) {
			console.error(e);
		}
	}

	async function toggleSub(sub: Subtarea) {
		if (!tarea) return;
		const optimisticSubs = tarea.subtareas.map((s) => (s.id === sub.id ? { ...s, completada: !s.completada } : s));
		const completadas = optimisticSubs.filter((s) => s.completada).length;
		const total = optimisticSubs.length;
		const progreso = total > 0 ? Math.round((completadas / total) * 100 * 10) / 10 : tarea.completada_manual ? 100 : 0;
		const estado = total > 0 && completadas === total ? 'completada' : 'pendiente';
		onTaskChange({ ...tarea, subtareas: optimisticSubs, subtareas_completadas: completadas, subtareas_total: total, progreso, estado } as Tarea);
		try {
			const t = await api.actualizarSubtarea(sub.id, { completada: !sub.completada });
			onTaskChange(t);
		} catch {
			onTaskChange(tarea);
		}
	}

	async function addSub() {
		if (!tarea || !nuevaSub.trim()) return;
		loading = true;
		try {
			const t = await api.agregarSubtarea(tarea.id, nuevaSub, {
				descripcion: nuevaSubDesc,
				estado: nuevaSubEstado,
				prompt: nuevaSubPrompt,
				archivo: nuevaSubArchivo,
				repo: tarea.github_repo
			});
			onTaskChange(t);
			nuevaSub = '';
			nuevaSubDesc = '';
			nuevaSubPrompt = '';
			nuevaSubArchivo = '';
			nuevaSubEstado = 'pendiente';
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	async function guardarSub(sub: Subtarea) {
		try {
			const t = await api.actualizarSubtarea(sub.id, {
				titulo: sub.titulo,
				descripcion: sub.descripcion,
				estado: sub.estado,
				prompt: sub.prompt,
				repo: sub.repo,
				archivo: sub.archivo
			});
			onTaskChange(t);
		} catch (e) {
			console.error(e);
		}
	}

	async function ejecutarSub(sub: Subtarea) {
		if (!tarea) return;
		if (!sub.prompt) {
			mostrarError('La subtarea no tiene un prompt para el agente. Edítala y añade instrucciones.');
			return;
		}
		ejecutandoSub = sub.id;
		mensajeError = null;
		progresoSub = { ...progresoSub, [sub.id]: { paso: 'iniciando', detalle: 'Preparando agente...', estado: 'en_progreso' } };
		const interval = setInterval(() => consultarProgreso(sub), 1200);
		try {
			const res = await api.ejecutarSubtarea(tarea.id, sub.id);
			clearInterval(interval);
			if (res.ok) {
				progresoSub = { ...progresoSub, [sub.id]: { paso: 'completado', detalle: 'Subtarea resuelta', estado: 'completado' } };
				const t = await api.obtenerTarea(tarea.id);
				onTaskChange(t);
			} else {
				mostrarError(res.error || 'No se pudo ejecutar la subtarea');
				progresoSub = { ...progresoSub, [sub.id]: { paso: 'error', detalle: res.error || 'Error desconocido', estado: 'error' } };
			}
		} catch (e: any) {
			clearInterval(interval);
			console.error(e);
			mostrarError(e?.message || 'Error de conexión al ejecutar subtarea');
			progresoSub = { ...progresoSub, [sub.id]: { paso: 'error', detalle: e?.message || 'Error de conexión', estado: 'error' } };
		} finally {
			ejecutandoSub = null;
		}
	}

	async function ejecutarTodasSubtareas() {
		if (!tarea) return;
		const subs = tarea.subtareas.filter((s) => s.prompt && s.estado !== 'completada');
		if (subs.length === 0) {
			mostrarError('No hay subtareas con prompt pendientes de ejecución.');
			return;
		}
		ejecutandoTodas = true;
		mensajeError = null;
		const interval = setInterval(() => subs.forEach(consultarProgreso), 1500);
		try {
			const res = await api.ejecutarTodasSubtareas(tarea.id);
			clearInterval(interval);
			if (res.ok) {
				const t = await api.obtenerTarea(tarea.id);
				onTaskChange(t);
			} else {
				mostrarError(res.mensaje || 'No se pudieron ejecutar todas las subtareas');
			}
			if (res.fallidas && res.fallidas.length > 0) {
				const errores = res.fallidas.map((f) => f.error || 'Error desconocido').join('; ');
				mostrarError(`Algunas subtareas fallaron: ${errores}`);
			}
		} catch (e: any) {
			clearInterval(interval);
			console.error(e);
			mostrarError(e?.message || 'Error de conexión al ejecutar subtareas');
		} finally {
			ejecutandoTodas = false;
		}
	}

	async function commitearSub(sub: Subtarea) {
		if (!tarea) return;
		commiteandoSub = sub.id;
		mensajeError = null;
		try {
			const res = await api.commitearSubtarea(tarea.id, sub.id);
			if (res.ok) {
				const t = await api.obtenerTarea(tarea.id);
				onTaskChange(t);
			} else {
				mostrarError(res.error || 'No se pudo subir el resultado');
			}
		} catch (e: any) {
			console.error(e);
			mostrarError(e?.message || 'Error de conexión al subir resultado');
		} finally {
			commiteandoSub = null;
		}
	}

	async function sincronizarSubs() {
		if (!tarea) return;
		sincronizando = true;
		mensajeError = null;
		try {
			const res = await api.sincronizarSubtareas(tarea.id);
			if (res.ok) {
				const t = await api.obtenerTarea(tarea.id);
				onTaskChange(t);
			} else {
				mostrarError(res.mensaje || 'No se pudieron sincronizar commits');
			}
			if (res.pendientes && res.pendientes.length > 0) {
				mostrarError(`Aún hay ${res.pendientes.length} commit(s) pendiente(s).`);
			}
		} catch (e: any) {
			console.error(e);
			mostrarError(e?.message || 'Error de conexión al sincronizar');
		} finally {
			sincronizando = false;
		}
	}

	async function iterarSub(sub: Subtarea) {
		if (!tarea) return;
		iterandoSub = sub.id;
		mensajeError = null;
		progresoSub = { ...progresoSub, [sub.id]: { paso: 'planificando', detalle: 'Mejorando sobre el resultado previo...', estado: 'en_progreso' } };
		const interval = setInterval(() => consultarProgreso(sub), 1200);
		try {
			const extra = (instruccionesIterar[sub.id] || '').trim();
			const res = await api.iterarSubtarea(tarea.id, sub.id, extra || undefined);
			clearInterval(interval);
			if (res.ok) {
				progresoSub = { ...progresoSub, [sub.id]: { paso: 'completado', detalle: 'Iteración completada', estado: 'completado' } };
				instruccionesIterar = { ...instruccionesIterar, [sub.id]: '' };
				const t = await api.obtenerTarea(tarea.id);
				onTaskChange(t);
			} else {
				mostrarError(res.error || 'No se pudo iterar la subtarea');
				progresoSub = { ...progresoSub, [sub.id]: { paso: 'error', detalle: res.error || 'Error desconocido', estado: 'error' } };
			}
		} catch (e: any) {
			clearInterval(interval);
			console.error(e);
			mostrarError(e?.message || 'Error de conexión al iterar subtarea');
			progresoSub = { ...progresoSub, [sub.id]: { paso: 'error', detalle: e?.message || 'Error de conexión', estado: 'error' } };
		} finally {
			iterandoSub = null;
		}
	}

	const ESTADO_LABEL: Record<string, string> = {
		pendiente: 'Pendiente',
		en_progreso: 'En progreso',
		bloqueada: 'Bloqueada',
		completada: 'Completada'
	};

	const ESTADO_COLOR: Record<string, string> = {
		pendiente: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
		en_progreso: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
		bloqueada: 'bg-red-500/10 text-red-400 border-red-500/20',
		completada: 'bg-green-500/10 text-green-400 border-green-500/20'
	};

	async function delSub(sub: Subtarea) {
		try {
			const t = await api.eliminarSubtarea(sub.id);
			onTaskChange(t);
		} catch (e) {
			console.error(e);
		}
	}

	async function eliminar() {
		if (!tarea || !confirm('¿Eliminar esta tarea?')) return;
		onTaskChange(null, tarea.id);
		modalStore.closeDetail();
		try {
			await api.eliminarTarea(tarea.id);
		} catch {
			// revert handled by store
		}
	}

	async function generarResumen() {
		if (!tarea) return;
		resumenLoading = true;
		resumen = '';
		try {
			const res = await api.resumenTarea(tarea.id);
			resumen = res.resumen;
		} catch (e) {
			console.error(e);
			resumen = 'No pude generar el resumen.';
		} finally {
			resumenLoading = false;
		}
	}

	let done = $derived(tarea?.estado === 'completada');
	let tieneInforme = $derived(!!tarea?.documento);
	let esHabito = $derived(tarea?.etiqueta === 'habito' || tarea?.repetible);
	let esEmprendimiento = $derived(tarea?.etiqueta === 'emprendimiento');
	let esInvestigacion = $derived(tarea?.etiqueta === 'investigacion');
	let esIdea = $derived(tarea?.etiqueta === 'idea');

	const ETAPAS_DESIGN_THINKING = [
		{ key: 'empatizar', label: 'Empatizar', icon: Users, desc: 'Entender al cliente' },
		{ key: 'definir', label: 'Definir', icon: Target, desc: 'Problem statement' },
		{ key: 'idear', label: 'Idear', icon: Sparkles, desc: 'Propuesta de valor' },
		{ key: 'prototipar', label: 'Prototipar', icon: Rocket, desc: 'MVP o prueba' },
		{ key: 'testear', label: 'Testear', icon: TrendingUp, desc: 'Validar con usuarios' },
	];

	function calcularRacha(log: string[]): number {
		if (log.length === 0) return 0;
		const hoy = new Date().toISOString().slice(0, 10);
		const ordenados = [...log].sort();
		if (ordenados[ordenados.length - 1] !== hoy) return 0;
		let racha = 1;
		for (let i = ordenados.length - 1; i > 0; i--) {
			const dia = new Date(ordenados[i] + 'T00:00:00');
			const anterior = new Date(ordenados[i - 1] + 'T00:00:00');
			anterior.setDate(anterior.getDate() + 1);
			if (dia.toISOString().slice(0, 10) === anterior.toISOString().slice(0, 10)) racha++;
			else break;
		}
		return racha;
	}
	let rachaHabito = $derived(tarea && esHabito ? calcularRacha(tarea.habito_log) : 0);
	let totalHabito = $derived(tarea?.habito_log.length || 0);
	let ultimoHabito = $derived(tarea?.habito_log[tarea.habito_log.length - 1] || null);

	function etapaActiva(t: Tarea): number {
		const nombres = t.subtareas.map((s) => s.titulo.toLowerCase());
		for (let i = ETAPAS_DESIGN_THINKING.length - 1; i >= 0; i--) {
			if (nombres.some((n) => n.includes(ETAPAS_DESIGN_THINKING[i].key))) return i;
		}
		return 0;
	}
	let etapaDT = $derived(tarea && esEmprendimiento ? etapaActiva(tarea) : -1);
	let progresoDT = $derived(tarea && esEmprendimiento ? Math.round(((etapaDT + 1) / ETAPAS_DESIGN_THINKING.length) * 100) : 0);
</script>

{#if tarea}
	<div class="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 animate-fade-in p-4" onclick={modalStore.closeDetail}>
		<div class="bg-card border border-border rounded-2xl w-full max-w-2xl md:max-w-4xl lg:max-w-6xl xl:max-w-[1400px] max-h-[92vh] flex flex-col animate-slide-up" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between px-5 py-3.5 border-b border-border">
				<div class="text-sm font-semibold">Detalle de tarea</div>
				<div class="flex items-center gap-2">
					<button
						onclick={() => (visualCanvasOpen = true)}
						class="flex items-center gap-1.5 text-[11px] font-medium bg-card2 hover:bg-accent/10 text-text hover:text-accent border border-border rounded-lg px-3 py-1.5 transition-colors"
					>
						<Workflow size={14} /> Lienzo visual
					</button>
					<button onclick={modalStore.closeDetail} class="text-muted hover:text-text">
						<X size={20} />
					</button>
				</div>
			</div>

			<div class="overflow-y-auto px-5 py-4">
				<div class="flex items-start gap-3 mb-4">
					<div class="w-6 h-6 min-w-6 rounded-lg border-2 flex items-center justify-center text-xs transition-all {done ? 'bg-green border-green text-white' : 'border-border'}">
						{#if done}✓{/if}
					</div>
					<div class="flex-1">
						<div class="flex items-center gap-2 mb-1">
							<span class="text-xs font-bold px-2 py-1 rounded bg-card2 text-muted border border-border">Tarea #{tarea.numero}</span>
							<h2 class="text-lg font-semibold leading-snug {done ? 'line-through text-muted' : 'text-text'}">{tarea.titulo}</h2>
						</div>
						{#if tarea.descripcion}
							<p class="text-sm text-muted mt-1.5">{tarea.descripcion}</p>
						{/if}
					</div>
				</div>

				<div class="flex flex-wrap gap-2 mb-4">
					<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border">{ETIQUETA_LABEL[tarea.etiqueta] || tarea.etiqueta}</span>
					<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border">Prioridad {PRIORIDAD_LABEL[tarea.prioridad]}</span>
					{#if tarea.repetible}
						<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-green-500/15 text-green-400 border border-green-500/20">Tarea repetible</span>
					{/if}
					{#if tarea.fecha_limite}
						<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-text border border-border flex items-center gap-1">
							<Calendar size={10} /> {tarea.fecha_limite}
						</span>
					{/if}
					{#if tarea.horas && tarea.horas.length > 0}
						<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-pink-500/15 text-pink-300 border border-pink-500/20 flex items-center gap-1">
							<Clock size={10} /> {tarea.horas.join(', ')}
						</span>
					{/if}
					{#if tarea.dias_semana && tarea.dias_semana.length > 0}
						<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20">
							{tarea.dias_semana.map((d) => d.toUpperCase()).join(' ')}
						</span>
					{/if}
					{#if tarea.objetivo}
						<span class="text-[10px] font-medium px-2.5 py-1 rounded-full bg-card2 text-accent border border-border">Objetivo: {tarea.objetivo}</span>
					{/if}
				</div>

				<div class="bg-card2 border border-border rounded-xl p-3 mb-4">
					<div class="flex items-center justify-between mb-1.5">
						<span class="text-xs font-medium text-text">Progreso</span>
						<span class="text-xs font-medium text-muted">{Math.round(tarea.progreso)}%</span>
					</div>
					<ProgressBar pct={tarea.progreso} />
					<div class="text-[10px] text-muted mt-2">{tarea.subtareas_completadas} de {tarea.subtareas_total} subtareas completadas</div>
				</div>

				{#if esHabito}
					<div class="bg-pink-500/10 border border-pink-500/20 rounded-xl p-3 mb-4">
						<div class="text-xs font-semibold text-text mb-2 flex items-center gap-1.5">
							<Heart size={14} class="text-pink-400" /> Historia del hábito
						</div>
						<div class="grid grid-cols-3 gap-3">
							<div class="bg-card rounded-lg p-2 text-center">
								<div class="text-lg font-bold text-pink-400">{rachaHabito}</div>
								<div class="text-[10px] text-muted">Racha actual</div>
							</div>
							<div class="bg-card rounded-lg p-2 text-center">
								<div class="text-lg font-bold text-text">{totalHabito}</div>
								<div class="text-[10px] text-muted">Total hecho</div>
							</div>
							<div class="bg-card rounded-lg p-2 text-center">
								<div class="text-lg font-bold text-text">{ultimoHabito || '—'}</div>
								<div class="text-[10px] text-muted">Último</div>
							</div>
						</div>
					</div>
				{/if}

				{#if esEmprendimiento}
					<div class="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3 mb-4">
						<div class="text-xs font-semibold text-text mb-2 flex items-center gap-1.5">
							<Rocket size={14} class="text-indigo-400" /> Historia del proyecto — Design Thinking
						</div>
						<div class="flex items-center gap-2 mb-3">
							<span class="text-xs font-medium text-text">Progreso en etapas</span>
							<span class="text-xs font-medium text-indigo-400">{progresoDT}%</span>
						</div>
						<div class="relative mb-3">
							<div class="h-2 bg-card rounded-full overflow-hidden">
								<div class="h-full bg-indigo-500 rounded-full transition-all" style="width: {progresoDT}%"></div>
							</div>
						</div>
						<div class="grid grid-cols-5 gap-2">
							{#each ETAPAS_DESIGN_THINKING as etapa, idx}
								{@const activa = idx <= etapaDT}
								{@const completada = idx < etapaDT}
								<div class="bg-card rounded-lg p-2 text-center border {activa ? 'border-indigo-500/50' : 'border-border'} {completada ? 'opacity-70' : ''}">
									<etapa.icon size={14} class="mx-auto mb-1 {activa ? 'text-indigo-400' : 'text-muted'}" />
									<div class="text-[10px] font-medium {activa ? 'text-text' : 'text-muted'}">{etapa.label}</div>
									<div class="text-[9px] text-muted mt-0.5 hidden lg:block">{etapa.desc}</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				{#if tarea.proxima_alta_valor}
					<div class="flex items-start gap-2 text-sm text-accent mb-4 p-3 rounded-xl bg-accent/5 border border-accent/10">
						<Sparkles size={16} class="mt-0.5 shrink-0" />
						<div>{tarea.proxima_alta_valor}</div>
					</div>
				{/if}

				<div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 mb-4 min-h-[420px]">
					<div class="flex flex-col gap-4">
						<div class="bg-card2 border border-border rounded-xl p-3">
							<div class="text-xs font-semibold text-text mb-2 flex items-center justify-between gap-1.5">
								<div class="flex items-center gap-1.5">
									<CheckSquare size={14} /> Subtareas
								</div>
								<div class="flex items-center gap-1">
									<button onclick={ejecutarTodasSubtareas} disabled={ejecutandoTodas} class="p-1.5 rounded-md text-muted hover:text-indigo-400 hover:bg-indigo-500/10 disabled:opacity-50" title="Ejecutar todas con agentes">
										{#if ejecutandoTodas}<Loader2 size={12} class="animate-spin" />{:else}<Bot size={12} />{/if}
									</button>
									<button onclick={sincronizarSubs} disabled={sincronizando} class="p-1.5 rounded-md text-muted hover:text-indigo-400 hover:bg-indigo-500/10 disabled:opacity-50" title="Sincronizar commits pendientes">
										{#if sincronizando}<Loader2 size={12} class="animate-spin" />{:else}<RefreshCw size={12} />{/if}
									</button>
								</div>
							</div>
							{#if mensajeError}
								<div class="mb-2 text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-start gap-2">
									<AlertCircle size={14} class="shrink-0 mt-0.5" />
									<span>{mensajeError}</span>
								</div>
							{/if}
							{#if tarea.subtareas.length === 0}
								<p class="text-[11px] text-muted">No hay subtareas.</p>
							{:else}
								<div class="space-y-1.5 max-h-[260px] overflow-y-auto pr-1">
									{#each tarea.subtareas as sub}
										<div class="rounded-lg bg-bg border border-border overflow-hidden {sub.completada ? 'opacity-60' : ''}">
											<div class="flex items-center gap-2 p-2">
												<button onclick={() => toggleSub(sub)} class="w-5 h-5 min-w-5 rounded-md border-2 flex items-center justify-center text-[10px] {sub.completada ? 'bg-green border-green text-white' : 'border-border hover:border-accent'}">
													{#if sub.completada}✓{/if}
												</button>
												<input
													class="flex-1 bg-transparent border-none text-sm {sub.completada ? 'line-through text-muted' : 'text-text'} focus:outline-none px-1"
													bind:value={sub.titulo}
													onchange={() => guardarSub(sub)}
												/>
												<div class="flex items-center gap-1">
													{#if sub.resultado}
														<span class="text-[9px] px-1.5 py-0.5 rounded border bg-indigo-500/10 text-indigo-400 border-indigo-500/20" title="Tiene resultado de agente">A</span>
													{/if}
													{#if sub.commit_pendiente}
														<span class="text-[9px] px-1.5 py-0.5 rounded border bg-amber-500/10 text-amber-400 border-amber-500/20" title="Commit pendiente">P</span>
													{/if}
													{#if sub.commit_sha}
														<span class="text-[9px] px-1.5 py-0.5 rounded border bg-green-500/10 text-green-400 border-green-500/20" title="Commiteado">C</span>
													{/if}
													<span class="text-[9px] px-1.5 py-0.5 rounded border {ESTADO_COLOR[sub.estado] || ESTADO_COLOR.pendiente}">
														{ESTADO_LABEL[sub.estado] || sub.estado}
													</span>
												</div>
												<button onclick={() => subExpandida = subExpandida === sub.id ? null : sub.id} class="p-1 text-muted hover:text-accent">
													<Pencil size={12} />
												</button>
												{#if sub.prompt}
													<button onclick={() => ejecutarSub(sub)} disabled={ejecutandoSub === sub.id} class="p-1 text-muted hover:text-indigo-400" title="Ejecutar con agente">
														{#if ejecutandoSub === sub.id}<Loader2 size={12} class="animate-spin" />{:else}<Bot size={12} />{/if}
													</button>
												{/if}
												{#if sub.resultado}
													<button onclick={() => commitearSub(sub)} disabled={commiteandoSub === sub.id} class="p-1 text-muted hover:text-indigo-400" title="Subir a GitHub">
														{#if commiteandoSub === sub.id}<Loader2 size={12} class="animate-spin" />{:else}<GitCommit size={12} />{/if}
													</button>
												{/if}
												<button onclick={() => modalStore.openReminder({ tarea, subtarea: sub })} class="p-1 text-muted hover:text-accent">
													<Bell size={12} />
												</button>
												<button onclick={() => delSub(sub)} class="p-1 text-muted hover:text-red">
													<Trash2 size={12} />
												</button>
											</div>
											{#if progresoSub[sub.id] && progresoSub[sub.id].estado !== 'esperando'}
								<div class="px-2 pb-1.5">
									<div class="bg-card2 border border-border rounded-lg px-2 py-2 space-y-1.5">
										<div class="flex items-center justify-between">
											<div class="flex items-center gap-1.5">
												{#each PIPELINE_PASOS as paso, i}
													{@const idx = pasoIndice(progresoSub[sub.id].paso)}
													<span class="text-[9px] px-1.5 py-0.5 rounded border {idx >= i ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' : 'bg-slate-500/10 text-slate-400 border-slate-500/20'}">
														{paso.label}
													</span>
												{/each}
											</div>
											{#if progresoSub[sub.id].estado === 'en_progreso'}<Loader2 size={12} class="animate-spin text-indigo-400" />{/if}
										</div>
										<div class="flex items-center gap-2 text-[10px] {progresoSub[sub.id].estado === 'error' ? 'text-red-400' : progresoSub[sub.id].estado === 'completado' ? 'text-green-400' : 'text-indigo-400'}">
											{#if progresoSub[sub.id].estado === 'error'}<AlertCircle size={12} class="shrink-0" />{/if}
											{#if progresoSub[sub.id].estado === 'completado'}<CheckSquare size={12} class="shrink-0" />{/if}
											<span class="font-medium">{progresoSub[sub.id].paso}</span>
											<span class="text-muted truncate">{progresoSub[sub.id].detalle}</span>
										</div>
									</div>
								</div>
							{/if}
											{#if subExpandida === sub.id}
												<div class="px-2 pb-2 space-y-2">
													<div>
														<label for="sub-desc-{sub.id}" class="text-[10px] text-muted block mb-1">Descripción</label>
														<textarea
																id="sub-desc-{sub.id}"
																rows={2}
																class="w-full bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text placeholder-muted resize-none"
																placeholder="¿Qué se quiere lograr con esta subtarea?"
																bind:value={sub.descripcion}
																onchange={() => guardarSub(sub)}
															></textarea>
													</div>
															<div>
																<label for="sub-prompt-{sub.id}" class="text-[10px] text-muted block mb-1">Prompt para el agente</label>
																<textarea
																	id="sub-prompt-{sub.id}"
																	rows={4}
																	class="w-full bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text placeholder-muted resize-none font-mono"
																	placeholder="Instrucciones detalladas que recibirá el agente para ejecutar esta subtarea..."
																	bind:value={sub.prompt}
																	onchange={() => guardarSub(sub)}
																></textarea>
															</div>
															<div class="grid grid-cols-2 gap-2">
																<div>
																	<label for="sub-repo-{sub.id}" class="text-[10px] text-muted block mb-1">Repo</label>
																	<input id="sub-repo-{sub.id}" class="w-full bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text" placeholder="usuario/repo" bind:value={sub.repo} onchange={() => guardarSub(sub)} />
																</div>
																<div>
																	<label for="sub-archivo-{sub.id}" class="text-[10px] text-muted block mb-1">Archivo destino</label>
																	<input id="sub-archivo-{sub.id}" class="w-full bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text" placeholder="src/resultado.md" bind:value={sub.archivo} onchange={() => guardarSub(sub)} />
																</div>
															</div>
															{#if sub.resultado}
								<div class="bg-bg border border-border rounded-lg p-2 space-y-2">
									<div class="flex items-center justify-between">
										<div class="text-[10px] text-muted">Resultado del agente</div>
										<div class="flex items-center gap-1.5">
											{#if sub.score != null}<span class="text-[10px] font-semibold {scoreColor(sub.score)}">Score {Math.round(sub.score)}/100</span>{/if}
											{#if sub.iteraciones && (sub.iteraciones || []).length > 1}<span class="text-[9px] text-slate-400">v{(sub.iteraciones || []).length}</span>{/if}
										</div>
									</div>
									{#if sub.resumen}
										<div class="text-[11px] text-indigo-200 bg-indigo-500/10 border border-indigo-500/20 rounded px-2 py-1">{sub.resumen}</div>
									{/if}
									<pre class="text-[10px] text-text whitespace-pre-wrap font-mono">{sub.resultado}</pre>
									{#if sub.revision}
										<div class="border-t border-border pt-1.5">
											<div class="text-[10px] text-muted mb-0.5">Feedback del revisor</div>
											<div class="text-[10px] text-amber-300">{sub.revision}</div>
										</div>
									{/if}
									{#if sub.plan}
										<details class="text-[10px]">
											<summary class="cursor-pointer text-muted hover:text-text">Ver plan</summary>
											<div class="text-[10px] text-slate-300 mt-1 whitespace-pre-wrap">{sub.plan}</div>
										</details>
									{/if}
									<div class="border-t border-border pt-2 space-y-1.5">
										<div class="text-[10px] text-muted">Mejorar este resultado</div>
										<textarea rows="2" class="w-full bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text placeholder-muted resize-none" placeholder="Indica qué quieres mejorar (opcional)..." bind:value={instruccionesIterar[sub.id]}></textarea>
										<div class="flex gap-2">
											<button onclick={() => iterarSub(sub)} disabled={iterandoSub === sub.id} class="flex-1 text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-lg px-2 py-1 hover:bg-indigo-500/30 disabled:opacity-50 flex items-center justify-center gap-1">
												{#if iterandoSub === sub.id}<Loader2 size={10} class="animate-spin" />{/if} Iterar / Mejorar
											</button>
											{#if sub.iteraciones && (sub.iteraciones || []).length > 0}
												<button onclick={() => verHistorial = verHistorial === sub.id ? null : sub.id} class="text-[10px] bg-slate-500/10 text-slate-300 border border-slate-500/20 rounded-lg px-2 py-1 hover:bg-slate-500/20">
													{verHistorial === sub.id ? 'Ocultar' : 'Historial'} v{(sub.iteraciones || []).length}
												</button>
											{/if}
										</div>
									</div>
									{#if verHistorial === sub.id}
										<div class="space-y-1.5 border-t border-border pt-2">
											<div class="text-[10px] text-muted">Historial de iteraciones</div>
											{#each (sub.iteraciones || []).slice().reverse() as it, idx}
												<div class="bg-slate-500/5 border border-slate-500/10 rounded-lg px-2 py-1.5">
													<div class="flex items-center justify-between text-[10px]">
														<span class="text-slate-400">v{(sub.iteraciones || []).length - idx} · {it.timestamp}</span>
														{#if it.score != null}<span class="font-semibold {scoreColor(it.score)}">{Math.round(it.score)}/100</span>{/if}
													</div>
													{#if it.resumen}<div class="text-[11px] text-indigo-200 mt-0.5">{it.resumen}</div>{/if}
													{#if it.feedback}<div class="text-[10px] text-amber-300 mt-0.5">{it.feedback}</div>{/if}
													<details class="text-[10px] mt-1">
														<summary class="cursor-pointer text-muted hover:text-text">Ver resultado</summary>
														<pre class="text-[10px] text-text whitespace-pre-wrap font-mono mt-1">{it.resultado}</pre>
													</details>
												</div>
											{/each}
										</div>
									{/if}
								</div>
							{/if}
													<div class="flex items-center gap-2">
														<label for="sub-estado-{sub.id}" class="text-[10px] text-muted">Estado</label>
														<select
																id="sub-estado-{sub.id}"
															class="bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
															bind:value={sub.estado}
															onchange={() => guardarSub(sub)}
														>
															<option value="pendiente">Pendiente</option>
															<option value="en_progreso">En progreso</option>
															<option value="bloqueada">Bloqueada</option>
															<option value="completada">Completada</option>
														</select>
														<button onclick={() => guardarSub(sub)} class="ml-auto text-[10px] bg-accent text-white rounded-lg px-2 py-1">Guardar</button>
													</div>
												</div>
											{/if}
										</div>
									{/each}
								</div>
							{/if}
							<div class="space-y-2 mt-3 pt-3 border-t border-border">
								<input class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted" placeholder="Título de la nueva subtarea..." bind:value={nuevaSub} onkeydown={(e) => e.key === 'Enter' && addSub()} />
								<textarea rows={2} class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted resize-none" placeholder="Descripción (opcional)" bind:value={nuevaSubDesc}></textarea>
																<textarea rows={3} class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted resize-none font-mono" placeholder="Prompt detallado para el agente (opcional)" bind:value={nuevaSubPrompt}></textarea>
																<input class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted" placeholder="Archivo destino en repo (opcional)" bind:value={nuevaSubArchivo} />
								<div class="flex gap-2">
									<select class="bg-bg border border-border rounded-lg px-2 py-2 text-xs text-text" bind:value={nuevaSubEstado}>
										<option value="pendiente">Pendiente</option>
										<option value="en_progreso">En progreso</option>
										<option value="bloqueada">Bloqueada</option>
										<option value="completada">Completada</option>
									</select>
									<button onclick={addSub} disabled={loading || !nuevaSub.trim()} class="flex-1 bg-accent text-white rounded-lg px-3 text-sm hover:opacity-90 transition-opacity disabled:opacity-50">
										{#if loading}<Loader2 size={14} class="animate-spin mx-auto" />{:else}<Plus size={16} class="mx-auto" />{/if}
									</button>
								</div>
							</div>
						</div>

						<div class="bg-accent/5 border border-accent/20 rounded-xl p-3">
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-semibold text-text flex items-center gap-1.5">
									<Sparkles size={14} class="text-accent" /> Resumen del agente
								</div>
								<button onclick={generarResumen} disabled={resumenLoading} class="text-[10px] bg-accent text-white rounded-lg px-2.5 py-1.5 flex items-center gap-1 disabled:opacity-50">
									{#if resumenLoading}<Loader2 size={10} class="animate-spin" />{:else}<Sparkles size={10} />{/if}
									{resumenLoading ? 'Generando...' : 'Resumen'}
								</button>
							</div>
							{#if resumen}
								<div class="prose prose-invert prose-sm max-w-none bg-bg border border-border rounded-lg p-3 overflow-y-auto max-h-[400px]">
									{@html marked.parse(resumen, { async: false })}
								</div>
							{:else}
								<p class="text-[11px] text-muted">Pulsa "Resumen" para que Jarvis te diga qué pasos seguir, qué riesgos hay y qué priorizar.</p>
							{/if}
						</div>
					</div>

					<div>
						<ChatPanel {tarea} />
					</div>

					<div>
						<GitHubTaskPanel {tarea} />
					</div>
				</div>

				{#if tieneInforme}
					<button onclick={() => (docOpen = true)} class="w-full mt-4 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-xl p-2.5 text-xs font-medium flex items-center justify-center gap-2 hover:bg-amber-500/15">
						<FileText size={14} /> Ver informe detallado de la idea
					</button>
				{/if}
			</div>

			<div class="flex items-center gap-2 px-5 py-3 border-t border-border">
				<button onclick={() => modalStore.openReminder({ tarea })} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-card2 text-text border border-border hover:border-accent transition-colors">
					<Bell size={14} /> Recordatorio
				</button>
				<button onclick={() => { modalStore.openEdit(tarea); modalStore.closeDetail(); }} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-card2 text-text border border-border hover:border-blue-400 transition-colors">
					<Pencil size={14} /> Editar
				</button>
				<button onclick={eliminar} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors">
					<Trash2 size={14} /> Eliminar
				</button>
				<button onclick={modalStore.closeDetail} class="ml-auto px-4 py-2 rounded-lg text-xs font-medium bg-bg border border-border text-muted hover:text-text transition-colors">
					Cerrar
				</button>
			</div>
		</div>
	</div>
{/if}

{#if visualCanvasOpen && tarea}
	<VisualCanvas tarea={tarea} onClose={() => (visualCanvasOpen = false)} />
{/if}

{#if docOpen && tarea}
	<div class="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4" onclick={() => (docOpen = false)}>
		<div class="bg-card border border-border rounded-2xl p-5 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-base font-semibold">Informe: {tarea.titulo}</h3>
				<button onclick={() => (docOpen = false)} class="text-muted hover:text-text"><X size={20} /></button>
			</div>
			<div class="prose prose-invert max-w-none text-sm whitespace-pre-wrap">{tarea.documento}</div>
		</div>
	</div>
{/if}
