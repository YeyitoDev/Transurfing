<script lang="ts">
	import { Plus, Repeat, Rocket, CheckSquare, Heart, ChevronDown, Search, Clock, X, Lightbulb } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
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

	const TEMPLATES: Record<string, string[]> = {
		emprendimiento: [
			'Empatizar: entender al cliente y su problema',
			'Definir: perfil de usuario y problem statement',
			'Idear: propuesta de valor y posibles soluciones',
			'Prototipar: MVP o prueba rápida de concepto',
			'Testear: validar con usuarios reales',
			'Modelo de negocio: costos, ingresos y canales',
			'Plan de acción: próximos pasos concretos'
		],
		investigacion: [
			'Definir la pregunta de investigación',
			'Buscar fuentes y referencias clave',
			'Sintetizar información relevante',
			'Extraer conclusiones y aprendizajes',
			'Documentar resultados'
		],
		tarea: [
			'Definir el alcance y criterios de éxito',
			'Planificar pasos y recursos necesarios',
			'Ejecutar el trabajo principal',
			'Revisar y ajustar'
		],
		idea: [
			'Describir la idea en una frase',
			'Listar supuestos clave',
			'Evaluar viabilidad y riesgos',
			'Definir siguiente paso para validar'
		],
		habito: []
	};

	let titulo = $state('');
	let descripcion = $state('');
	let prioridad = $state('media');
	let etiqueta = $state('tarea');
	let objetivo = $state('');
	let repetible = $state(false);
	let expandido = $state(false);
	let horas = $state<string[]>([]);
	let nuevaHora = $state('');
	let diasSemana = $state<string[]>([]);
	let vozError = $state<string | null>(null);

	let esHabito = $derived(etiqueta === 'habito');
	let templatePreview = $derived(TEMPLATES[etiqueta] || []);
	let tieneTemplate = $derived(templatePreview.length > 0);

	function resetFormulario() {
		titulo = '';
		descripcion = '';
		prioridad = 'media';
		etiqueta = 'tarea';
		objetivo = '';
		repetible = false;
		horas = [];
		diasSemana = [];
		expandido = false;
	}

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

	async function crear() {
		if (!titulo.trim()) return;
		const finalRepetible = esHabito ? true : repetible;
		const finalHoras = esHabito ? horas : [];
		const finalDias = esHabito ? diasSemana : [];
		try {
			const t = await api.crearTarea({
				titulo,
				descripcion,
				prioridad,
				fecha_limite: null,
				etiqueta,
				repetible: finalRepetible,
				horas: finalHoras,
				dias_semana: finalDias,
				objetivo: objetivo.trim()
			});
			onTaskChange(t);
			resetFormulario();
		} catch (e) {
			console.error(e);
		}
	}

	async function procesarVoz(texto: string) {
		try {
			vozError = null;
			const res = await api.vozProcesar(texto);
			if (res.tarea_creada) {
				onTaskChange(res.tarea_creada);
				resetFormulario();
			} else if (res.accion === 'agregar_subtarea' && res.tarea_numero && res.subtarea_titulo) {
				const t = await api.agregarSubtareaPorNumero(res.tarea_numero, res.subtarea_titulo);
				onTaskChange(t);
				vozError = `✅ Subtarea añadida a la tarea #${res.tarea_numero}`;
			} else if (res.draft) {
				const confirm = await api.vozConfirmar(res.draft);
				if (confirm.tarea_creada) {
					onTaskChange(confirm.tarea_creada);
					resetFormulario();
				}
			} else if (res.mensaje) {
				vozError = res.mensaje;
			}
		} catch (e) {
			console.error(e);
			vozError = 'No pude entender el mensaje de voz. Intenta de nuevo.';
		}
	}

	async function onVoice() {
		const texto = prompt('Introduce el texto de voz para procesar:');
		if (texto) await procesarVoz(texto);
	}
</script>

<div class="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-lg">
	<div class="relative mb-3">
		<input
			class="w-full bg-bg border border-border rounded-xl pl-4 pr-12 py-3.5 text-base text-text placeholder-muted"
			placeholder="¿Qué necesitas hacer?"
			bind:value={titulo}
			onkeydown={(e) => e.key === 'Enter' && crear()}
			onfocus={() => (expandido = true)}
		/>
		<button
			onclick={onVoice}
			class="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all bg-card border border-border text-muted hover:text-accent"
			title="Hablar para crear tarea (simulado)"
		>
			<X size={18} /> ⚠️
		</button>
	</div>

	{#if vozError}
		<div class="mb-3 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 flex items-start gap-2">
			<span class="mt-0.5">⚠️</span>
			<span>{vozError}</span>
		</div>
	{/if}

	{#if expandido}
		<textarea
			class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted mb-3 resize-none"
			placeholder="Descripción (opcional)..."
			rows={2}
			bind:value={descripcion}
		></textarea>

		<input
			class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted mb-3"
			placeholder="Objetivo / área / proyecto (opcional)..."
			bind:value={objetivo}
		/>

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
			{#if tieneTemplate}
				<div class="mt-2 p-2 rounded-xl bg-bg border border-border">
					<div class="text-[10px] text-muted mb-1.5">Subtareas que se crearán automáticamente:</div>
					<ul class="space-y-1">
						{#each templatePreview as item}
							<li class="text-xs text-muted flex items-start gap-1.5">
								<span class="text-accent mt-0.5">•</span>
								{item}
							</li>
						{/each}
					</ul>
				</div>
			{:else if esHabito}
				<div class="mt-2 text-[10px] text-pink-300">Solo se creará un hábito con seguimiento de racha y estadísticas.</div>
			{/if}
		</div>

		<div class="mb-3">
			<label class="text-xs text-muted font-medium mb-1.5 block">Prioridad</label>
			<div class="flex gap-2">
				{#each PRIORIDADES as { key, label, color }}
					<button
						onclick={() => (prioridad = key)}
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
					<button
						class="bg-pink-500/20 border border-pink-500/30 text-pink-300 rounded-lg px-3 text-sm hover:bg-pink-500/30 transition-colors"
						onclick={addHora}
					>
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
			<div class="flex items-center justify-between mb-3">
				<label class="flex items-center gap-2 text-sm text-muted cursor-pointer">
					<input type="checkbox" class="w-4 h-4 accent-accent" bind:checked={repetible} />
					<Repeat size={14} />
					Tarea repetible diaria
				</label>
			</div>
		{/if}
	{/if}

	<div class="flex items-center justify-between gap-2">
		{#if expandido}
			<button class="text-xs text-muted hover:text-text transition-colors" onclick={() => (expandido = false)}>
				<ChevronDown size={16} class="inline" /> Menos
			</button>
		{/if}
		<button class="ml-auto bg-accent text-white rounded-xl px-5 py-2.5 text-sm font-semibold hover:opacity-90 transition-opacity flex items-center gap-1.5" onclick={crear}>
			<Plus size={18} />
			Crear tarea
		</button>
	</div>
</div>
