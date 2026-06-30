<script lang="ts">
	import { Bot, X, Loader2, Send } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import type { Agente } from '../types';

	let agentes = $state<Agente[]>([]);
	let prompt = $state('');
	let respuesta = $state('');
	let loading = $state(false);
	let error = $state('');
	let abierto = $state(true);

	async function cargar() {
		try {
			const res = await api.listarAgentes();
			agentes = res.agentes;
		} catch (e) {
			console.error(e);
		}
	}

	async function ejecutar(agente: Agente) {
		if (!prompt.trim()) return;
		loading = true;
		respuesta = '';
		error = '';
		try {
			const res = await api.ejecutarAgente(agente.id, prompt);
			respuesta = res.respuesta;
		} catch (e) {
			console.error(e);
			error = 'Error ejecutando el agente.';
		} finally {
			loading = false;
		}
	}

	async function agenteRecordatorio() {
		loading = true;
		respuesta = '';
		error = '';
		try {
			const res = await api.agenteRecordatorio();
			respuesta = res.mensaje;
		} catch (e) {
			console.error(e);
			error = 'Error consultando agente.';
		} finally {
			loading = false;
		}
	}

	cargar();
</script>

{#if abierto}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onclick={() => (abierto = false)}>
		<div class="bg-card border border-border rounded-2xl p-5 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-base font-semibold flex items-center gap-2"><Bot size={20} /> Agentes especializados</h3>
				<button onclick={() => (abierto = false)} class="text-muted hover:text-text"><X size={20} /></button>
			</div>

			<button onclick={agenteRecordatorio} class="mb-4 px-4 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:opacity-90 transition-opacity">Resumen del agente de recordatorios</button>

			<div class="mb-4">
				<label class="text-xs text-muted font-medium mb-1.5 block">Prompt</label>
				<div class="flex gap-2">
					<input class="flex-1 bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text" placeholder="Pregunta a los agentes..." bind:value={prompt} onkeydown={(e) => e.key === 'Enter' && agentes[0] && ejecutar(agentes[0])} />
					<button onclick={() => agentes[0] && ejecutar(agentes[0])} class="bg-accent text-white rounded-xl px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity">
						<Send size={16} />
					</button>
				</div>
			</div>

			{#if loading}
				<div class="text-center text-muted py-4"><Loader2 class="animate-spin inline" size={20} /> Procesando...</div>
			{/if}
			{#if error}
				<div class="p-3 rounded-xl bg-red-500/10 text-red-300 text-sm mb-3">{error}</div>
			{/if}
			{#if respuesta}
				<div class="p-3 rounded-xl bg-card2 border border-border text-sm text-text whitespace-pre-wrap">{respuesta}</div>
			{/if}

			<div class="mt-4">
				<h4 class="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Agentes ({agentes.length})</h4>
				{#if agentes.length === 0}
					<div class="text-sm text-muted">No hay agentes configurados</div>
				{:else}
					<div class="space-y-2">
						{#each agentes as agente}
							<div class="p-3 rounded-xl bg-card2 border border-border flex items-center justify-between">
								<div>
									<div class="text-sm font-medium">{agente.nombre}</div>
									<div class="text-xs text-muted">{agente.modelo}</div>
								</div>
								<button onclick={() => ejecutar(agente)} class="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity">Ejecutar</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
