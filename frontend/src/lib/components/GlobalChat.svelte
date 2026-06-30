<script lang="ts">
	import { Send, Loader2, Trash2, Bot, Paperclip, X, Sparkles, CheckCircle2, AlertCircle, RefreshCw, Edit3, ListPlus, Trash, GitCommit, Terminal, Play, CalendarClock } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange, onRecordatorioChange } from '../stores';
	import type { ChatGlobalMessage, ModeloAgente, ChatAdjunto, Recordatorio } from '../types';

	let input = $state('');
	let loading = $state(false);
	let historial = $state<ChatGlobalMessage[]>([]);
	let error = $state('');
	let modelos = $state<ModeloAgente[]>([]);
	let modelo = $state('');
	let adjuntos = $state<ChatAdjunto[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);
	let scrollContainer: HTMLDivElement | null = $state(null);

	let sugerenciasIniciales = [
		'Crear una tarea alta',
		'Crear un hábito para meditar',
		'Crear idea de app',
		'Crear proyecto de investigación'
	];

	async function cargarHistorial() {
		try {
			const [res, modRes] = await Promise.all([api.chatGlobalHistorial(), api.listarModelos()]);
			historial = res.historial;
			modelos = modRes.modelos;
			modelo = modelo || modRes.default;
		} catch (e) {
			console.error(e);
		}
	}
	cargarHistorial();

	function scrollToBottom() {
		if (scrollContainer) {
			scrollContainer.scrollTop = scrollContainer.scrollHeight;
		}
	}

	$effect(() => {
		if (historial.length > 0) {
			scrollToBottom();
		}
	});

	async function handleFiles(e: Event) {
		const target = e.target as HTMLInputElement;
		const files = target.files;
		if (!files) return;
		for (const file of Array.from(files)) {
			const texto = await file.text();
			adjuntos = [...adjuntos, { nombre: file.name, tipo: file.type || 'text/plain', contenido: texto }];
		}
		if (fileInput) fileInput.value = '';
	}

	function removeAdjunto(idx: number) {
		adjuntos = adjuntos.filter((_, i) => i !== idx);
	}

	async function enviar(textoOverride = '') {
		const texto = textoOverride || input.trim();
		if (!texto || loading) return;
		input = '';
		historial = [...historial, { role: 'user', content: texto }];
		loading = true;
		error = '';
		try {
			const res = await api.chatGlobal(texto, {
				modelo: modelo || undefined,
				archivos: adjuntos.length > 0 ? adjuntos : undefined
			});
			adjuntos = [];
			historial = [
				...historial,
				{
					role: 'assistant',
					content: res.mensaje,
					accion: res.accion,
					opciones: res.opciones
				}
			];
			if (res.accion === 'eliminar_tarea') {
				if (res.tarea_numero) {
					const tarea = res.tarea || { id: '' };
					onTaskChange(null, tarea.id);
				}
			} else if (res.tarea) {
				onTaskChange(res.tarea);
			}
			if (res.accion === 'eliminar_recordatorio') {
				if (res.recordatorio) {
					onRecordatorioChange(null, res.recordatorio.id);
				}
			} else if (res.recordatorio) {
				onRecordatorioChange(res.recordatorio as Recordatorio);
			}
		} catch (e: any) {
			console.error(e);
			error = e?.message || 'Error enviando mensaje.';
		} finally {
			loading = false;
		}
	}

	async function limpiar() {
		if (!confirm('¿Borrar toda la conversación?')) return;
		try {
			await api.chatGlobalLimpiar();
			historial = [];
		} catch (e) {
			console.error(e);
		}
	}

	function iconoAccion(accion?: string) {
		if (accion === 'crear_tarea') return CheckCircle2;
		if (accion === 'actualizar_tarea') return Edit3;
		if (accion === 'agregar_subtareas') return ListPlus;
		if (accion === 'eliminar_tarea') return Trash;
		if (accion === 'ejecutar_subtarea') return Play;
		if (accion === 'commitear_subtarea') return GitCommit;
		if (accion === 'sincronizar_subtareas') return RefreshCw;
		if (accion === 'eliminar_subtarea') return Trash;
		if (accion === 'crear_recordatorio' || accion === 'actualizar_recordatorio' || accion === 'eliminar_recordatorio') return CalendarClock;
		if (accion === 'error') return AlertCircle;
		return Sparkles;
	}

	function colorAccion(accion?: string) {
		if (accion === 'crear_tarea') return 'text-green-400';
		if (accion === 'actualizar_tarea') return 'text-blue-400';
		if (accion === 'agregar_subtareas') return 'text-purple-400';
		if (accion === 'eliminar_tarea') return 'text-red-400';
		if (accion === 'ejecutar_subtarea') return 'text-indigo-400';
		if (accion === 'commitear_subtarea') return 'text-green-400';
		if (accion === 'sincronizar_subtareas') return 'text-amber-400';
		if (accion === 'eliminar_subtarea') return 'text-red-400';
		if (accion === 'crear_recordatorio') return 'text-pink-400';
		if (accion === 'actualizar_recordatorio') return 'text-blue-400';
		if (accion === 'eliminar_recordatorio') return 'text-red-400';
		if (accion === 'error') return 'text-red-400';
		return 'text-amber-400';
	}
