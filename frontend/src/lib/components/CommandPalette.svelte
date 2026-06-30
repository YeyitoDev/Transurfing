<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Search, Loader2, CornerDownLeft, Compass, ListChecks, Sparkles } from 'lucide-svelte';
	import { tareasStore } from '../stores';
	import { modalStore } from './modalStore';
	import { api } from '../api';
	import type { Tarea, MemoriaResultado } from '../types';

	let open = $state(false);
	let query = $state('');
	let semResults = $state<MemoriaResultado[]>([]);
	let semLoading = $state(false);
	let inputEl = $state<HTMLInputElement | null>(null);

	const NAV: { label: string; path: string; kw: string }[] = [
		{ label: 'Inicio · Tareas', path: '/', kw: 'home crear nueva tarea' },
		{ label: 'Completadas', path: '/completadas', kw: 'hechas terminadas' },
		{ label: 'Calendario', path: '/calendario', kw: 'fechas agenda' },
		{ label: 'Kanban', path: '/kanban', kw: 'tablero board' },
		{ label: 'Alarmas', path: '/alarmas', kw: 'recordatorios' },
		{ label: 'Agentes', path: '/agentes', kw: 'skills knowledge' },
		{ label: 'GitHub', path: '/github', kw: 'repos pr' },
		{ label: 'Changelog', path: '/changelog', kw: 'qa versiones' },
		{ label: 'Voz', path: '/voz', kw: 'microfono dictar' }
	];

	let tareas = $derived($tareasStore);
	let q = $derived(query.trim().toLowerCase());
	let navMatches = $derived(q ? NAV.filter((n) => (n.label + ' ' + n.kw).toLowerCase().includes(q)) : NAV);
	let taskMatches = $derived(
		q ? tareas.filter((t) => (t.titulo + ' ' + (t.descripcion || '')).toLowerCase().includes(q)).slice(0, 6) : []
	);

	function openPalette() {
		open = true;
		query = '';
		semResults = [];
		setTimeout(() => inputEl?.focus(), 30);
	}
	function closePalette() {
		open = false;
	}

	function onKey(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
			e.preventDefault();
			open ? closePalette() : openPalette();
		} else if (open && e.key === 'Escape') {
			closePalette();
		}
	}

	function go(path: string) {
		closePalette();
		goto(path);
	}
	function openTask(t: Tarea) {
		closePalette();
		modalStore.openDetail(t);
	}

	async function buscarSemantica() {
		if (!q) return;
		semLoading = true;
		try {
			const res = await api.buscarMemoria(query.trim(), 6);
			semResults = res.resultados;
		} catch (e) {
			console.error(e);
		} finally {
			semLoading = false;
		}
	}

	onMount(() => {
		const handler = () => openPalette();
		window.addEventListener('cmdk:open', handler);
		return () => window.removeEventListener('cmdk:open', handler);
	});
</script>

<svelte:window onkeydown={onKey} />

{#if open}
	<div
		class="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 backdrop-blur-sm pt-[12vh] px-4 animate-fade-in"
		role="button"
		tabindex="-1"
		onclick={closePalette}
	>
		<div
			class="w-full max-w-xl bg-card border border-border rounded-2xl shadow-2xl overflow-hidden animate-slide-up"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="flex items-center gap-2 px-4 py-3 border-b border-border">
				<Search size={16} class="text-muted" />
				<input
					bind:this={inputEl}
					bind:value={query}
					onkeydown={(e) => e.key === 'Enter' && buscarSemantica()}
					placeholder="Buscar o navegar…  (Enter = búsqueda semántica)"
					class="flex-1 bg-transparent text-sm text-text outline-none placeholder-muted"
				/>
				<kbd class="text-[10px] text-muted border border-border rounded px-1 py-0.5">Esc</kbd>
			</div>

			<div class="max-h-[60vh] overflow-y-auto p-2 space-y-3">
				{#if navMatches.length > 0}
					<div>
						<div class="px-2 py-1 text-[10px] uppercase tracking-wide text-muted flex items-center gap-1">
							<Compass size={11} /> Navegar
						</div>
						{#each navMatches as n}
							<button
								onclick={() => go(n.path)}
								class="w-full text-left px-3 py-2 rounded-lg text-sm text-text hover:bg-card2 flex items-center justify-between group"
							>
								<span>{n.label}</span>
								<CornerDownLeft size={13} class="text-muted opacity-0 group-hover:opacity-100" />
							</button>
						{/each}
					</div>
				{/if}

				{#if taskMatches.length > 0}
					<div>
						<div class="px-2 py-1 text-[10px] uppercase tracking-wide text-muted flex items-center gap-1">
							<ListChecks size={11} /> Tareas
						</div>
						{#each taskMatches as t}
							<button
								onclick={() => openTask(t)}
								class="w-full text-left px-3 py-2 rounded-lg text-sm text-text hover:bg-card2 flex items-center gap-2"
							>
								{#if t.icono}<span class="shrink-0">{t.icono}</span>{/if}
								<span class="truncate">{t.titulo}</span>
								<span class="ml-auto text-[10px] text-muted">#{t.numero}</span>
							</button>
						{/each}
					</div>
				{/if}

				<div>
					<div class="px-2 py-1 text-[10px] uppercase tracking-wide text-muted flex items-center gap-1">
						<Sparkles size={11} /> Búsqueda semántica
					</div>
					{#if semLoading}
						<div class="px-3 py-3 text-xs text-muted flex items-center gap-2">
							<Loader2 size={13} class="animate-spin" /> Buscando en tu memoria…
						</div>
					{:else if semResults.length > 0}
						{#each semResults as r}
							{@const tarea = r.source === 'tarea' && r.source_id ? tareas.find((t) => t.id === r.source_id) : null}
							{#if tarea}
								<button onclick={() => openTask(tarea)} class="w-full text-left px-3 py-2 rounded-lg hover:bg-card2 flex items-start gap-2">
									{#if tarea.icono}<span class="shrink-0">{tarea.icono}</span>{/if}
									<div class="min-w-0">
										<div class="text-xs text-text line-clamp-2">{r.text}</div>
										<div class="text-[10px] text-accent mt-0.5 truncate">Abrir tarea · {tarea.titulo}</div>
									</div>
								</button>
							{:else}
								<div class="px-3 py-2 rounded-lg hover:bg-card2">
									<div class="text-xs text-text line-clamp-2">{r.text}</div>
									<div class="text-[10px] text-muted mt-0.5">{r.source}</div>
								</div>
							{/if}
						{/each}
					{:else if q}
						<button onclick={buscarSemantica} class="w-full text-left px-3 py-2 rounded-lg text-xs text-accent hover:bg-card2">
							Buscar “{query}” en todo lo que escribí →
						</button>
					{:else}
						<div class="px-3 py-2 text-[11px] text-muted">Escribe y pulsa Enter para buscar por significado.</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
