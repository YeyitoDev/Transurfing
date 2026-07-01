<script lang="ts">
	import type { Tarea, Subtarea } from '../types';
	import { CheckCircle2, Circle, Loader2, Ban, ListTree } from 'lucide-svelte';

	let { tarea, onSelect }: { tarea: Tarea; onSelect?: (s: Subtarea) => void } = $props();

	type EstadoKey = 'completada' | 'en_progreso' | 'bloqueada' | 'pendiente';

	const ESTADO_META: Record<
		EstadoKey,
		{ label: string; dot: string; ring: string; bg: string; text: string; icon: typeof Circle }
	> = {
		completada: { label: 'Completada', dot: 'bg-green-500', ring: 'border-green-500/60', bg: 'bg-green-500/10', text: 'text-green-300', icon: CheckCircle2 },
		en_progreso: { label: 'En progreso', dot: 'bg-amber-500', ring: 'border-amber-500/60', bg: 'bg-amber-500/10', text: 'text-amber-300', icon: Loader2 },
		bloqueada: { label: 'Bloqueada', dot: 'bg-red-500', ring: 'border-red-500/60', bg: 'bg-red-500/10', text: 'text-red-300', icon: Ban },
		pendiente: { label: 'Pendiente', dot: 'bg-slate-500', ring: 'border-slate-500/50', bg: 'bg-slate-500/10', text: 'text-slate-300', icon: Circle }
	};

	function estadoDe(s: Subtarea): EstadoKey {
		return (s.estado as EstadoKey) || (s.completada ? 'completada' : 'pendiente');
	}
	function resumenDe(s: Subtarea): string {
		const r = s.resumen || s.descripcion || (s.resultado ? s.resultado.slice(0, 180) : '');
		return (r || 'Sin resumen todavía. Ábrela para añadir detalles.').trim();
	}
	function sdProgreso(s: Subtarea): { done: number; total: number } {
		const sd = s.subdetalles || [];
		return { done: sd.filter((x) => x.completada).length, total: sd.length };
	}

	let hoverId = $state<string | null>(null);
	let subs = $derived(tarea.subtareas || []);
</script>

<div class="bg-card2 border border-border rounded-xl p-3 mb-4">
	<div class="flex items-center justify-between mb-3">
		<span class="text-xs font-semibold text-text flex items-center gap-1.5">
			<ListTree size={14} class="text-accent" /> Flujograma del proyecto
		</span>
		<span class="text-[10px] text-muted">{tarea.subtareas_completadas}/{tarea.subtareas_total} · {Math.round(tarea.progreso)}%</span>
	</div>

	<div class="flex flex-col items-center">
		<!-- Nodo raíz -->
		<div class="w-full max-w-md rounded-xl border-2 border-accent/50 bg-accent/10 px-4 py-2.5 text-center">
			<div class="text-sm font-semibold text-text truncate">{tarea.titulo}</div>
			<div class="text-[10px] text-muted mt-0.5">{Math.round(tarea.progreso)}% completado</div>
		</div>

		{#if subs.length === 0}
			<div class="h-4 w-px bg-border"></div>
			<div class="text-[11px] text-muted italic py-2">Sin subtareas todavía</div>
		{:else}
			<div class="h-4 w-px bg-border"></div>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
				{#each subs as s (s.id)}
					{@const est = estadoDe(s)}
					{@const m = ESTADO_META[est]}
					{@const Icon = m.icon}
					{@const sd = sdProgreso(s)}
					<button
						type="button"
						onclick={() => onSelect?.(s)}
						onmouseenter={() => (hoverId = s.id)}
						onmouseleave={() => (hoverId = null)}
						onfocus={() => (hoverId = s.id)}
						onblur={() => (hoverId = null)}
						class="relative text-left rounded-xl border-2 {m.ring} {m.bg} px-3 py-2.5 transition-all hover:shadow-lg hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-accent/50"
					>
						<div class="flex items-center gap-2">
							<span class="w-2.5 h-2.5 rounded-full {m.dot} shrink-0 {est === 'en_progreso' ? 'animate-pulse' : ''}"></span>
							<span class="text-xs font-semibold text-text flex-1 line-clamp-2">{s.titulo}</span>
							<Icon size={13} class="{m.text} shrink-0 {est === 'en_progreso' ? 'animate-spin' : ''}" />
						</div>
						<div class="flex items-center gap-2 mt-1.5 text-[9px] flex-wrap">
							<span class="px-1.5 py-0.5 rounded-full {m.bg} {m.text} border {m.ring}">{m.label}</span>
							{#if sd.total > 0}
								<span class="text-muted flex items-center gap-1"><ListTree size={9} /> {sd.done}/{sd.total} subdetalles</span>
							{/if}
						</div>

						{#if hoverId === s.id}
							<div class="absolute z-30 left-1/2 -translate-x-1/2 top-full mt-1.5 w-64 rounded-xl border border-border bg-card shadow-2xl p-3 text-left pointer-events-none animate-fade-in">
								<div class="flex items-center gap-1.5 mb-1">
									<span class="w-2 h-2 rounded-full {m.dot}"></span>
									<span class="text-[10px] font-semibold {m.text}">{m.label}</span>
								</div>
								<div class="text-[11px] font-semibold text-text mb-1 line-clamp-2">{s.titulo}</div>
								<div class="text-[10px] text-muted line-clamp-4">{resumenDe(s)}</div>
								{#if sd.total > 0}
									<div class="mt-2 h-1 rounded-full bg-card2 overflow-hidden">
										<div class="h-full {m.dot}" style="width:{Math.round((sd.done / sd.total) * 100)}%"></div>
									</div>
									<div class="mt-1 text-[9px] text-muted">{sd.done}/{sd.total} subdetalles hechos</div>
								{/if}
								<div class="mt-1.5 text-[9px] text-accent">Clic para ver el detalle →</div>
							</div>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Leyenda -->
	<div class="flex flex-wrap gap-x-3 gap-y-1 mt-3 pt-2.5 border-t border-border text-[9px] text-muted">
		{#each Object.entries(ESTADO_META) as [key, m] (key)}
			<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full {m.dot}"></span> {m.label}</span>
		{/each}
	</div>
</div>
