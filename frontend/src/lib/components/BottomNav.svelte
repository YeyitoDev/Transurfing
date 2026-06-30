<script lang="ts">
	import { page } from '$app/stores';
	import { ListTodo, CheckCircle2, Bell, Columns3, Calendar, Mic, Bot, Github } from 'lucide-svelte';

	const TABS = [
		{ href: '/', label: 'Pendientes', icon: ListTodo },
		{ href: '/completadas', label: 'Completadas', icon: CheckCircle2 },
		{ href: '/calendario', label: 'Calendario', icon: Calendar },
		{ href: '/alarmas', label: 'Alarmas', icon: Bell },
		{ href: '/kanban', label: 'Kanban', icon: Columns3 },
		{ href: '/voz', label: 'Voz', icon: Mic },
		{ href: '/agentes', label: 'Agentes', icon: Bot },
		{ href: '/github', label: 'GitHub', icon: Github }
	] as const;
</script>

<nav class="fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border safe-bottom">
	<div class="flex items-center justify-around max-w-3xl mx-auto h-16 overflow-x-auto no-scrollbar px-2">
		{#each TABS as { href, label, icon: Icon }}
			{@const active = $page.url.pathname === href}
			<a
				{href}
				class="flex flex-col items-center gap-1 px-2 py-2 rounded-xl transition-colors min-w-[52px] {active ? 'text-accent' : 'text-muted'}"
			>
				<Icon size={22} strokeWidth={active ? 2.5 : 2} />
				<span class="text-[10px] font-medium whitespace-nowrap">{label}</span>
			</a>
		{/each}
	</div>
</nav>
