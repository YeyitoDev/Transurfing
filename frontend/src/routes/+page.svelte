<script lang="ts">
	import { ListTodo, Rows3, Grid3x3 } from 'lucide-svelte';
	import { tareasStore, densidadStore } from '../lib/stores';
	import TaskCard from '../lib/components/TaskCard.svelte';

	let filtro = $state('todas');
	let pendientes = $derived($tareasStore.filter((t) => t.estado !== 'completada' && (filtro === 'todas' || t.etiqueta === filtro)));
	let compacta = $derived($densidadStore === 'compacta');
</script>

{#if pendientes.length === 0}
	<div class="text-center py-16 text-muted">
		<ListTodo class="mx-auto mb-3" size={40} />
		<p>No tienes tareas pendientes</p>
	</div>
{:else}
	<div class="flex justify-end mb-2">
		<div class="inline-flex items-center rounded-lg border border-border bg-card overflow-hidden text-xs">
			<button onclick={() => densidadStore.set('comoda')} class="px-2.5 py-1 flex items-center gap-1 {!compacta ? 'bg-accent text-white' : 'text-muted hover:text-text'}" title="Vista cómoda"><Rows3 size={13} /> Cómoda</button>
			<button onclick={() => densidadStore.set('compacta')} class="px-2.5 py-1 flex items-center gap-1 {compacta ? 'bg-accent text-white' : 'text-muted hover:text-text'}" title="Vista compacta"><Grid3x3 size={13} /> Compacta</button>
		</div>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-2 {compacta ? 'lg:grid-cols-4' : 'lg:grid-cols-3'} gap-3">
		{#each pendientes as t (t.id)}
			<TaskCard tarea={t} compact={compacta} />
		{/each}
	</div>
{/if}
