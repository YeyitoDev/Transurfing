<script lang="ts">
	import { Bell, Trash2, Rocket, CheckSquare, Heart, Calendar, Search, Clock, Pencil, Lightbulb, FileText, Expand, Sparkles, Github, Code2, Workflow } from 'lucide-svelte';
	import type { Tarea } from '../types';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import { modalStore } from './modalStore';
	import ProgressBar from './ProgressBar.svelte';
	import VisualCanvas from './VisualCanvas.svelte';

	const ETIQUETA_CONFIG: Record<string, { label: string; icon: typeof Rocket; color: string; bg: string; text: string; border: string }> = {
		emprendimiento: { label: 'Emprendimiento', icon: Rocket, color: 'indigo', bg: 'bg-indigo-500/15', text: 'text-indigo-300', border: 'border-l-indigo-500' },
		tarea: { label: 'Tarea', icon: CheckSquare, color: 'slate', bg: 'bg-slate-500/15', text: 'text-slate-300', border: 'border-l-slate-400' },
		habito: { label: 'Hábito', icon: Heart, color: 'pink', bg: 'bg-pink-500/15', text: 'text-pink-300', border: 'border-l-pink-500' },
		investigacion: { label: 'Investigación', icon: Search, color: 'cyan', bg: 'bg-cyan-500/15', text: 'text-cyan-300', border: 'border-l-cyan-500' },
		idea: { label: 'Idea', icon: Lightbulb, color: 'amber', bg: 'bg-amber-500/15', text: 'text-amber-300', border: 'border-l-amber-500' }
	};

	const PRIORIDAD_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
		alta: { label: 'Alta', bg: 'bg-red-500/15', text: 'text-red-400', dot: 'bg-red-500' },
		media: { label: 'Media', bg: 'bg-amber-500/15', text: 'text-amber-400', dot: 'bg-amber-500' },
		baja: { label: 'Baja', bg: 'bg-green-500/15', text: 'text-green-400', dot: 'bg-green-500' }
	};

	function hoyISO() {
		return new Date().toISOString().slice(0, 10);
	}

	let { tarea, compact = false }: { tarea: Tarea; compact?: boolean } = $props();
	let docOpen = $state(false);
	let visualCanvasOpen = $state(false);
	let done = $derived(tarea.estado === 'completada');
	let tieneInforme = $derived(!!tarea.documento);
	let vencida = $derived(tarea.fecha_limite && tarea.fecha_limite < hoyISO() && !done);
	let enProgreso = $derived(tarea.progreso > 0 && tarea.progreso < 100);
	let esHabito = $derived(tarea.etiqueta === 'habito' || tarea.repetible);
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
			if (dia.toISOString().slice(0, 10) === anterior.toISOString().slice(0, 10)) {
				racha++;
			} else {
				break;
			}
		}
		return racha;
	}
	let rachaHabito = $derived(esHabito ? calcularRacha(tarea.habito_log) : 0);
	let totalCompletadosHabito = $derived(tarea.habito_log.length);
	let etq = $derived(ETIQUETA_CONFIG[tarea.etiqueta] || ETIQUETA_CONFIG.tarea);
	let pri = $derived(PRIORIDAD_CONFIG[tarea.prioridad] || PRIORIDAD_CONFIG.media);
	let EtqIcon = $derived(etq.icon);
	let statusBadge = $derived(
		done
			? { label: 'Completada', bg: 'bg-green-500/20', text: 'text-green-400' }
			: vencida
				? { label: 'Vencida', bg: 'bg-red-500/20', text: 'text-red-400' }
				: enProgreso
					? { label: 'En progreso', bg: 'bg-blue-500/20', text: 'text-blue-400' }
					: { label: 'Pendiente', bg: 'bg-zinc-500/20', text: 'text-zinc-400' }
	);
	let subStats = $derived(() => {
		const subs = tarea.subtareas || [];
		const conResultado = subs.filter((s) => s.resultado).length;
		const scores = subs.filter((s) => s.score != null).map((s) => s.score as number);
		const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
		const iteraciones = subs.reduce((acc, s) => acc + (s.iteraciones?.length || 0), 0);
		return { conResultado, avgScore, iteraciones };
	});
	let stats = $derived(subStats());

	async function toggleManual(e: Event) {
		e.stopPropagation();
		const optimistic = { ...tarea, completada_manual: !done, estado: (!done ? 'completada' : 'pendiente') as Tarea['estado'] };
		onTaskChange(optimistic);
		try {
			const t = await api.actualizarTarea(tarea.id, { completada_manual: !done });
			onTaskChange(t);
		} catch {
			onTaskChange(tarea);
		}
	}

	async function delTask(e: Event) {
		e.stopPropagation();
		if (!confirm('¿Eliminar esta tarea?')) return;
		onTaskChange(null, tarea.id);
		try {
			await api.eliminarTarea(tarea.id);
		} catch {
			onTaskChange(tarea);
		}
	}
