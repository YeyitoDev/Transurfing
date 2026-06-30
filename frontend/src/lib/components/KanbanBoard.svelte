<script lang="ts">
	import { onTaskChange } from '../stores';
	import { api } from '../api';
	import TaskCard from './TaskCard.svelte';
	import type { Tarea } from '../types';

	const cols = [
		{ key: 'pendiente', label: 'Pendientes' },
		{ key: 'en_progreso', label: 'En progreso' },
		{ key: 'completada', label: 'Completadas' }
	] as const;

	let { tareas, compact = true }: { tareas: Tarea[]; compact?: boolean } = $props();

	let dragId = $state<string | null>(null);
	let dragOverCol = $state<string | null>(null);

	function onDragStart(e: DragEvent, id: string) {
		dragId = id;
		if (e.dataTransfer) {
			e.dataTransfer.setData('text/plain', id);
			e.dataTransfer.effectAllowed = 'move';
		}
	}

	async function moverA(colKey: string, id: string) {
		const completar = colKey === 'completada';
		const prev = tareas.find((t) => t.id === id);
		if (!prev) return;
		onTaskChange({ ...prev, completada_manual: completar, estado: completar ? 'completada' : 'pendiente' } as Tarea);
		try {
			const t = await api.actualizarTarea(id, { completada_manual: completar });
			onTaskChange(t);
		} catch (err) {
			console.error(err);
			onTaskChange(prev);
		}
	}

	function onDrop(e: DragEvent, colKey: string) {
		e.preventDefault();
		const id = dragId || e.dataTransfer?.getData('text/plain') || '';
		dragOverCol = null;
		dragId = null;
		if (id) moverA(colKey, id);
	}

	const porCol = $derived({
		pendiente: tareas.filter((t) => t.progreso === 0 && t.estado !== 'completada'),
		en_progreso: tareas.filter((t) => t.progreso > 0 && t.progreso < 100),
		completada: tareas.filter((t) => t.estado === 'completada')
	});
</script>

<div class="flex gap-3 overflow-x-auto pb-3 -mx-4 px-4">
	{#each cols as col}
		<div
			class="min-w-[260px] w-[260px] bg-card border rounded-2xl p-3 flex flex-col gap-2 transition-colors {dragOverCol === col.key ? 'border-accent ring-2 ring-accent/40' : 'border-border'}"
			role="list"
			ondragover={(e) => { e.preventDefault(); dragOverCol = col.key; }}
			ondragleave={() => { if (dragOverCol === col.key) dragOverCol = null; }}
			ondrop={(e) => onDrop(e, col.key)}
		>
			<h3 class="text-xs font-semibold text-muted uppercase tracking-wide mb-1">{col.label} ({porCol[col.key].length})</h3>
			{#each porCol[col.key] as t}
				<div draggable="true" ondragstart={(e) => onDragStart(e, t.id)} class="cursor-grab active:cursor-grabbing">
					<TaskCard tarea={t} {compact} />
				</div>
			{/each}
			{#if porCol[col.key].length === 0}
				<div class="text-center text-muted text-xs py-8">Sin tareas{dragOverCol === col.key ? ' · soltar aquí' : ''}</div>
			{/if}
		</div>
	{/each}
</div>
