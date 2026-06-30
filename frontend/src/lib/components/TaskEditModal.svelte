<script lang="ts">
	import { X, Save, Trash2, Rocket, CheckSquare, Heart, Search, Repeat, Clock, Plus, Lightbulb } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import { editModalStore, modalStore } from './modalStore';
	import type { Tarea } from '../types';

	const TIPOS = [
		{ key: 'emprendimiento', label: 'Emprendimiento', icon: Rocket, color: 'indigo' },
		{ key: 'tarea', label: 'Tarea', icon: CheckSquare, color: 'slate' },
		{ key: 'habito', label: 'Hábito', icon: Heart, color: 'pink' },
		{ key: 'investigacion', label: 'Investigación', icon: Search, color: 'cyan' },
		{ key: 'idea', label: 'Idea', icon: Lightbulb, color: 'amber' }
	] as const;

	const PRIORIDADES = [
		{ key: 'alta', label: 'Alta', color: 'red' },
		{ key: 'media', label: 'Media', color: 'yellow' },
		{ key: 'baja', label: 'Baja', color: 'green' }
	] as const;

	const DIAS = [
		{ key: 'lun', label: 'L' },
		{ key: 'mar', label: 'M' },
		{ key: 'mie', label: 'X' },
		{ key: 'jue', label: 'J' },
		{ key: 'vie', label: 'V' },
		{ key: 'sab', label: 'S' },
		{ key: 'dom', label: 'D' }
	] as const;

	let tarea = $derived($editModalStore);
	let titulo = $state('');
	let descripcion = $state('');
	let prioridad = $state<Tarea['prioridad']>('media');
	let etiqueta = $state('tarea');
	let repetible = $state(false);
	let fechaLimite = $state('');
	let horas = $state<string[]>([]);
	let nuevaHora = $state('');
	let diasSemana = $state<string[]>([]);
	let icono = $state('');
	let color = $state('');
	let saving = $state(false);

	const EMOJIS = ['✅','🚀','💡','🔬','🔁','🏋️','📚','💻','📞','🛒','✈️','💰','🩺','🎨','✍️','🎵','🍳','🎓','📧','🏠','⭐','🔥','🎯','📌'];

	let esHabito = $derived(etiqueta === 'habito');

	$effect(() => {
		if (tarea) {
			titulo = tarea.titulo;
			descripcion = tarea.descripcion || '';
			prioridad = tarea.prioridad;
			etiqueta = tarea.etiqueta;
			repetible = tarea.repetible;
			fechaLimite = tarea.fecha_limite || '';
			horas = tarea.horas || [];
			diasSemana = tarea.dias_semana || [];
			icono = tarea.icono || '';
			color = tarea.color || '';
		}
	});

	function toggleDia(dia: string) {
		diasSemana = diasSemana.includes(dia) ? diasSemana.filter((d) => d !== dia) : [...diasSemana, dia];
	}

	function addHora() {
		if (nuevaHora && !horas.includes(nuevaHora)) {
			horas = [...horas, nuevaHora].sort();
			nuevaHora = '';
		}
	}

	function removeHora(h: string) {
		horas = horas.filter((x) => x !== h);
	}

	async function guardar() {
		if (!tarea || !titulo.trim()) return;
		saving = true;
		try {
			const t = await api.actualizarTarea(tarea.id, {
				titulo,
				descripcion,
				prioridad,
				etiqueta,
				repetible: esHabito ? true : repetible,
				fecha_limite: fechaLimite || null,
				horas: esHabito ? horas : [],
				dias_semana: esHabito ? diasSemana : [],
				icono,
				color
			});
			onTaskChange(t);
			modalStore.closeEdit();
		} catch (e) {
			console.error(e);
		} finally {
			saving = false;
		}
	}

	async function eliminar() {
		if (!tarea || !confirm('¿Eliminar esta tarea?')) return;
		try {
			await api.eliminarTarea(tarea.id);
			onTaskChange(null, tarea.id);
			modalStore.closeEdit();
		} catch (e) {
			console.error(e);
		}
	}
</script>