</script>

<div class="h-[180px] flex flex-col bg-card border border-border {etq.border} border-l-4 rounded-2xl overflow-hidden transition-all hover:shadow-lg hover:scale-[1.01] {done ? 'opacity-50' : ''} {vencida ? 'ring-1 ring-red-500/30' : ''}">
	<div class="flex-1 flex flex-col p-4 cursor-pointer" onclick={() => modalStore.openDetail(tarea)}>
		<div class="flex items-start gap-3 min-h-0">
			<div class="w-6 h-6 min-w-6 mt-0.5 rounded-lg border-2 flex items-center justify-center text-xs transition-all {done ? 'bg-green border-green text-white' : 'border-border hover:border-accent'}" onclick={toggleManual} title={done ? 'Marcar pendiente' : 'Marcar completada'}>
				{#if done}✓{/if}
			</div>
			<div class="flex-1 min-w-0">
				<div class="flex items-center gap-2 mb-1">
					<span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-card2 text-muted border border-border">#{tarea.numero}</span>
					<div class="text-sm font-semibold leading-snug line-clamp-2 {done ? 'line-through' : ''}">{tarea.titulo}</div>
				</div>
				{#if tarea.descripcion && !compact}
					<p class="text-xs text-muted mt-1 line-clamp-2">{tarea.descripcion}</p>
				{/if}
				{#if esHabito}
					<div class="flex items-center gap-2 mt-2 text-[10px]">
						<span class="px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">Racha: {rachaHabito} días</span>
						<span class="px-2 py-0.5 rounded-full bg-card2 text-muted">Completado: {totalCompletadosHabito} veces</span>
					</div>
				{/if}
			</div>
		</div>

		<div class="flex items-center gap-1.5 mt-2 flex-wrap">
			<span class="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 {etq.bg} {etq.text}">
				<EtqIcon size={10} />
				{etq.label}
			</span>
			<span class="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 {pri.bg} {pri.text}">
				<span class="w-1.5 h-1.5 rounded-full {pri.dot}"></span>
				{pri.label}
			</span>
			<span class="text-[10px] font-medium px-2 py-0.5 rounded-full {statusBadge.bg} {statusBadge.text}">{statusBadge.label}</span>
			{#if tarea.github_repo}
				<span class="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 bg-slate-500/15 text-slate-300">
					<Github size={10} />
					{tarea.github_repo}
				</span>
			{/if}
			{#if stats.conResultado > 0}
				<span class="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 bg-indigo-500/15 text-indigo-300" title="Subtareas con resultado de agente">
					<Sparkles size={10} />
					{stats.conResultado} agente{stats.conResultado > 1 ? 's' : ''}
				</span>
			{/if}
			{#if stats.avgScore != null}
				<span class="text-[10px] font-medium px-2 py-0.5 rounded-full {stats.avgScore >= 80 ? 'bg-green-500/15 text-green-400' : stats.avgScore >= 60 ? 'bg-amber-500/15 text-amber-400' : 'bg-red-500/15 text-red-400'}" title="Score promedio de subtareas">
					{stats.avgScore}/100
				</span>
			{/if}
			{#if stats.iteraciones > 0}
				<span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-500/15 text-slate-300" title="Iteraciones totales">
					{stats.iteraciones} iteración{stats.iteraciones > 1 ? 'es' : ''}
				</span>
			{/if}
			{#if tarea.canvas && tarea.canvas.bloques && tarea.canvas.bloques.length > 0}
				<span class="text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 bg-purple-500/15 text-purple-300" title="Tiene lienzo visual">
					<Workflow size={10} />
					{tarea.canvas.bloques.length} bloque{tarea.canvas.bloques.length > 1 ? 's' : ''}
				</span>
			{/if}
		</div>

		<div class="mt-auto pt-3">
			{#if tarea.proxima_alta_valor}
				<div class="flex items-start gap-1.5 text-[10px] text-accent mb-2 line-clamp-1" title={tarea.proxima_alta_valor}>
					<Sparkles size={10} class="mt-0.5 shrink-0" />
					<span>{tarea.proxima_alta_valor}</span>
				</div>
			{/if}
			<div class="flex items-center gap-2 text-[10px] text-muted mb-2">
				{#if tarea.fecha_limite}
					<span class="flex items-center gap-1 px-2 py-0.5 rounded-full {vencida ? 'bg-red-500/15 text-red-400' : 'bg-card2'}">
						<Calendar size={10} />
						{tarea.fecha_limite}
					</span>
				{/if}
				{#if tarea.horas && tarea.horas.length > 0}
					<span class="flex items-center gap-1 px-2 py-0.5 rounded-full bg-pink-500/15 text-pink-300">
						<Clock size={10} />
						{tarea.horas.join(', ')}
					</span>
				{/if}
				{#if tarea.subtareas_total > 0}
					<span class="px-2 py-0.5 rounded-full bg-card2">{tarea.subtareas_completadas}/{tarea.subtareas_total} subtareas</span>
				{/if}
			</div>

			<div class="flex items-center justify-between gap-3">
				<ProgressBar pct={tarea.progreso} />
				<div class="flex items-center gap-1">
					{#if tieneInforme}
						<button class="p-1.5 rounded-lg text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 transition-colors" onclick={(e) => { e.stopPropagation(); docOpen = true; }} title="Ver informe detallado">
							<FileText size={15} />
						</button>
					{/if}
					<button class="p-1.5 rounded-lg text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 transition-colors" onclick={(e) => { e.stopPropagation(); visualCanvasOpen = true; }} title="Abrir lienzo visual">
						<Workflow size={15} />
					</button>
					<button class="p-1.5 rounded-lg text-muted hover:text-accent hover:bg-accent/10 transition-colors" onclick={(e) => { e.stopPropagation(); modalStore.openReminder({ tarea }); }}>
						<Bell size={15} />
					</button>
					<button class="p-1.5 rounded-lg text-muted hover:text-blue-400 hover:bg-blue-400/10 transition-colors" onclick={(e) => { e.stopPropagation(); modalStore.openEdit(tarea); }}>
						<Pencil size={15} />
					</button>
					<button class="p-1.5 rounded-lg text-muted hover:text-red hover:bg-red-500/10 transition-colors" onclick={delTask}>
						<Trash2 size={15} />
					</button>
					{#if tarea.github_repo}
						<button class="p-1.5 rounded-lg text-accent hover:text-text hover:bg-accent/10 transition-colors" onclick={(e) => { e.stopPropagation(); modalStore.openDetail(tarea); }} title="GitHub">
							<Code2 size={15} />
						</button>
					{/if}
					<button class="p-1.5 rounded-lg text-muted hover:text-text hover:bg-card2 transition-colors" onclick={(e) => { e.stopPropagation(); modalStore.openDetail(tarea); }} title="Ver detalle">
						<Expand size={15} />
					</button>
				</div>
			</div>
		</div>
	</div>
</div>

{#if visualCanvasOpen}
	<VisualCanvas {tarea} onClose={() => (visualCanvasOpen = false)} />
{/if}
