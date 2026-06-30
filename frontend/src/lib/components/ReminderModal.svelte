<script lang="ts">
	import { X } from 'lucide-svelte';
	import { api } from '../api';
	import { cargarRecordatorios } from '../hooks/useSync';
	import { reminderModalStore, modalStore } from './modalStore';

	function ahoraISO() {
		return new Date().toISOString().slice(0, 16);
	}

	let target = $derived($reminderModalStore);
	let isSub = $derived(!!target?.subtarea);
	let tarea = $derived(target?.tarea);
	let titulo = $state('');
	let fechaHora = $state(ahoraISO());

	$effect(() => {
		if (target) {
			titulo = isSub ? `Subtarea: ${target.subtarea!.titulo}` : `Tarea: ${target!.tarea!.titulo}`;
		}
	});

	async function guardar() {
		if (!tarea) return;
		try {
			await api.crearRecordatorio({
				titulo,
				fecha_hora: fechaHora,
				tarea_id: tarea.id,
				subtarea_id: isSub ? target!.subtarea!.id : null
			});
			await cargarRecordatorios();
			modalStore.closeReminder();
		} catch (e) {
			console.error(e);
		}
	}
</script>

{#if target}
	<div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 animate-fade-in" onclick={modalStore.closeReminder}>
		<div class="bg-card border border-border rounded-t-2xl sm:rounded-2xl p-6 w-full max-w-md animate-slide-up" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold">Nuevo recordatorio</h3>
				<button class="p-1 text-muted hover:text-text" onclick={modalStore.closeReminder}>
					<X size={20} />
				</button>
			</div>
			<div class="text-sm text-muted mb-3">
				{#if isSub}Subtarea: {target.subtarea!.titulo}{:else}Tarea: {target.tarea!.titulo}{/if}
			</div>
			<input class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text mb-3" bind:value={titulo} />
			<input type="datetime-local" class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text mb-4 [color-scheme:dark]" bind:value={fechaHora} />
			<div class="flex justify-end gap-2">
				<button class="px-4 py-2 rounded-xl border border-border text-muted hover:text-text transition-colors" onclick={modalStore.closeReminder}>Cancelar</button>
				<button class="px-4 py-2 rounded-xl bg-accent text-white font-medium hover:opacity-90 transition-opacity" onclick={guardar}>Guardar</button>
			</div>
		</div>
	</div>
{/if}
