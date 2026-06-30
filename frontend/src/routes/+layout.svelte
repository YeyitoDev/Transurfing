<script lang="ts">
	import { page } from '$app/stores';
	import { Bell, Settings, Bot, Github, FileText } from 'lucide-svelte';
	import { useSync } from '../lib/hooks/useSync';
	import { useTheme } from '../lib/hooks/useTheme';
	import { requestPermission } from '../lib/hooks/useNotifications';
	import { tareasStore, recordatoriosStore, loadingStore, notifEnabledStore } from '../lib/stores';
	import BottomNav from '../lib/components/BottomNav.svelte';
	import FilterBar from '../lib/components/FilterBar.svelte';
	import TaskEditModal from '../lib/components/TaskEditModal.svelte';
	import TaskDetailModal from '../lib/components/TaskDetailModal.svelte';
	import ReminderModal from '../lib/components/ReminderModal.svelte';
	import ThemeSettings from '../lib/components/ThemeSettings.svelte';
	import VoiceBot from '../lib/components/VoiceBot.svelte';
	import GlobalChat from '../lib/components/GlobalChat.svelte';
	import { modalStore } from '../lib/components/modalStore';
	import type { EtiquetaKey } from '../lib/types';
	import '../app.css';

	let { children } = $props();
	useSync();
	useTheme();

	let showTheme = $state(false);
	let filtro = $state<EtiquetaKey>('todas');
	let notifEnabled = $derived($notifEnabledStore);
	let pendientesCount = $derived($tareasStore.filter((t) => t.estado !== 'completada').length);
	let completadasCount = $derived($tareasStore.filter((t) => t.estado === 'completada').length);
	let proximas = $derived($tareasStore.filter((t) => t.estado !== 'completada' && t.fecha_limite && t.fecha_limite <= new Date().toISOString().slice(0, 10)));
	let isHome = $derived($page.url.pathname === '/');
</script>

<div class="min-h-screen bg-bg text-text pb-20">
	<div class="max-w-5xl mx-auto px-4 sm:px-6">
		<header class="text-center pt-8 pb-4 relative">
			<div class="absolute right-0 top-8 flex items-center gap-1">
				<a href="/changelog" class="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors" aria-label="Changelog y QA">
					<FileText size={20} />
				</a>
				<a href="/github" class="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors" aria-label="Configuración GitHub">
					<Github size={20} />
				</a>
				<a href="/agentes" class="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors" aria-label="Agentes especializados">
					<Bot size={20} />
				</a>
				<button onclick={() => (showTheme = true)} class="p-2 rounded-xl text-muted hover:text-accent hover:bg-card2 transition-colors" aria-label="Personalizar colores">
					<Settings size={20} />
				</button>
			</div>
			<h1 class="text-2xl font-bold">Mis Tareas</h1>
			<p class="text-sm text-muted mt-1.5">
				{pendientesCount} pendientes · {completadasCount} completadas · {$recordatoriosStore.length} alarmas
				{#if proximas.length > 0}
					<span class="ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 animate-pulse">{proximas.length} próximas</span>
				{/if}
			</p>
		</header>

		{#if !notifEnabled}
			<div class="mb-4 bg-card2 border border-border rounded-xl px-4 py-3 flex items-center justify-between text-sm text-muted max-w-2xl mx-auto">
				<span class="flex items-center gap-2">
					<Bell size={16} />
					Activa notificaciones para recordatorios
				</span>
				<button class="bg-accent text-white rounded-lg px-3 py-1.5 text-xs font-medium" onclick={requestPermission}>Activar</button>
			</div>
		{/if}

		{#if isHome}
			<div class="mb-4 max-w-2xl mx-auto">
				<GlobalChat />
			</div>
			<div class="mb-3 max-w-2xl mx-auto">
				<FilterBar bind:value={filtro} />
			</div>
		{/if}

		<main>
			{#if $loadingStore}
				<div class="text-center text-muted py-16">Cargando...</div>
			{:else}
				{@render children()}
			{/if}
		</main>
	</div>

	<VoiceBot />
	<BottomNav />
	<TaskDetailModal />
	<TaskEditModal />
	<ReminderModal />

	{#if showTheme}
		<ThemeSettings onClose={() => (showTheme = false)} />
	{/if}
</div>
