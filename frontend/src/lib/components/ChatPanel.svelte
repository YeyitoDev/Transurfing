<script lang="ts">
	import { Send, Plus, MessageSquare, Sparkles, Loader2, CheckSquare, Paperclip, X, Bot } from 'lucide-svelte';
	import type { Tarea, ModeloAgente, ChatAdjunto } from '../types';
	import { api } from '../api';
	import { onTaskChange } from '../stores';

	let { tarea }: { tarea: Tarea } = $props();

	let activeId = $state('');
	let input = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);
	let initialized = $state(false);
	let modelos = $state<ModeloAgente[]>([]);
	let modelo = $state('');
	let adjuntos = $state<ChatAdjunto[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);

	let sesiones = $derived(tarea.chat_sesiones || []);
	let activeSession = $derived(sesiones.find((s) => s.id === activeId) || sesiones[0]);

	$effect(() => {
		if (!initialized) {
			activeId = sesiones[0]?.id || '';
			initialized = true;
		} else if (sesiones.length > 0 && !sesiones.some((s) => s.id === activeId)) {
			activeId = sesiones[sesiones.length - 1]?.id || '';
		}
	});

	async function loadModelos() {
		try {
			const res = await api.listarModelos();
			modelos = res.modelos;
			modelo = modelo || res.default;
		} catch (e) {
			console.error(e);
		}
	}
	loadModelos();

	async function createSession() {
		loading = true;
		try {
			const res = await api.crearChatSesion(tarea.id, `Sesión ${sesiones.length + 1}`);
			onTaskChange(res.tarea);
			const newId = res.tarea.chat_sesiones[res.tarea.chat_sesiones.length - 1]?.id || '';
			activeId = newId;
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

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

	async function sendMessage() {
		if (!input.trim() || !activeSession) return;
		const text = input.trim();
		input = '';
		loading = true;
		error = null;
		try {
			const res = await api.enviarChatMensaje(tarea.id, activeSession.id, text, {
				modelo: modelo || undefined,
				archivos: adjuntos.length > 0 ? adjuntos : undefined
			});
			onTaskChange(res.tarea);
			adjuntos = [];
		} catch (e: any) {
			console.error(e);
			error = e?.message || 'No se pudo enviar el mensaje.';
		} finally {
			loading = false;
		}
	}

	function acceptSubtasks() {
		onTaskChange(tarea);
	}
</script>

<div class="bg-card2 border border-border rounded-2xl overflow-hidden flex flex-col h-[420px] max-h-[420px]">
	<div class="flex items-center justify-between px-4 py-3 border-b border-border">
		<div class="flex items-center gap-2">
			<MessageSquare size={16} class="text-accent" />
			<span class="text-sm font-semibold text-text">Chat del agente</span>
		</div>
		<button
			onclick={createSession}
			disabled={loading}
			class="flex items-center gap-1 text-[10px] font-medium bg-accent text-white rounded-lg px-2.5 py-1.5 disabled:opacity-50"
		>
			<Plus size={10} /> Nueva sesión
		</button>
	</div>

	<div class="flex items-center gap-2 px-4 py-2 border-b border-border overflow-x-auto">
		{#if sesiones.length === 0}
			<span class="text-[10px] text-muted">No hay sesiones. Crea una para empezar.</span>
		{:else}
			{#each sesiones as s}
				<button
					onclick={() => (activeId = s.id)}
					class="text-[10px] font-medium px-2.5 py-1 rounded-lg whitespace-nowrap border transition-colors {activeId === s.id
						? 'bg-accent text-white border-accent'
						: 'bg-card border-border text-muted hover:text-text'}"
				>
					{s.nombre}
				</button>
			{/each}
		{/if}
	</div>

	<div class="flex items-center gap-2 px-4 py-2 border-b border-border">
		<Bot size={14} class="text-muted" />
		<select
			class="flex-1 bg-bg border border-border rounded-lg px-2 py-1 text-xs text-text"
			bind:value={modelo}
			disabled={!activeSession || loading}
		>
			{#each modelos as m}
				<option value={m.id}>{m.nombre} — {m.descripcion}</option>
			{/each}
			{#if modelos.length === 0}
				<option value="">Modelo por defecto</option>
			{/if}
		</select>
	</div>

	<div class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
		{#if activeSession}
			{#each activeSession.mensajes as m (m.id)}
				<div class="flex {m.rol === 'user' ? 'justify-end' : 'justify-start'}">
					<div
						class="max-w-[85%] text-xs rounded-xl px-3 py-2 leading-relaxed {m.rol === 'user'
							? 'bg-accent text-white'
							: 'bg-card border border-border text-text'}"
					>
						{m.texto}
					</div>
				</div>
			{/each}
		{:else}
			<div class="text-center text-[11px] text-muted py-8">
				Crea una sesión para conversar con el agente sobre esta tarea.
			</div>
		{/if}
		{#if loading}
			<div class="flex justify-start">
				<div class="bg-card border border-border rounded-xl px-3 py-2 flex items-center gap-2">
					<Loader2 size={12} class="animate-spin text-accent" />
					<span class="text-[10px] text-muted">Jarvis está escribiendo...</span>
				</div>
			</div>
		{/if}
	</div>

	<div class="px-4 py-3 border-t border-border">
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
			<div class="mb-2 text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
				{error}
			</div>
		{/if}
		<div class="flex items-center gap-2">
			<input
				class="flex-1 bg-bg border border-border rounded-xl px-3 py-2 text-xs text-text placeholder-muted"
				placeholder="Pide ayuda para generar subtareas..."
				bind:value={input}
				onkeydown={(e) => e.key === 'Enter' && sendMessage()}
				disabled={!activeSession || loading}
			/>
			<input
				type="file"
				multiple
				class="hidden"
				bind:this={fileInput}
				onchange={handleFiles}
			/>
			<button
				onclick={() => fileInput?.click()}
				disabled={!activeSession || loading}
				class="p-2 text-muted hover:text-text bg-bg border border-border rounded-xl disabled:opacity-50"
				title="Adjuntar archivos"
			>
				<Paperclip size={14} />
			</button>
			<button
				onclick={sendMessage}
				disabled={!activeSession || loading || !input.trim()}
				class="bg-accent text-white rounded-xl px-3 py-2 disabled:opacity-50"
			>
				{#if loading}<Loader2 size={14} class="animate-spin" />{:else}<Send size={14} />{/if}
			</button>
		</div>
		<div class="flex items-center gap-3 mt-2">
			<div class="flex items-center gap-1 text-[10px] text-accent">
				<Sparkles size={10} />
				{tarea.proxima_alta_valor || 'Sin acción prioritaria definida aún'}
			</div>
			<button onclick={acceptSubtasks} class="ml-auto text-[10px] text-muted hover:text-text flex items-center gap-1">
				<CheckSquare size={10} /> Subtareas actualizadas
			</button>
		</div>
	</div>
</div>
