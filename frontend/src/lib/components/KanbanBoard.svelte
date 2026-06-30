<script lang="ts">
	import { tareasStore } from '../stores';
	import TaskCard from './TaskCard.svelte';
	import type { Tarea } from '../types';

	const cols = [
		{ key: 'pendiente', label: 'Pendientes' },
		{ key: 'en_progreso', label: 'En progreso' },
		{ key: 'completada', label: 'Completadas' }
	] as const;

	let { tareas, compact = true }: { tareas: Tarea[]; compact?: boolean } = $props();

	$effect(() => {
		// keep reactive if parent passes a filtered subset
	});

	const porCol = $derived({
		pendiente: tareas.filter((t) => t.progreso === 0 && t.estado !== 'completada'),
		en_progreso: tareas.filter((t) => t.progreso > 0 && t.progreso < 100),
		completada: tareas.filter((t) => t.estado === 'completada')
	});
</script>

<div class="flex gap-3 overflow-x-auto pb-3 -mx-4 px-4">
	{#each cols as col}
		<div class="min-w-[260px] w-[260px] bg-card border border-border rounded-2xl p-3 flex flex-col gap-2">
			<h3 class="text-xs font-semibold text-muted uppercase tracking-wide mb-1">{col.label} ({porCol[col.key].length})</h3>
			{#each porCol[col.key] as t}
				<TaskCard tarea={t} {compact} />
			{/each}
			{#if porCol[col.key].length === 0}
				<div class="text-center text-muted text-xs py-8">Sin tareas</div>
			{/if}
		</div>
	{/each}
</div>
