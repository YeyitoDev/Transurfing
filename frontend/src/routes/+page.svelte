<script lang="ts">
	import { ListTodo } from 'lucide-svelte';
	import { tareasStore } from '../lib/stores';
	import TaskCard from '../lib/components/TaskCard.svelte';

	let filtro = $state('todas');
	let pendientes = $derived($tareasStore.filter((t) => t.estado !== 'completada' && (filtro === 'todas' || t.etiqueta === filtro)));
</script>

{#if pendientes.length === 0}
	<div class="text-center py-16 text-muted">
		<ListTodo class="mx-auto mb-3" size={40} />
		<p>No tienes tareas pendientes</p>
	</div>
{:else}
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
		{#each pendientes as t (t.id)}
			<TaskCard tarea={t} />
		{/each}
	</div>
{/if}
