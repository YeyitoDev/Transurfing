<script lang="ts">
	import { Check, Trash2, Bell } from 'lucide-svelte';
	import { api } from '../api';
	import { recordatoriosStore, onRecordatorioChange } from '../stores';

	async function completar(r: import('../types').Recordatorio) {
		try {
			await api.actualizarRecordatorio(r.id, { estado: 'completado' });
			onRecordatorioChange({ ...r, estado: 'completado' });
		} catch (e) {
			console.error(e);
		}
	}

	async function eliminar(r: import('../types').Recordatorio) {
		if (!confirm('¿Eliminar recordatorio?')) return;
		try {
			await api.eliminarRecordatorio(r.id);
			onRecordatorioChange(null, r.id);
		} catch (e) {
			console.error(e);
		}
	}
</script>

{#if $recordatoriosStore.length === 0}
	<div class="text-center text-muted py-16">
		<Bell size={40} class="mx-auto mb-3 opacity-40" />
		<p class="text-sm">Sin alarmas activas</p>
	</div>
{:else}
	<div class="space-y-2">
		{#each $recordatoriosStore as r}
			<div class="bg-card border rounded-xl p-4 flex items-center gap-3 {r.proximo ? 'border-red-500/50 bg-red-500/5' : 'border-border'}">
				<div class="flex-1 min-w-0">
					<div class="text-sm font-semibold">{r.titulo}</div>
					<div class="text-xs text-muted mt-1">
						{r.fecha_hora.replace('T', ' ')}
						{#if r.tarea_titulo} · {r.tarea_titulo}{/if}
						{#if r.subtarea_titulo} / {r.subtarea_titulo}{/if}
					</div>
				</div>
				{#if r.proximo}
					<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">AHORA</span>
				{/if}
				<button class="p-2 rounded-lg text-muted hover:text-green transition-colors" onclick={() => completar(r)}>
					<Check size={18} />
				</button>
				<button class="p-2 rounded-lg text-muted hover:text-red transition-colors" onclick={() => eliminar(r)}>
					<Trash2 size={18} />
				</button>
			</div>
		{/each}
	</div>
{/if}
