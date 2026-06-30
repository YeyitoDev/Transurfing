<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '../../lib/api';
	import {
		Sparkles, Loader2, RefreshCw, Newspaper, Lightbulb, Cpu, Wrench, BookOpen,
		Rss, FlaskConical, MessageSquare, Globe, ExternalLink, HelpCircle, Eye
	} from 'lucide-svelte';

	type FeedItem = { proyecto: string; tipo: string; titulo: string; resumen: string; sugerencia: string };
	type Senales = { relevancia: number; recencia: number; popularidad: number; autoridad: number };
	type VivoItem = {
		fuente: string; fuente_label: string; tipo: string; titulo: string; resumen: string;
		url: string; tema: string; score: number; fecha?: string; senales: Senales;
		metricas?: { puntos?: number; comentarios?: number };
	};
	type VivoData = {
		experimental: boolean; enabled: boolean; items: VivoItem[]; preguntas: string[];
		panorama?: string; fuentes?: string[]; criterios?: Record<string, number>;
		ttl_min?: number; generado_en: string; cache?: boolean; rate_limited?: boolean;
		aviso?: string; error?: string;
	};

	let vista = $state<'curado' | 'vivo'>('curado');

	// Feed curado (IA)
	let items = $state<FeedItem[]>([]);
	let loading = $state(false);
	let error = $state('');
	let generadoEn = $state('');

	// Feed vivo (experimental)
	let vivo = $state<VivoData | null>(null);
	let vivoLoading = $state(false);
	let vivoError = $state('');
	let vivoCargado = false;

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

	const FUENTE_META: Record<string, { label: string; icon: typeof Cpu; cls: string }> = {
		arxiv: { label: 'arXiv', icon: FlaskConical, cls: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
		hackernews: { label: 'Hacker News', icon: MessageSquare, cls: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
		wikipedia: { label: 'Wikipedia', icon: BookOpen, cls: 'text-slate-300 bg-slate-500/10 border-slate-500/20' },
		web: { label: 'Web', icon: Globe, cls: 'text-sky-400 bg-sky-500/10 border-sky-500/20' }
	};
	function fmeta(f: string) {
		return FUENTE_META[f] || FUENTE_META.web;
	}

	const CRIT = [
		{ key: 'relevancia', label: 'Relevancia', cls: 'bg-accent' },
		{ key: 'recencia', label: 'Recencia', cls: 'bg-sky-400' },
		{ key: 'popularidad', label: 'Popularidad', cls: 'bg-amber-400' },
		{ key: 'autoridad', label: 'Autoridad', cls: 'bg-emerald-400' }
	] as const;

	function scoreCls(s: number) {
		if (s >= 70) return 'text-green-400 bg-green-500/10 border-green-500/20';
		if (s >= 45) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
		return 'text-muted bg-card2 border-border';
	}
	function fmtFecha(s: string) {
		try {
			return new Date(s).toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' });
		} catch {
			return s;
		}
	}
	const tieneWeb = $derived((vivo?.fuentes || []).some((f) => f.startsWith('web')));

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

	async function cargarVivo(force = false) {
		vivoLoading = true;
		vivoError = '';
		try {
			vivo = await api.feedVivo(force);
			if (vivo?.error) vivoError = 'El feed vivo se generó parcialmente.';
		} catch (e: any) {
			vivoError = e?.message || 'No se pudo generar el feed vivo.';
		} finally {
			vivoLoading = false;
		}
	}

	function setVista(v: 'curado' | 'vivo') {
		vista = v;
		if (v === 'vivo' && !vivoCargado) {
			vivoCargado = true;
			cargarVivo(false);
		}
	}

	function refrescar() {
		if (vista === 'curado') cargar();
		else cargarVivo(true);
	}

	onMount(cargar);
</script>

<div class="space-y-5">
	<div class="flex items-start justify-between gap-3 flex-wrap">
		<div>
			<h1 class="text-xl font-bold flex items-center gap-2"><Sparkles size={20} class="text-accent" /> Feed</h1>
			<p class="text-sm text-muted">Inspiración, novedades y descubrimientos para tus proyectos.</p>
		</div>
		<div class="flex items-center gap-2">
			<div class="flex bg-card border border-border rounded-xl p-0.5 text-xs">
				<button
					onclick={() => setVista('curado')}
					class="px-3 py-1.5 rounded-lg font-medium transition-colors {vista === 'curado' ? 'bg-accent text-white' : 'text-muted hover:text-text'}"
				>Curado</button>
				<button
					onclick={() => setVista('vivo')}
					class="px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1 {vista === 'vivo' ? 'bg-accent text-white' : 'text-muted hover:text-text'}"
				><Rss size={12} /> Vivo</button>
			</div>
			<button
				onclick={refrescar}
				disabled={vista === 'curado' ? loading : vivoLoading}
				class="shrink-0 flex items-center gap-1.5 text-xs font-medium bg-card border border-border rounded-xl px-3 py-2 text-text hover:border-accent disabled:opacity-50"
			>
				{#if vista === 'curado' ? loading : vivoLoading}<Loader2 size={14} class="animate-spin" />{:else}<RefreshCw size={14} />{/if}
				Actualizar
			</button>
		</div>
	</div>

	{#if vista === 'curado'}
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
	{:else}
		<div class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] text-amber-300/90 flex items-start gap-2">
			<Rss size={14} class="mt-0.5 shrink-0" />
			<div>
				<b>Experimental.</b> Búsquedas reales en arXiv, Hacker News y Wikipedia{tieneWeb ? ' + web' : ''}, a partir de tus proyectos. Ranking por criterios medibles: relevancia, recencia, popularidad y autoridad. Resultados cacheados {vivo?.ttl_min ? Math.round(vivo.ttl_min / 60) : 6} h para no abusar de las consultas.
				{#if vivo?.aviso}<div class="mt-1 text-amber-200">{vivo.aviso}</div>{/if}
			</div>
		</div>

		{#if vivoLoading && !vivo}
			<div class="text-center text-muted py-16 flex flex-col items-center gap-2">
				<Loader2 size={22} class="animate-spin" /> Buscando lo más relevante del mundo…
			</div>
		{:else if vivoError && !vivo?.items?.length}
			<div class="text-center text-red-400 py-16">{vivoError}</div>
		{:else if vivo && vivo.enabled === false}
			<div class="text-center text-muted py-16">El feed vivo está desactivado.</div>
		{:else if vivo && vivo.items.length === 0}
			<div class="text-center text-muted py-16">Sin resultados todavía. Crea proyectos con un objetivo claro y vuelve a intentar.</div>
		{:else if vivo}
			{#if vivo.panorama}
				<div class="rounded-2xl border border-accent/30 bg-accent/5 p-4">
					<div class="text-xs font-semibold text-accent flex items-center gap-1.5 mb-1"><Eye size={14} /> Lo que veo</div>
					<p class="text-sm text-text">{vivo.panorama}</p>
				</div>
			{/if}

			{#if vivo.preguntas?.length}
				<div class="rounded-2xl border border-border bg-card p-4">
					<div class="text-xs font-semibold flex items-center gap-1.5 mb-2"><HelpCircle size={14} class="text-accent" /> Preguntas para explorar</div>
					<ul class="space-y-1.5">
						{#each vivo.preguntas as p}
							<li class="text-sm text-muted flex gap-2"><span class="text-accent shrink-0">·</span><span>{p}</span></li>
						{/each}
					</ul>
				</div>
			{/if}

			<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
				{#each vivo.items as it (it.url)}
					{@const fm = fmeta(it.fuente)}
					{@const FIcon = fm.icon}
					<a
						href={it.url}
						target="_blank"
						rel="noopener noreferrer"
						class="group bg-card border border-border rounded-2xl p-4 flex flex-col gap-2 hover:border-accent transition-colors"
					>
						<div class="flex items-center justify-between gap-2">
							<span class="text-[10px] font-medium px-2 py-0.5 rounded-full border flex items-center gap-1 {fm.cls}">
								<FIcon size={11} /> {fm.label}
							</span>
							<span class="text-[10px] font-bold px-2 py-0.5 rounded-full border {scoreCls(it.score)}" title="Puntuación objetiva 0–100">{it.score}</span>
						</div>
						<div class="text-sm font-semibold text-text group-hover:text-accent flex items-start gap-1">
							<span>{it.titulo}</span>
							<ExternalLink size={12} class="mt-0.5 shrink-0 opacity-0 group-hover:opacity-60" />
						</div>
						{#if it.resumen}<div class="text-xs text-muted">{it.resumen}</div>{/if}
						<div class="flex items-center gap-2 flex-wrap text-[10px] text-muted">
							{#if it.tema}<span class="px-2 py-0.5 rounded-full bg-card2 border border-border truncate max-w-[60%]">{it.tema}</span>{/if}
							{#if it.fecha}<span>{it.fecha}</span>{/if}
							{#if it.metricas?.puntos}<span>{it.metricas.puntos} pts</span>{/if}
							{#if it.metricas?.comentarios}<span>{it.metricas.comentarios} coment.</span>{/if}
						</div>
						<div class="border-t border-border pt-2 mt-auto grid grid-cols-2 gap-x-3 gap-y-1">
							{#each CRIT as c}
								<div class="flex items-center gap-1.5" title="{c.label}: {Math.round(it.senales[c.key] * 100)}%">
									<span class="text-[9px] text-muted w-16 shrink-0">{c.label}</span>
									<div class="flex-1 h-1 rounded-full bg-card2 overflow-hidden">
										<div class="h-full {c.cls}" style="width:{Math.round(it.senales[c.key] * 100)}%"></div>
									</div>
								</div>
							{/each}
						</div>
					</a>
				{/each}
			</div>

			<div class="flex items-center gap-2 flex-wrap text-[10px] text-muted">
				{#if vivo.fuentes?.length}
					<span>Fuentes:</span>
					{#each vivo.fuentes as f}<span class="px-2 py-0.5 rounded-full bg-card2 border border-border">{f}</span>{/each}
				{/if}
				{#if vivo.generado_en}<span class="ml-auto">{vivo.cache ? 'En cache · ' : ''}Actualizado {fmtFecha(vivo.generado_en)}</span>{/if}
			</div>
			{#if vivoError}<div class="text-[11px] text-amber-400 text-center">{vivoError}</div>{/if}
		{/if}
	{/if}
</div>
