<script lang="ts">
	import { tareasStore } from '../../lib/stores';
	import { modalStore } from '../../lib/components/modalStore';
	import ProgressBar from '../../lib/components/ProgressBar.svelte';
	import { CheckCircle2, Loader2, Circle, ListTodo, AlertTriangle, Calendar, Target } from 'lucide-svelte';
	import type { Tarea } from '../../lib/types';

	const ETIQUETA_LABEL: Record<string, string> = {
		emprendimiento: 'Emprendimiento',
		tarea: 'Tarea',
		habito: 'Hábito',
		investigacion: 'Investigación',
		idea: 'Idea'
	};

	const hoy = new Date().toISOString().slice(0, 10);

	function clasificar(t: Tarea): 'completada' | 'en_progreso' | 'pendiente' {
		if (t.estado === 'completada') return 'completada';
		if (t.en_progreso_manual || (t.progreso > 0 && t.progreso < 100)) return 'en_progreso';
		return 'pendiente';
	}

	let proyectos = $derived($tareasStore);
	let completados = $derived(proyectos.filter((t) => clasificar(t) === 'completada'));
	let enProgreso = $derived(proyectos.filter((t) => clasificar(t) === 'en_progreso'));
	let pendientes = $derived(proyectos.filter((t) => clasificar(t) === 'pendiente'));

	let subTotal = $derived(proyectos.reduce((a, t) => a + (t.subtareas_total || 0), 0));
	let subHechas = $derived(proyectos.reduce((a, t) => a + (t.subtareas_completadas || 0), 0));
	let subFaltan = $derived(subTotal - subHechas);
	let progresoGlobal = $derived(
		proyectos.length === 0 ? 0 : Math.round(proyectos.reduce((a, t) => a + (t.progreso || 0), 0) / proyectos.length)
	);

	let vencidos = $derived(
		proyectos.filter((t) => t.estado !== 'completada' && t.fecha_limite && t.fecha_limite < hoy)
	);

	const ORDEN = { en_progreso: 0, pendiente: 1, completada: 2 } as const;
	let ordenados = $derived(
		[...proyectos].sort((a, b) => {
			const da = ORDEN[clasificar(a)];
			const db = ORDEN[clasificar(b)];
			if (da !== db) return da - db;
			return (b.progreso || 0) - (a.progreso || 0);
		})
	);

	const ESTADO_META = {
		completada: { label: 'Completado', icon: CheckCircle2, cls: 'text-green-400 bg-green-500/10 border-green-500/20' },
		en_progreso: { label: 'En progreso', icon: Loader2, cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
		pendiente: { label: 'Pendiente', icon: Circle, cls: 'text-slate-300 bg-slate-500/10 border-slate-500/20' }
	} as const;
</script>

<div class="space-y-5">
	<div>
		<h1 class="text-xl font-bold">Dashboard de proyectos</h1>
		<p class="text-sm text-muted">Resumen de lo realizado y lo que falta por proyecto.</p>
	</div>

	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		<div class="bg-card border border-border rounded-2xl p-4">
			<div class="flex items-center gap-2 text-muted text-xs"><ListTodo size={14} /> Proyectos</div>
			<div class="text-2xl font-bold mt-1">{proyectos.length}</div>
			<div class="text-[11px] text-muted mt-0.5">{enProgreso.length} en progreso · {pendientes.length} pendientes</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4">
			<div class="flex items-center gap-2 text-muted text-xs"><CheckCircle2 size={14} /> Completados</div>
			<div class="text-2xl font-bold mt-1 text-green-400">{completados.length}</div>
			<div class="text-[11px] text-muted mt-0.5">{proyectos.length ? Math.round((completados.length / proyectos.length) * 100) : 0}% del total</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4">
			<div class="flex items-center gap-2 text-muted text-xs"><Target size={14} /> Subtareas</div>
			<div class="text-2xl font-bold mt-1">{subHechas}<span class="text-base text-muted">/{subTotal}</span></div>
			<div class="text-[11px] text-muted mt-0.5">faltan {subFaltan}</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4">
			<div class="flex items-center gap-2 text-muted text-xs"><AlertTriangle size={14} /> Vencidos</div>
			<div class="text-2xl font-bold mt-1 {vencidos.length ? 'text-red-400' : ''}">{vencidos.length}</div>
			<div class="text-[11px] text-muted mt-0.5">con fecha pasada</div>
		</div>
	</div>

	<div class="bg-card border border-border rounded-2xl p-4">
		<div class="flex items-center justify-between mb-1.5">
			<span class="text-xs font-medium text-text">Progreso global</span>
			<span class="text-xs font-medium text-muted">{progresoGlobal}%</span>
		</div>
		<ProgressBar pct={progresoGlobal} />
	</div>

	{#if proyectos.length === 0}
		<div class="text-center text-muted py-16">No hay proyectos todavía.</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
			{#each ordenados as t (t.id)}
				{@const estado = clasificar(t)}
				{@const meta = ESTADO_META[estado]}
				{@const Icon = meta.icon}
				{@const faltan = (t.subtareas_total || 0) - (t.subtareas_completadas || 0)}
				{@const vencido = t.estado !== 'completada' && t.fecha_limite && t.fecha_limite < hoy}
				<button
					onclick={() => modalStore.openDetail(t)}
					class="text-left bg-card border border-border rounded-2xl p-4 hover:border-accent transition-colors flex flex-col gap-2"
				>
					<div class="flex items-start justify-between gap-2">
						<div class="flex items-center gap-2 min-w-0">
							{#if t.icono}<span class="text-lg shrink-0">{t.icono}</span>{/if}
							<div class="min-w-0">
								<div class="text-sm font-semibold truncate {estado === 'completada' ? 'line-through text-muted' : 'text-text'}">{t.titulo}</div>
								<div class="text-[10px] text-muted">#{t.numero} · {ETIQUETA_LABEL[t.etiqueta] || t.etiqueta}</div>
							</div>
						</div>
						<span class="text-[10px] font-medium px-2 py-0.5 rounded-full border flex items-center gap-1 shrink-0 {meta.cls}">
							<Icon size={11} class={estado === 'en_progreso' ? 'animate-spin' : ''} /> {meta.label}
						</span>
					</div>

					<div>
						<div class="flex items-center justify-between text-[10px] text-muted mb-1">
							<span>{t.subtareas_completadas}/{t.subtareas_total} subtareas</span>
							<span>{Math.round(t.progreso)}%</span>
						</div>
						<ProgressBar pct={t.progreso} />
					</div>

					<div class="flex items-center gap-2 flex-wrap text-[10px]">
						{#if faltan > 0}
							<span class="px-2 py-0.5 rounded-full bg-card2 border border-border text-muted">Faltan {faltan}</span>
						{:else if t.subtareas_total > 0}
							<span class="px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400">Todo hecho</span>
						{/if}
						{#if t.fecha_limite}
							<span class="px-2 py-0.5 rounded-full border flex items-center gap-1 {vencido ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-card2 border-border text-muted'}">
								<Calendar size={10} /> {t.fecha_limite}
							</span>
						{/if}
					</div>

					{#if t.proxima_alta_valor}
						<div class="text-[11px] text-accent/90 border-t border-border pt-2 mt-0.5">
							<span class="text-muted">Próximo:</span> {t.proxima_alta_valor}
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
