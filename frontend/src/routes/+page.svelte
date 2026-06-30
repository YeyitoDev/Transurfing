<script lang="ts">
	import { ListTodo, Rows3, Grid3x3, Trash2, X, Loader2 } from 'lucide-svelte';
	import { tareasStore, densidadStore, onTaskChange } from '../lib/stores';
	import { api } from '../lib/api';
	import { rubberband } from '../lib/actions/rubberband';
	import TaskCard from '../lib/components/TaskCard.svelte';

	let filtro = $state('todas');
	let pendientes = $derived($tareasStore.filter((t) => t.estado !== 'completada' && (filtro === 'todas' || t.etiqueta === filtro)));
	let compacta = $derived($densidadStore === 'compacta');

	let seleccion = $state<string[]>([]);
	let borrando = $state(false);

	async function eliminarSeleccion() {
		if (seleccion.length === 0) return;
		if (!confirm(`¿Eliminar ${seleccion.length} tarea(s)? Esta acción no se puede deshacer.`)) return;
		const ids = [...seleccion];
		borrando = true;
		seleccion = [];
		try {
			for (const id of ids) {
				await api.eliminarTarea(id);
				onTaskChange(null, id);
			}
		} catch (e) {
			console.error(e);
		} finally {
			borrando = false;
		}
	}
</script>

{#if pendientes.length === 0}
	<div class="text-center py-16 text-muted">
		<ListTodo class="mx-auto mb-3" size={40} />
		<p>No tienes tareas pendientes</p>
	</div>
{:else}
	<div class="flex items-center justify-between mb-2 gap-2">
		<span class="text-[11px] text-muted hidden sm:block">Arrastra sobre las tarjetas para seleccionar varias y eliminarlas.</span>
		<div class="inline-flex items-center rounded-lg border border-border bg-card overflow-hidden text-xs">
			<button onclick={() => densidadStore.set('comoda')} class="px-2.5 py-1 flex items-center gap-1 {!compacta ? 'bg-accent text-white' : 'text-muted hover:text-text'}" title="Vista cómoda"><Rows3 size={13} /> Cómoda</button>
			<button onclick={() => densidadStore.set('compacta')} class="px-2.5 py-1 flex items-center gap-1 {compacta ? 'bg-accent text-white' : 'text-muted hover:text-text'}" title="Vista compacta"><Grid3x3 size={13} /> Compacta</button>
		</div>
	</div>
	<div use:rubberband={{ itemSelector: '[data-taskid]', onChange: (ids) => (seleccion = ids) }} class="grid grid-cols-1 md:grid-cols-2 {compacta ? 'lg:grid-cols-4' : 'lg:grid-cols-3'} gap-3">
		{#each pendientes as t (t.id)}
			<div data-taskid={t.id} class="rounded-2xl {seleccion.includes(t.id) ? 'ring-2 ring-accent' : ''}">
				<TaskCard tarea={t} compact={compacta} />
			</div>
		{/each}
	</div>
{/if}

{#if seleccion.length > 0}
	<div class="fixed bottom-20 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-card border border-border rounded-2xl shadow-xl px-4 py-2.5">
		<span class="text-sm font-semibold text-text">{seleccion.length} seleccionada(s)</span>
		<button onclick={eliminarSeleccion} disabled={borrando} class="flex items-center gap-1.5 text-xs font-medium bg-red-500/15 text-red-400 border border-red-500/30 rounded-lg px-3 py-1.5 hover:bg-red-500/25 disabled:opacity-50">
			{#if borrando}<Loader2 size={13} class="animate-spin" />{:else}<Trash2 size={13} />{/if} Eliminar
		</button>
		<button onclick={() => (seleccion = [])} class="flex items-center gap-1 text-xs text-muted hover:text-text border border-border rounded-lg px-3 py-1.5"><X size={13} /> Cancelar</button>
	</div>
{/if}
