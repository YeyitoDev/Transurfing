<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '../../lib/api';
	import { Sparkles, Loader2, RefreshCw, Newspaper, Lightbulb, Cpu, Wrench, BookOpen } from 'lucide-svelte';

	type FeedItem = { proyecto: string; tipo: string; titulo: string; resumen: string; sugerencia: string };

	let items = $state<FeedItem[]>([]);
	let loading = $state(false);
	let error = $state('');
	let generadoEn = $state('');

	const TIPO_META: Record<string, { label: string; icon: typeof Cpu; cls: string }> = {
		modelo: { label: 'Modelo', icon: Cpu, cls: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
		noticia: { label: 'Noticia', icon: Newspaper, cls: 'text-sky-400 bg-sky-500/10 border-sky-500/20' },
		inspiracion: { label: 'Inspiración', icon: Lightbulb, cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
		recurso: { label: 'Recurso', icon: BookOpen, cls: 'text-green-400 bg-green-500/10 border-green-500/20' },
		consejo: { label: 'Consejo', icon: Wrench, cls: 'text-pink-400 bg-pink-500/10 border-pink-500/20' }
	};
	function meta(tipo: string) {
		return TIPO_META[tipo] || TIPO_META.inspiracion;
	}

	async function cargar() {
		loading = true;
		error = '';
		try {
			const res = await api.feed();
			items = res.items || [];
			generadoEn = res.generado_en || '';
			if (res.error) error = 'El feed se generó parcialmente.';
		} catch (e: any) {
			error = e?.message || 'No se pudo generar el feed.';
		} finally {
			loading = false;
		}
	}

	onMount(cargar);
</script>

<div class="space-y-5">
	<div class="flex items-start justify-between gap-3">
		<div>
			<h1 class="text-xl font-bold flex items-center gap-2"><Sparkles size={20} class="text-accent" /> Feed</h1>
			<p class="text-sm text-muted">Inspiración y novedades para tus proyectos activos.</p>
		</div>
		<button
			onclick={cargar}
			disabled={loading}
			class="shrink-0 flex items-center gap-1.5 text-xs font-medium bg-card border border-border rounded-xl px-3 py-2 text-text hover:border-accent disabled:opacity-50"
		>
			{#if loading}<Loader2 size={14} class="animate-spin" />{:else}<RefreshCw size={14} />{/if}
			Actualizar
		</button>
	</div>

	{#if loading && items.length === 0}
		<div class="text-center text-muted py-16 flex flex-col items-center gap-2">
			<Loader2 size={22} class="animate-spin" /> Generando feed con IA…
		</div>
	{:else if error && items.length === 0}
		<div class="text-center text-red-400 py-16">{error}</div>
	{:else if items.length === 0}
		<div class="text-center text-muted py-16">No hay proyectos activos para inspirar un feed. Crea una tarea primero.</div>
	{:else}
		{#if error}
			<div class="text-[11px] text-amber-400 text-center">{error}</div>
		{/if}
		<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
			{#each items as it, i (i)}
				{@const m = meta(it.tipo)}
				{@const Icon = m.icon}
				<div class="bg-card border border-border rounded-2xl p-4 flex flex-col gap-2">
					<div class="flex items-center justify-between gap-2">
						<span class="text-[10px] font-medium px-2 py-0.5 rounded-full border flex items-center gap-1 {m.cls}">
							<Icon size={11} /> {m.label}
						</span>
						{#if it.proyecto}<span class="text-[10px] text-muted truncate max-w-[55%]">{it.proyecto}</span>{/if}
					</div>
					<div class="text-sm font-semibold text-text">{it.titulo}</div>
					{#if it.resumen}<div class="text-xs text-muted">{it.resumen}</div>{/if}
					{#if it.sugerencia}
						<div class="text-[11px] text-accent/90 border-t border-border pt-2 mt-auto">
							<span class="text-muted">Para tu proyecto:</span> {it.sugerencia}
						</div>
					{/if}
				</div>
			{/each}
		</div>
		{#if generadoEn}<div class="text-[10px] text-muted text-center">Generado el {generadoEn}</div>{/if}
	{/if}
</div>
