<script lang="ts">
	import { ChevronLeft, ChevronRight } from 'lucide-svelte';
	import { tareasStore, onTaskChange } from '../stores';
	import { api } from '../api';
	import TaskCard from './TaskCard.svelte';
	import type { Tarea } from '../types';

	const DIAS_SEMANA = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
	const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

	function hoyISO() {
		return new Date().toISOString().slice(0, 10);
	}

	function getTareasDeFecha(tareas: Tarea[], fecha: string): Tarea[] {
		return tareas.filter((t) => t.fecha_limite === fecha || t.creada_en.slice(0, 10) === fecha || (t.estado === 'completada' && t.completada_en?.slice(0, 10) === fecha));
	}

	let currentMonth = $state(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
	let selectedDate = $state(hoyISO());
	let hoy = $state(hoyISO());
	let dragTaskId = $state<string | null>(null);
	let dragOverFecha = $state<string | null>(null);

	let diasGrid = $derived.by(() => {
		const year = currentMonth.getFullYear();
		const month = currentMonth.getMonth();
		const primerDia = new Date(year, month, 1);
		const ultimoDia = new Date(year, month + 1, 0);
		let primerDiaSemana = primerDia.getDay() - 1;
		if (primerDiaSemana < 0) primerDiaSemana = 6;
		const dias: (string | null)[] = [];
		for (let i = 0; i < primerDiaSemana; i++) dias.push(null);
		for (let d = 1; d <= ultimoDia.getDate(); d++) {
			const fecha = new Date(year, month, d).toISOString().slice(0, 10);
			dias.push(fecha);
		}
		return dias;
	});

	let tareasSeleccionadas = $derived(getTareasDeFecha($tareasStore, selectedDate));

	function mesAnterior() {
		currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
	}
	function mesSiguiente() {
		currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
	}
	function irHoy() {
		const now = new Date();
		currentMonth = new Date(now.getFullYear(), now.getMonth(), 1);
		selectedDate = hoy;
	}

	function onDragStart(e: DragEvent, id: string) {
		dragTaskId = id;
		if (e.dataTransfer) {
			e.dataTransfer.setData('text/plain', id);
			e.dataTransfer.effectAllowed = 'move';
		}
	}

	async function reprogramar(id: string, fecha: string) {
		const prev = $tareasStore.find((t) => t.id === id);
		if (!prev || prev.fecha_limite === fecha) return;
		onTaskChange({ ...prev, fecha_limite: fecha });
		try {
			const t = await api.actualizarTarea(id, { fecha_limite: fecha });
			onTaskChange(t);
		} catch (err) {
			console.error(err);
			onTaskChange(prev);
		}
	}

	function onDropFecha(e: DragEvent, fecha: string) {
		e.preventDefault();
		const id = dragTaskId || e.dataTransfer?.getData('text/plain') || '';
		dragOverFecha = null;
		dragTaskId = null;
		if (id) reprogramar(id, fecha);
	}
</script>

<div class="max-w-5xl mx-auto">
	<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
		<div class="flex items-center gap-3">
			<h3 class="text-lg font-semibold">{MESES[currentMonth.getMonth()]} {currentMonth.getFullYear()}</h3>
			<div class="flex items-center gap-1">
				<button class="p-1.5 rounded-lg text-muted hover:text-text hover:bg-card2 transition-colors" onclick={mesAnterior}>
					<ChevronLeft size={20} />
				</button>
				<button class="p-1.5 rounded-lg text-muted hover:text-text hover:bg-card2 transition-colors" onclick={mesSiguiente}>
					<ChevronRight size={20} />
				</button>
			</div>
		</div>
		<button class="text-sm text-accent font-medium hover:opacity-80 transition-opacity" onclick={irHoy}>Hoy</button>
	</div>

	<div class="grid grid-cols-7 gap-1 mb-1">
		{#each DIAS_SEMANA as d}
			<div class="text-center text-xs font-medium text-muted py-1">{d}</div>
		{/each}
	</div>

	<div class="grid grid-cols-7 gap-1">
		{#each diasGrid as fecha}
			{#if fecha}
				{@const tareasDia = getTareasDeFecha($tareasStore, fecha)}
				<button
					class="min-h-[56px] sm:min-h-[80px] p-1.5 rounded-xl border bg-card text-left transition-colors hover:bg-card2 {selectedDate === fecha ? 'ring-1 ring-accent' : ''} {fecha === hoy ? 'bg-accent/5' : ''} {dragOverFecha === fecha ? 'border-accent ring-2 ring-accent/50' : 'border-border'}"
					onclick={() => (selectedDate = fecha)}
					ondragover={(e) => { e.preventDefault(); dragOverFecha = fecha; }}
					ondragleave={() => { if (dragOverFecha === fecha) dragOverFecha = null; }}
					ondrop={(e) => onDropFecha(e, fecha)}
				>
					<div class="text-xs font-medium mb-1 {fecha === hoy ? 'text-accent' : 'text-muted'}">{Number(fecha.slice(8, 10))}</div>
					<div class="space-y-0.5">
						{#each tareasDia.slice(0, 3) as t}
							<div class="h-1.5 rounded-full {t.prioridad === 'alta' ? 'bg-red-500' : t.prioridad === 'media' ? 'bg-amber-500' : 'bg-green-500'}" title={t.titulo}></div>
						{/each}
					</div>
				</button>
			{:else}
				<div class="min-h-[56px] sm:min-h-[80px]"></div>
			{/if}
		{/each}
	</div>

	<div class="mt-4">
		<h4 class="text-sm font-semibold mb-2">
			Tareas para {selectedDate} ({tareasSeleccionadas.length})
		</h4>
		{#if tareasSeleccionadas.length === 0}
			<div class="text-center text-muted py-8 text-sm">No hay tareas para este día</div>
		{:else}
			<p class="text-[11px] text-muted mb-2">Arrastra una tarea a un día del calendario para reprogramar su fecha límite.</p>
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
				{#each tareasSeleccionadas as t}
					<div draggable="true" ondragstart={(e) => onDragStart(e, t.id)} class="cursor-grab active:cursor-grabbing">
						<TaskCard tarea={t} />
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
