<script lang="ts">
	import { CheckCircle2 } from 'lucide-svelte';
	import { tareasStore } from '../../lib/stores';
	import TaskCard from '../../lib/components/TaskCard.svelte';

	let completadas = $derived($tareasStore.filter((t) => t.estado === 'completada'));
</script>

{#if completadas.length === 0}
	<div class="text-center py-16 text-muted">
		<CheckCircle2 class="mx-auto mb-3" size={40} />
		<p>No tienes tareas completadas</p>
	</div>
{:else}
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
		{#each completadas as t (t.id)}
			<TaskCard tarea={t} />
		{/each}
	</div>
{/if}