{#if tarea}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fade-in p-4" onclick={modalStore.closeEdit}>
		<div class="bg-card border border-border rounded-2xl p-5 w-full max-w-lg max-h-[90vh] overflow-y-auto animate-slide-up" onclick={(e) => e.stopPropagation()}>
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-base font-semibold">Editar tarea</h3>
				<button onclick={modalStore.closeEdit} class="text-muted hover:text-text">
					<X size={20} />
				</button>
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Título</label>
				<input class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text" bind:value={titulo} />
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Descripción</label>
				<textarea class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text resize-none" rows={3} bind:value={descripcion}></textarea>
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Apariencia (emoji y color)</label>
				<div class="flex items-center gap-2 mb-2">
					<input class="w-14 bg-bg border border-border rounded-xl px-2 py-2 text-center text-lg" maxlength="2" bind:value={icono} placeholder="🙂" />
					<input type="color" class="w-9 h-9 rounded cursor-pointer bg-transparent border border-border p-0" value={color || '#667eea'} oninput={(ev) => (color = ev.currentTarget.value)} />
					{#if color}<button class="text-[11px] text-muted hover:text-text" onclick={() => (color = '')}>Quitar color</button>{/if}
				</div>
				<div class="flex flex-wrap gap-1">
					{#each EMOJIS as em}
						<button onclick={() => (icono = em)} class="w-8 h-8 rounded-lg text-base hover:bg-card2 border {icono === em ? 'border-accent' : 'border-transparent'}">{em}</button>
					{/each}
				</div>
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Fecha límite</label>
				<input type="date" class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text [color-scheme:dark]" bind:value={fechaLimite} />
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Tipo</label>
				<div class="flex gap-2 flex-wrap">
					{#each TIPOS as { key, label, icon: Icon, color }}
						<button
							onclick={() => (etiqueta = key)}
							class="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-all {etiqueta === key
								? `bg-${color}-500/20 border-${color}-500/50 text-${color}-300`
								: 'bg-bg border-border text-muted hover:text-text'}"
						>
							<Icon size={14} />
							{label}
						</button>
					{/each}
				</div>
			</div>

			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Prioridad</label>
				<div class="flex gap-2">
					{#each PRIORIDADES as { key, label, color }}
						<button
							onclick={() => (prioridad = key as Tarea['prioridad'])}
							class="px-4 py-2 rounded-xl text-xs font-semibold border transition-all {prioridad === key
								? `bg-${color}-500/20 border-${color}-500/50 text-${color}-300`
								: 'bg-bg border-border text-muted hover:text-text'}"
						>
							{label}
						</button>
					{/each}
				</div>
			</div>

			{#if esHabito}
				<div class="mb-3 bg-pink-500/5 border border-pink-500/20 rounded-xl p-3">
					<div class="flex items-center gap-2 mb-3">
						<Repeat size={14} class="text-pink-300" />
						<span class="text-xs font-semibold text-pink-300">Configuración de hábito</span>
					</div>
					<label class="text-xs text-muted mb-1.5 block">Días a repetir</label>
					<div class="flex gap-1.5 mb-3">
						{#each DIAS as { key, label }}
							<button
								onclick={() => toggleDia(key)}
								class="w-8 h-8 rounded-lg text-xs font-bold border transition-all {diasSemana.includes(key)
									? 'bg-pink-500/30 border-pink-500/50 text-pink-200'
									: 'bg-bg border-border text-muted hover:text-text'}"
							>
								{label}
							</button>
						{/each}
					</div>
					<label class="text-xs text-muted mb-1.5 block flex items-center gap-1">
						<Clock size={12} /> Horas de recordatorio
					</label>
					<div class="flex gap-2 mb-2">
						<input type="time" class="bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text [color-scheme:dark]" bind:value={nuevaHora} />
						<button class="bg-pink-500/20 border border-pink-500/30 text-pink-300 rounded-lg px-3 text-sm hover:bg-pink-500/30 transition-colors" onclick={addHora}>
							<Plus size={16} />
						</button>
					</div>
					{#if horas.length > 0}
						<div class="flex gap-1.5 flex-wrap">
							{#each horas as h}
								<span class="flex items-center gap-1 bg-pink-500/15 text-pink-300 text-xs px-2 py-1 rounded-full">
									<Clock size={10} />
									{h}
									<button onclick={() => removeHora(h)} class="hover:text-red transition-colors">
										<X size={12} />
									</button>
								</span>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			{#if !esHabito}
				<div class="flex items-center justify-between mb-4">
					<label class="flex items-center gap-2 text-sm text-muted cursor-pointer">
						<input type="checkbox" class="w-4 h-4 accent-accent" bind:checked={repetible} />
						<Repeat size={14} />
						Tarea repetible diaria
					</label>
				</div>
			{/if}

			<div class="flex items-center justify-between gap-3 pt-2 border-t border-border">
				<button class="flex items-center gap-1.5 text-red text-sm font-medium hover:opacity-80 transition-opacity" onclick={eliminar}>
					<Trash2 size={16} />
					Eliminar
				</button>
				<div class="flex gap-2">
					<button class="px-4 py-2 rounded-xl border border-border text-muted hover:text-text transition-colors" onclick={modalStore.closeEdit}>Cancelar</button>
					<button class="px-4 py-2 rounded-xl bg-accent text-white font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5" onclick={guardar}>
						<Save size={16} />
						{saving ? 'Guardando...' : 'Guardar'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
