<script lang="ts">
	import { Mic, X, Volume2 } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import { tareasStore } from '../stores';

	let texto = $state('');
	let respuesta = $state('');
	let loading = $state(false);
	let abierto = $state(false);

	async function enviar() {
		if (!texto.trim()) return;
		loading = true;
		respuesta = '';
		try {
			const res = await api.vozProcesar(texto);
			respuesta = res.mensaje;
			if (res.tarea_creada) onTaskChange(res.tarea_creada);
			else if (res.accion === 'agregar_subtarea' && res.tarea_numero && res.subtarea_titulo) {
				const t = await api.agregarSubtareaPorNumero(res.tarea_numero, res.subtarea_titulo);
				onTaskChange(t);
				respuesta = `✅ Subtarea añadida a la tarea #${res.tarea_numero}`;
			} else if (res.draft) {
				const confirm = await api.vozConfirmar(res.draft);
				if (confirm.tarea_creada) onTaskChange(confirm.tarea_creada);
				respuesta = confirm.mensaje || respuesta;
			}
			texto = '';
		} catch (e) {
			console.error(e);
			respuesta = 'Error procesando el comando de voz.';
		} finally {
			loading = false;
		}
	}

	async function resumen() {
		try {
			const res = await api.vozResumen();
			respuesta = res.mensaje;
			abierto = true;
		} catch (e) {
			console.error(e);
		}
	}
</script>

{#if !abierto}
	<div class="fixed right-4 bottom-24 z-40 flex flex-col gap-2 items-end">
		<button onclick={resumen} class="p-3 rounded-full bg-card border border-border text-muted hover:text-accent shadow-lg" title="Resumen por voz">
			<Volume2 size={20} />
		</button>
		<button onclick={() => (abierto = true)} class="p-3 rounded-full bg-accent text-white shadow-lg shadow-accent/30 hover:opacity-90 transition-opacity" title="Asistente de voz">
			<Mic size={20} />
		</button>
	</div>
{:else}
	<div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-4" onclick={() => (abierto = false)}>
		<div class="bg-card border border-border rounded-t-2xl sm:rounded-2xl p-5 w-full max-w-md" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-base font-semibold">Asistente de voz</h3>
				<button onclick={() => (abierto = false)} class="text-muted hover:text-text"><X size={20} /></button>
			</div>
			<div class="relative mb-3">
				<input class="w-full bg-bg border border-border rounded-xl pl-4 pr-12 py-3 text-sm text-text placeholder-muted" placeholder="Di o escribe un comando..." bind:value={texto} onkeydown={(e) => e.key === 'Enter' && enviar()} />
				<button onclick={enviar} class="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">
					<Mic size={16} />
				</button>
			</div>
			{#if loading}
				<div class="text-sm text-muted text-center py-3">Procesando...</div>
			{:else if respuesta}
				<div class="p-3 rounded-xl bg-card2 border border-border text-sm text-text">{respuesta}</div>
			{/if}
		</div>
	</div>
{/if}
