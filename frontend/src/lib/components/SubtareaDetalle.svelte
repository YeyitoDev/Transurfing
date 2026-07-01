<script lang="ts">
	import { X, Sparkles, Loader2, Plus, Trash2, Check, Wand2, ListTree } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import type { Subtarea } from '../types';

	let { sub, onClose }: { sub: Subtarea; onClose: () => void } = $props();

	let nuevoSd = $state('');
	let addingSd = $state(false);
	let sintetizando = $state(false);
	let instrucciones = $state('');
	let mostrarInstr = $state(false);
	let error = $state('');
	let busy = $state<string | null>(null);

	const ESTADOS: { key: NonNullable<Subtarea['estado']>; label: string; cls: string }[] = [
		{ key: 'pendiente', label: 'Pendiente', cls: 'bg-slate-500/15 text-slate-300 border-slate-500/40' },
		{ key: 'en_progreso', label: 'En progreso', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/40' },
		{ key: 'bloqueada', label: 'Bloqueada', cls: 'bg-red-500/15 text-red-300 border-red-500/40' },
		{ key: 'completada', label: 'Completada', cls: 'bg-green-500/15 text-green-300 border-green-500/40' }
	];

	let subdetalles = $derived(sub.subdetalles || []);
	let sdDone = $derived(subdetalles.filter((s) => s.completada).length);
	let estadoActual = $derived(sub.estado || (sub.completada ? 'completada' : 'pendiente'));

	async function cambiarEstado(estado: NonNullable<Subtarea['estado']>) {
		try {
			onTaskChange(await api.actualizarSubtarea(sub.id, { estado, completada: estado === 'completada' }));
		} catch (e: any) {
			error = e?.message || 'Error';
		}
	}

	async function toggleSd(id: string, completada: boolean) {
		busy = id;
		try {
			onTaskChange(await api.actualizarSubdetalle(id, { completada: !completada }));
		} catch (e: any) {
			error = e?.message || 'Error';
		} finally {
			busy = null;
		}
	}

	async function guardarTitulo(id: string, titulo: string) {
		const t0 = titulo.trim();
		if (!t0) return;
		try {
			onTaskChange(await api.actualizarSubdetalle(id, { titulo: t0 }));
		} catch (e: any) {
			error = e?.message || 'Error';
		}
	}

	async function eliminarSd(id: string) {
		busy = id;
		try {
			onTaskChange(await api.eliminarSubdetalle(id));
		} catch (e: any) {
			error = e?.message || 'Error';
		} finally {
			busy = null;
		}
	}

	async function agregarSd() {
		const t0 = nuevoSd.trim();
		if (!t0) return;
		addingSd = true;
		try {
			onTaskChange(await api.agregarSubdetalle(sub.id, t0));
			nuevoSd = '';
		} catch (e: any) {
			error = e?.message || 'Error';
		} finally {
			addingSd = false;
		}
	}

	async function sintetizar() {
		sintetizando = true;
		error = '';
		try {
			const res = await api.sintetizarSubtarea(sub.id, { instrucciones });
			if (!res.ok) {
				error = res.error || 'No se pudo sintetizar.';
				return;
			}
			if (res.tarea) onTaskChange(res.tarea);
			instrucciones = '';
			mostrarInstr = false;
		} catch (e: any) {
			error = e?.message || 'Error al sintetizar.';
		} finally {
			sintetizando = false;
		}
	}
</script>

<div
	class="fixed inset-0 z-[70] flex items-end sm:items-center justify-center bg-black/70 animate-fade-in sm:p-4"
	onclick={onClose}
	role="presentation"
>
	<div
		class="bg-card border border-border rounded-t-2xl sm:rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col animate-slide-up"
		onclick={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
	>
		<div class="flex items-center justify-between px-4 py-3 border-b border-border">
			<div class="text-sm font-semibold flex items-center gap-2 min-w-0">
				<ListTree size={15} class="text-accent shrink-0" />
				<span class="truncate">{sub.titulo}</span>
			</div>
			<button onclick={onClose} class="text-muted hover:text-text shrink-0" aria-label="Cerrar"><X size={20} /></button>
		</div>

		<div class="overflow-y-auto px-4 py-3 space-y-4">
			<div class="flex flex-wrap gap-1.5">
				{#each ESTADOS as e (e.key)}
					<button
						onclick={() => cambiarEstado(e.key)}
						class="text-[10px] font-medium px-2.5 py-1 rounded-full border transition-colors {estadoActual === e.key ? e.cls : 'bg-card2 text-muted border-border hover:text-text'}"
					>{e.label}</button>
				{/each}
			</div>

			{#if sub.descripcion}
				<div>
					<div class="text-[10px] font-semibold text-muted uppercase tracking-wide mb-1">Descripción</div>
					<p class="text-sm text-text">{sub.descripcion}</p>
				</div>
			{/if}
			{#if sub.resumen}
				<div class="rounded-xl border border-accent/30 bg-accent/5 p-2.5 text-xs text-text">
					<span class="text-accent font-semibold">Resumen:</span> {sub.resumen}
				</div>
			{/if}

			<div class="rounded-xl border border-border bg-card2 p-3">
				<div class="flex items-center justify-between gap-2">
					<div class="text-xs font-semibold text-text flex items-center gap-1.5"><Wand2 size={14} class="text-accent" /> Agente de síntesis</div>
					<button
						onclick={sintetizar}
						disabled={sintetizando}
						class="flex items-center gap-1.5 text-[11px] font-medium bg-accent text-white rounded-lg px-3 py-1.5 disabled:opacity-50"
					>
						{#if sintetizando}<Loader2 size={13} class="animate-spin" />{:else}<Sparkles size={13} />{/if}
						Sintetizar
					</button>
				</div>
				<p class="text-[10px] text-muted mt-1">Reescribe la idea y genera subdetalles ordenados y accionables.</p>
				<button onclick={() => (mostrarInstr = !mostrarInstr)} class="text-[10px] text-accent hover:underline mt-1">
					{mostrarInstr ? 'Ocultar instrucciones' : 'Añadir instrucciones'}
				</button>
				{#if mostrarInstr}
					<textarea
						bind:value={instrucciones}
						rows="2"
						placeholder="Ej: enfócate en pasos técnicos, o resúmelo en 3 puntos…"
						class="w-full mt-1.5 bg-card border border-border rounded-lg px-2.5 py-1.5 text-xs text-text resize-none focus:outline-none focus:border-accent"
					></textarea>
				{/if}
			</div>

			<div>
				<div class="flex items-center justify-between mb-2">
					<div class="text-xs font-semibold text-text">
						Subdetalles
						{#if subdetalles.length}<span class="text-muted font-normal">({sdDone}/{subdetalles.length})</span>{/if}
					</div>
				</div>
				<div class="space-y-1.5">
					{#each subdetalles as sd (sd.id)}
						<div class="flex items-center gap-2 group">
							<button
								onclick={() => toggleSd(sd.id, sd.completada)}
								disabled={busy === sd.id}
								class="w-4 h-4 min-w-4 rounded border flex items-center justify-center transition-colors {sd.completada ? 'bg-green-500 border-green-500 text-white' : 'border-border hover:border-accent'}"
								aria-label="Alternar subdetalle"
							>
								{#if sd.completada}<Check size={11} />{/if}
							</button>
							<input
								value={sd.titulo}
								onchange={(e) => guardarTitulo(sd.id, (e.target as HTMLInputElement).value)}
								class="flex-1 bg-transparent text-sm text-text focus:outline-none border-b border-transparent focus:border-border {sd.completada ? 'line-through text-muted' : ''}"
							/>
							<button onclick={() => eliminarSd(sd.id)} class="text-muted hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" aria-label="Eliminar subdetalle">
								<Trash2 size={13} />
							</button>
						</div>
					{/each}
					{#if subdetalles.length === 0}
						<p class="text-[11px] text-muted italic">Sin subdetalles. Añade pasos o usa el agente de síntesis.</p>
					{/if}
				</div>
				<form onsubmit={(e) => { e.preventDefault(); agregarSd(); }} class="flex items-center gap-2 mt-2">
					<input
						bind:value={nuevoSd}
						placeholder="Nuevo subdetalle…"
						class="flex-1 bg-card2 border border-border rounded-lg px-2.5 py-1.5 text-xs text-text focus:outline-none focus:border-accent"
					/>
					<button
						type="submit"
						disabled={addingSd || !nuevoSd.trim()}
						class="bg-card2 border border-border rounded-lg p-1.5 text-accent hover:bg-accent/10 disabled:opacity-40"
						aria-label="Añadir subdetalle"
					>
						{#if addingSd}<Loader2 size={14} class="animate-spin" />{:else}<Plus size={14} />{/if}
					</button>
				</form>
			</div>

			{#if error}<div class="text-[11px] text-red-400">{error}</div>{/if}
		</div>
	</div>
</div>