</script>

<div class="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-lg flex flex-col h-[520px] max-h-[70vh]">
	<div class="flex items-center justify-between mb-3">
		<div class="flex items-center gap-2">
			<div class="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
				<Bot size={18} />
			</div>
			<div>
				<h3 class="text-sm font-semibold text-text">Jarvis</h3>
				<p class="text-[10px] text-muted">Asistente de productividad</p>
			</div>
		</div>
		<div class="flex items-center gap-2">
			<select
				class="bg-bg border border-border rounded-lg px-2 py-1 text-[10px] text-text"
				bind:value={modelo}
				disabled={loading}
			>
				{#each modelos as m}
					<option value={m.id}>{m.nombre}</option>
				{/each}
				{#if modelos.length === 0}
					<option value="">Modelo por defecto</option>
				{/if}
			</select>
			<button onclick={limpiar} class="p-1.5 text-muted hover:text-red-400" title="Limpiar conversación">
				<Trash2 size={14} />
			</button>
		</div>
	</div>

	<div bind:this={scrollContainer} class="flex-1 overflow-y-auto px-2 py-2 space-y-3 min-h-0">
		{#if historial.length === 0}
			<div class="text-center py-6">
				<div class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-indigo-500/10 text-indigo-400 mb-3">
					<Sparkles size={18} />
				</div>
				<p class="text-xs text-text font-medium mb-1">¿Qué necesitas hacer?</p>
				<p class="text-[11px] text-muted mb-3">Escribe una idea, tarea o card y te ayudaré a crearla y planificarla.</p>
				<div class="flex flex-wrap justify-center gap-1.5">
					{#each sugerenciasIniciales as s}
						<button
							onclick={() => enviar(s)}
							class="text-[10px] px-2.5 py-1.5 rounded-lg border border-border bg-bg text-muted hover:text-text hover:border-indigo-500/50 transition-colors"
						>
							{s}
						</button>
					{/each}
				</div>
			</div>
		{:else}
			{#each historial as m, i (m.content + i)}
				{@const Icon = iconoAccion(m.accion)}
				<div class="flex {m.role === 'user' ? 'justify-end' : 'justify-start'}">
					{#if m.role === 'assistant'}
						<div class="flex gap-2 max-w-[90%]">
							<div class="mt-1 shrink-0 {colorAccion(m.accion)}">
								<Icon size={14} />
							</div>
							<div class="w-full">
								<div class="text-xs rounded-xl px-3 py-2 leading-relaxed bg-card border border-border text-text">
									{m.content}
								</div>
								{#if m.accion && m.accion !== 'conversar'}
									<div class="mt-1 text-[9px] {colorAccion(m.accion)} font-medium">
										{m.accion === 'crear_tarea' && '✓ Tarea creada'}
										{m.accion === 'actualizar_tarea' && '✓ Tarea actualizada'}
										{m.accion === 'agregar_subtareas' && '✓ Subtareas añadidas'}
										{m.accion === 'eliminar_tarea' && '✓ Tarea eliminada'}
										{m.accion === 'ejecutar_subtarea' && '✓ Subtarea ejecutada'}
										{m.accion === 'commitear_subtarea' && '✓ Subido a GitHub'}
										{m.accion === 'sincronizar_subtareas' && '✓ Subtareas sincronizadas'}
										{m.accion === 'eliminar_subtarea' && '✓ Subtarea eliminada'}
										{m.accion === 'crear_recordatorio' && '✓ Recordatorio creado'}
										{m.accion === 'actualizar_recordatorio' && '✓ Recordatorio actualizado'}
										{m.accion === 'eliminar_recordatorio' && '✓ Recordatorio eliminado'}
										{m.accion === 'error' && '⚠ Error'}
									</div>
								{/if}
								{#if m.opciones && m.opciones.length > 0}
									<div class="flex flex-wrap gap-1.5 mt-2">
										{#each m.opciones as opt}
											<button
												onclick={() => enviar(opt)}
												class="text-[10px] px-2.5 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/20 transition-colors"
											>
												{opt}
											</button>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					{:else}
						<div class="max-w-[85%] text-xs rounded-xl px-3 py-2 leading-relaxed bg-indigo-500 text-white">
							{m.content}
							{#if adjuntos.length > 0 && i === historial.length - 1}
								<div class="mt-1 text-[9px] opacity-80">
									{adjuntos.length} archivo{adjuntos.length > 1 ? 's' : ''} adjunto
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/if}
		{#if loading}
			<div class="flex justify-start">
				<div class="bg-card border border-border rounded-xl px-3 py-2 flex items-center gap-2">
					<Loader2 size={12} class="animate-spin text-indigo-400" />
					<span class="text-[10px] text-muted">Jarvis está escribiendo...</span>
				</div>
			</div>
		{/if}
	</div>

	<div class="mt-3 pt-3 border-t border-border">
		{#if adjuntos.length > 0}
			<div class="flex flex-wrap gap-1.5 mb-2">
				{#each adjuntos as a, i}
					<div class="flex items-center gap-1 text-[10px] bg-bg border border-border rounded-lg px-2 py-1">
						<Paperclip size={10} />
						<span class="truncate max-w-[120px]">{a.nombre}</span>
						<button onclick={() => removeAdjunto(i)} class="text-muted hover:text-red"><X size={10} /></button>
					</div>
				{/each}
			</div>
		{/if}
		{#if error}
			<div class="mb-2 text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
		{/if}
		<div class="flex items-center gap-2">
			<input
				class="flex-1 bg-bg border border-border rounded-xl px-3 py-2.5 text-sm text-text placeholder-muted"
				placeholder="Escribe una idea, tarea o card..."
				bind:value={input}
				onkeydown={(e) => e.key === 'Enter' && enviar()}
				disabled={loading}
			/>
			<input type="file" multiple class="hidden" bind:this={fileInput} onchange={handleFiles} />
			<button
				onclick={() => fileInput?.click()}
				disabled={loading}
				class="p-2.5 text-muted hover:text-text bg-bg border border-border rounded-xl disabled:opacity-50"
				title="Adjuntar archivos"
			>
				<Paperclip size={16} />
			</button>
			<button
				onclick={() => enviar()}
				disabled={loading || !input.trim()}
				class="bg-indigo-500 text-white rounded-xl px-3 py-2.5 disabled:opacity-50"
			>
				{#if loading}<Loader2 size={16} class="animate-spin" />{:else}<Send size={16} />{/if}
			</button>
		</div>
		<div class="flex items-center gap-2 mt-2 text-[10px] text-muted">
			<RefreshCw size={10} />
			Puedes crear, actualizar, añadir subtareas o eliminar cards hablando con Jarvis.
		</div>
	</div>
</div>
