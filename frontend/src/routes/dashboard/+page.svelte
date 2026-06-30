<script lang="ts">
	import { tareasStore } from '../../lib/stores';
	import { modalStore } from '../../lib/components/modalStore';
	import ProgressBar from '../../lib/components/ProgressBar.svelte';
	import { api } from '../../lib/api';
	import { marked } from 'marked';
	import {
		CheckCircle2, Loader2, Circle, ListTodo, AlertTriangle, Calendar, Target,
		Sparkles, TrendingUp, Flame, Award, Clock, Search, X
	} from 'lucide-svelte';
	import type { Tarea } from '../../lib/types';

	const ETIQUETA_LABEL: Record<string, string> = {
		emprendimiento: 'Emprendimiento',
		tarea: 'Tarea',
		habito: 'Hábito',
		investigacion: 'Investigación',
		idea: 'Idea'
	};

	const hoy = new Date().toISOString().slice(0, 10);

	function clasificar(t: Tarea): 'completada' | 'en_progreso' | 'pendiente' {
		if (t.estado === 'completada') return 'completada';
		if (t.en_progreso_manual || (t.progreso > 0 && t.progreso < 100)) return 'en_progreso';
		return 'pendiente';
	}

	function diasDesde(iso: string | null | undefined): number {
		if (!iso) return 0;
		const d = new Date(iso);
		if (isNaN(d.getTime())) return 0;
		return Math.floor((Date.now() - d.getTime()) / 86400000);
	}

	function calcularRacha(log: string[]): number {
		if (!log || log.length === 0) return 0;
		const ordenados = [...log].sort();
		if (ordenados[ordenados.length - 1] !== hoy) return 0;
		let racha = 1;
		for (let i = ordenados.length - 1; i > 0; i--) {
			const dia = new Date(ordenados[i] + 'T00:00:00');
			const ant = new Date(ordenados[i - 1] + 'T00:00:00');
			ant.setDate(ant.getDate() + 1);
			if (dia.toISOString().slice(0, 10) === ant.toISOString().slice(0, 10)) racha++;
			else break;
		}
		return racha;
	}

	const CATEGORIAS = [
		{ id: 'todas', label: 'Todos' },
		{ id: 'emprendimiento', label: 'Emprendimientos' },
		{ id: 'idea', label: 'Ideas' },
		{ id: 'habito', label: 'Hábitos' },
		{ id: 'investigacion', label: 'Investigación' },
		{ id: 'tarea', label: 'Tareas' }
	] as const;
	let categoria = $state<string>('todas');
	let conteos = $derived.by(() => {
		const m: Record<string, number> = { todas: $tareasStore.length };
		for (const t of $tareasStore) m[t.etiqueta] = (m[t.etiqueta] || 0) + 1;
		return m;
	});

	let proyectos = $derived(
		categoria === 'todas' ? $tareasStore : $tareasStore.filter((t) => t.etiqueta === categoria)
	);
	let completados = $derived(proyectos.filter((t) => clasificar(t) === 'completada'));
	let enProgreso = $derived(proyectos.filter((t) => clasificar(t) === 'en_progreso'));
	let pendientes = $derived(proyectos.filter((t) => clasificar(t) === 'pendiente'));
	let subTotal = $derived(proyectos.reduce((a, t) => a + (t.subtareas_total || 0), 0));
	let subHechas = $derived(proyectos.reduce((a, t) => a + (t.subtareas_completadas || 0), 0));
	let subFaltan = $derived(subTotal - subHechas);
	let progresoGlobal = $derived(
		proyectos.length === 0 ? 0 : Math.round(proyectos.reduce((a, t) => a + (t.progreso || 0), 0) / proyectos.length)
	);
	let vencidos = $derived(
		proyectos.filter((t) => t.estado !== 'completada' && t.fecha_limite && t.fecha_limite < hoy)
	);

	let metrics = $derived.by(() => {
		const total = proyectos.length;
		const completionRate = total ? Math.round((completados.length / total) * 100) : 0;
		const hace7 = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
		const momentum = proyectos.filter((t) => t.completada_en && t.completada_en.slice(0, 10) >= hace7).length;
		const altaPend = proyectos.filter((t) => t.prioridad === 'alta' && clasificar(t) !== 'completada').length;
		let sumScore = 0, nScore = 0, low = 0, conResultado = 0, subN = 0;
		for (const t of proyectos) {
			for (const s of t.subtareas || []) {
				subN++;
				if (s.resultado) conResultado++;
				if (s.score != null) { sumScore += s.score; nScore++; if (s.score < 60) low++; }
			}
		}
		const avgScore = nScore ? Math.round(sumScore / nScore) : null;
		let rachaMax = 0, habitTop = '';
		for (const t of proyectos) {
			if (t.etiqueta === 'habito' || t.repetible) {
				const r = calcularRacha(t.habito_log || []);
				if (r > rachaMax) { rachaMax = r; habitTop = t.titulo; }
			}
		}
		const estancados = proyectos.filter((t) => clasificar(t) === 'en_progreso' && diasDesde(t.creada_en) > 14).length;
		const sinProximo = proyectos.filter((t) => clasificar(t) === 'en_progreso' && !t.proxima_alta_valor).length;
		return {
			total, completionRate, momentum, altaPend, avgScore, low, conResultado, subN,
			rachaMax, habitTop, estancados, sinProximo, vencidos: vencidos.length,
			enProgreso: enProgreso.length, pendientes: pendientes.length
		};
	});

	let headline = $derived.by(() => {
		const m = metrics;
		if (proyectos.length === 0) return 'Aún no hay datos. Crea tu primer proyecto para empezar a medir tu desarrollo.';
		if (m.vencidos > 0) return `Atención: ${m.vencidos} ${m.vencidos === 1 ? 'proyecto vencido necesita' : 'proyectos vencidos necesitan'} acción hoy.`;
		if (m.altaPend > 0 && m.completionRate < 60) return `${m.altaPend} ${m.altaPend === 1 ? 'proyecto de alta prioridad' : 'proyectos de alta prioridad'} en marcha — enfócate ahí para mover la aguja.`;
		if (m.momentum >= 2) return `Buen ritmo: cerraste ${m.momentum} proyectos en los últimos 7 días.`;
		if (m.completionRate >= 70) return `Vas muy bien: ${m.completionRate}% de tus proyectos están completados.`;
		return `${m.enProgreso} en progreso y ${m.pendientes} por empezar. Progreso global: ${progresoGlobal}%.`;
	});

	type Insight = { tipo: 'danger' | 'warn' | 'success' | 'info'; icon: any; titulo: string; detalle: string };
	let insights = $derived.by((): Insight[] => {
		const m = metrics;
		const out: Insight[] = [];
		if (proyectos.length === 0) return out;
		if (m.vencidos > 0) out.push({ tipo: 'danger', icon: AlertTriangle, titulo: `${m.vencidos} vencidos`, detalle: 'Con fecha límite pasada y sin completar.' });
		if (m.altaPend > 0) out.push({ tipo: 'warn', icon: Flame, titulo: `${m.altaPend} alta prioridad`, detalle: 'Proyectos prioritarios aún abiertos.' });
		if (m.estancados > 0) out.push({ tipo: 'warn', icon: Clock, titulo: `${m.estancados} estancados`, detalle: 'En progreso desde hace +14 días.' });
		if (m.momentum > 0) out.push({ tipo: 'success', icon: TrendingUp, titulo: `${m.momentum} cerrados (7d)`, detalle: 'Tu ritmo reciente de avance.' });
		if (m.avgScore != null) out.push({ tipo: m.avgScore >= 75 ? 'success' : 'info', icon: Award, titulo: `Calidad ${m.avgScore}/100`, detalle: m.low > 0 ? `${m.low} subtareas con score bajo.` : 'Buen nivel del trabajo del agente.' });
		if (m.rachaMax > 0) out.push({ tipo: 'success', icon: Flame, titulo: `Racha ${m.rachaMax} días`, detalle: m.habitTop });
		if (m.sinProximo > 0) out.push({ tipo: 'info', icon: Target, titulo: `${m.sinProximo} sin próximo paso`, detalle: 'Define la próxima acción de valor.' });
		if (out.length === 0) out.push({ tipo: 'success', icon: Sparkles, titulo: 'Todo en orden', detalle: 'Sin alertas importantes ahora mismo.' });
		return out;
	});

	const INSIGHT_CLS: Record<string, string> = {
		danger: 'border-red-500/30 bg-red-500/10 text-red-300',
		warn: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
		success: 'border-green-500/30 bg-green-500/10 text-green-300',
		info: 'border-accent/30 bg-accent/10 text-accent'
	};

	let q = $state('');
	let fEstado = $state('todos');
	let fEtiqueta = $state('todas');
	let fPrioridad = $state('todas');
	let orden = $state('relevancia');

	const ORDEN = { en_progreso: 0, pendiente: 1, completada: 2 } as const;
	const PRI: Record<string, number> = { alta: 0, media: 1, baja: 2 };

	let filtrados = $derived.by(() => {
		const term = q.trim().toLowerCase();
		const arr = proyectos.filter((t) => {
			if (term && !`${t.titulo} ${t.descripcion}`.toLowerCase().includes(term)) return false;
			const est = clasificar(t);
			if (fEstado === 'vencidos') {
				if (!(t.estado !== 'completada' && t.fecha_limite && t.fecha_limite < hoy)) return false;
			} else if (fEstado !== 'todos' && est !== fEstado) return false;
			if (fEtiqueta !== 'todas' && t.etiqueta !== fEtiqueta) return false;
			if (fPrioridad !== 'todas' && t.prioridad !== fPrioridad) return false;
			return true;
		});
		arr.sort((a, b) => {
			if (orden === 'progreso') return (b.progreso || 0) - (a.progreso || 0);
			if (orden === 'prioridad') return (PRI[a.prioridad] ?? 1) - (PRI[b.prioridad] ?? 1);
			if (orden === 'fecha') return (a.fecha_limite || '9999-12-31').localeCompare(b.fecha_limite || '9999-12-31');
			if (orden === 'recientes') return (b.creada_en || '').localeCompare(a.creada_en || '');
			const da = ORDEN[clasificar(a)], db = ORDEN[clasificar(b)];
			if (da !== db) return da - db;
			return (b.progreso || 0) - (a.progreso || 0);
		});
		return arr;
	});

	let filtrosActivos = $derived(q.trim() !== '' || fEstado !== 'todos' || fEtiqueta !== 'todas' || fPrioridad !== 'todas');
	function limpiarFiltros() { q = ''; fEstado = 'todos'; fEtiqueta = 'todas'; fPrioridad = 'todas'; orden = 'relevancia'; }

	let iaResumen = $state('');
	let iaLoading = $state(false);
	let iaError = $state('');
	async function generarIA() {
		iaLoading = true;
		iaError = '';
		try {
			const res = await api.resumenDashboard(categoria);
			iaResumen = res.resumen || '';
			if (res.error) iaError = res.error;
		} catch (e: any) {
			iaError = e?.message || 'No se pudo generar el análisis.';
		} finally {
			iaLoading = false;
		}
	}

	const ESTADO_META = {
		completada: { label: 'Completado', icon: CheckCircle2, cls: 'text-green-400 bg-green-500/10 border-green-500/20' },
		en_progreso: { label: 'En progreso', icon: Loader2, cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
		pendiente: { label: 'Pendiente', icon: Circle, cls: 'text-slate-300 bg-slate-500/10 border-slate-500/20' }
	} as const;
</script>

<div class="space-y-5">
	<div class="flex items-start justify-between gap-3 flex-wrap">
		<div>
			<h1 class="text-2xl font-bold">Tu desarrollo</h1>
			<p class="text-sm text-muted">Qué dicen tus datos y dónde conviene enfocar.</p>
		</div>
		<button
			onclick={generarIA}
			disabled={iaLoading || proyectos.length === 0}
			class="flex items-center gap-1.5 text-xs font-medium bg-accent text-white rounded-xl px-3 py-2 disabled:opacity-50 hover:opacity-90"
		>
			{#if iaLoading}<Loader2 size={14} class="animate-spin" />{:else}<Sparkles size={14} />{/if}
			{iaLoading ? 'Analizando...' : 'Analizar con IA'}
		</button>
	</div>

	<div class="flex gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1 pb-0.5">
		{#each CATEGORIAS as c}
			<button
				onclick={() => { categoria = c.id; iaResumen = ''; iaError = ''; }}
				class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors {categoria === c.id ? 'bg-accent text-white border-accent' : 'bg-card border-border text-muted hover:text-text'}"
			>
				{c.label}
				<span class="text-[10px] px-1.5 py-0.5 rounded-full {categoria === c.id ? 'bg-white/20' : 'bg-bg'}">{conteos[c.id] || 0}</span>
			</button>
		{/each}
	</div>

	<div class="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-accent/20 via-card to-card p-6">
		<div class="absolute -top-16 -right-16 w-48 h-48 bg-accent/10 rounded-full blur-3xl"></div>
		<div class="relative">
			<div class="flex items-center gap-1.5 text-accent text-xs font-semibold uppercase tracking-wide mb-2">
				<TrendingUp size={14} /> Resumen de tu desarrollo
			</div>
			<h2 class="text-2xl md:text-3xl font-bold leading-tight max-w-3xl text-text">{headline}</h2>

			<div class="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-sm">
				<div><span class="font-bold text-text">{proyectos.length}</span> <span class="text-muted">proyectos</span></div>
				<div><span class="font-bold text-green-400">{completados.length}</span> <span class="text-muted">completados ({metrics.completionRate}%)</span></div>
				<div><span class="font-bold text-text">{subHechas}/{subTotal}</span> <span class="text-muted">subtareas</span></div>
				{#if metrics.vencidos > 0}<div><span class="font-bold text-red-400">{metrics.vencidos}</span> <span class="text-muted">vencidos</span></div>{/if}
			</div>

			{#if iaResumen}
				<div class="mt-4 bg-bg/60 border border-border rounded-2xl p-4 prose prose-invert prose-sm max-w-none">
					{@html marked.parse(iaResumen, { async: false })}
				</div>
			{:else if iaError}
				<div class="mt-4 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">{iaError}</div>
			{/if}

			<div class="mt-5">
				<div class="flex items-center justify-between mb-1.5">
					<span class="text-xs font-medium text-muted">Progreso global</span>
					<span class="text-xs font-medium text-text">{progresoGlobal}%</span>
				</div>
				<ProgressBar pct={progresoGlobal} />
			</div>
		</div>
	</div>

	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		<div class="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
			<div class="w-10 h-10 rounded-xl bg-accent/15 text-accent flex items-center justify-center shrink-0"><ListTodo size={18} /></div>
			<div class="min-w-0">
				<div class="text-xl font-bold leading-none">{proyectos.length}</div>
				<div class="text-[11px] text-muted mt-1 truncate">{enProgreso.length} activos · {pendientes.length} pend.</div>
			</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
			<div class="w-10 h-10 rounded-xl bg-green-500/15 text-green-400 flex items-center justify-center shrink-0"><CheckCircle2 size={18} /></div>
			<div class="min-w-0">
				<div class="text-xl font-bold leading-none text-green-400">{completados.length}</div>
				<div class="text-[11px] text-muted mt-1 truncate">{metrics.completionRate}% del total</div>
			</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
			<div class="w-10 h-10 rounded-xl bg-accent/15 text-accent flex items-center justify-center shrink-0"><Target size={18} /></div>
			<div class="min-w-0">
				<div class="text-xl font-bold leading-none">{subHechas}<span class="text-sm text-muted">/{subTotal}</span></div>
				<div class="text-[11px] text-muted mt-1 truncate">faltan {subFaltan}</div>
			</div>
		</div>
		<div class="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
			<div class="w-10 h-10 rounded-xl {metrics.vencidos ? 'bg-red-500/15 text-red-400' : 'bg-slate-500/15 text-slate-400'} flex items-center justify-center shrink-0"><AlertTriangle size={18} /></div>
			<div class="min-w-0">
				<div class="text-xl font-bold leading-none {metrics.vencidos ? 'text-red-400' : ''}">{metrics.vencidos}</div>
				<div class="text-[11px] text-muted mt-1 truncate">vencidos</div>
			</div>
		</div>
	</div>

	{#if insights.length > 0}
		<div>
			<div class="flex items-center gap-1.5 text-sm font-semibold mb-2"><Sparkles size={15} class="text-accent" /> Lo que dicen tus datos</div>
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
				{#each insights as ins}
					{@const I = ins.icon}
					<div class="rounded-2xl border p-3 {INSIGHT_CLS[ins.tipo]}">
						<div class="flex items-center gap-1.5 font-semibold text-sm"><I size={15} /> {ins.titulo}</div>
						<div class="text-[11px] opacity-80 mt-1 leading-snug truncate">{ins.detalle}</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<div class="flex flex-wrap items-center gap-2 bg-card border border-border rounded-2xl p-3">
		<div class="relative flex-1 min-w-[160px]">
			<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
			<input bind:value={q} placeholder="Buscar proyecto..." class="w-full bg-bg border border-border rounded-xl pl-8 pr-3 py-2 text-xs text-text placeholder-muted" />
		</div>
		<select bind:value={fEstado} class="bg-bg border border-border rounded-xl px-2 py-2 text-xs text-text">
			<option value="todos">Estado: todos</option>
			<option value="en_progreso">En progreso</option>
			<option value="pendiente">Pendiente</option>
			<option value="completada">Completado</option>
			<option value="vencidos">Vencidos</option>
		</select>
		<select bind:value={fPrioridad} class="bg-bg border border-border rounded-xl px-2 py-2 text-xs text-text">
			<option value="todas">Prioridad: todas</option>
			<option value="alta">Alta</option>
			<option value="media">Media</option>
			<option value="baja">Baja</option>
		</select>
		<select bind:value={orden} class="bg-bg border border-border rounded-xl px-2 py-2 text-xs text-text">
			<option value="relevancia">Orden: relevancia</option>
			<option value="progreso">Mayor progreso</option>
			<option value="prioridad">Prioridad</option>
			<option value="fecha">Fecha límite</option>
			<option value="recientes">Más recientes</option>
		</select>
		<span class="text-[11px] text-muted ml-auto">{filtrados.length} de {proyectos.length}</span>
		{#if filtrosActivos}
			<button onclick={limpiarFiltros} class="flex items-center gap-1 text-[11px] text-muted hover:text-text border border-border rounded-xl px-2 py-2"><X size={12} /> Limpiar</button>
		{/if}
	</div>

	{#if proyectos.length === 0}
		<div class="text-center text-muted py-16">No hay proyectos todavía.</div>
	{:else if filtrados.length === 0}
		<div class="text-center text-muted py-16">Ningún proyecto coincide con los filtros.</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
			{#each filtrados as t (t.id)}
				{@const estado = clasificar(t)}
				{@const meta = ESTADO_META[estado]}
				{@const Icon = meta.icon}
				{@const faltan = (t.subtareas_total || 0) - (t.subtareas_completadas || 0)}
				{@const vencido = t.estado !== 'completada' && t.fecha_limite && t.fecha_limite < hoy}
				<button
					onclick={() => modalStore.openDetail(t)}
					class="text-left bg-card border border-border rounded-2xl p-4 hover:border-accent transition-colors flex flex-col gap-2"
				>
					<div class="flex items-start justify-between gap-2">
						<div class="flex items-center gap-2 min-w-0">
							{#if t.icono}<span class="text-lg shrink-0">{t.icono}</span>{/if}
							<div class="min-w-0">
								<div class="text-sm font-semibold truncate {estado === 'completada' ? 'line-through text-muted' : 'text-text'}">{t.titulo}</div>
								<div class="text-[10px] text-muted">#{t.numero} · {ETIQUETA_LABEL[t.etiqueta] || t.etiqueta}</div>
							</div>
						</div>
						<span class="text-[10px] font-medium px-2 py-0.5 rounded-full border flex items-center gap-1 shrink-0 {meta.cls}">
							<Icon size={11} class={estado === 'en_progreso' ? 'animate-spin' : ''} /> {meta.label}
						</span>
					</div>

					<div>
						<div class="flex items-center justify-between text-[10px] text-muted mb-1">
							<span>{t.subtareas_completadas}/{t.subtareas_total} subtareas</span>
							<span>{Math.round(t.progreso)}%</span>
						</div>
						<ProgressBar pct={t.progreso} />
					</div>

					<div class="flex items-center gap-2 flex-wrap text-[10px]">
						{#if faltan > 0}
							<span class="px-2 py-0.5 rounded-full bg-card2 border border-border text-muted">Faltan {faltan}</span>
						{:else if t.subtareas_total > 0}
							<span class="px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400">Todo hecho</span>
						{/if}
						{#if t.fecha_limite}
							<span class="px-2 py-0.5 rounded-full border flex items-center gap-1 {vencido ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-card2 border-border text-muted'}">
								<Calendar size={10} /> {t.fecha_limite}
							</span>
						{/if}
					</div>

					{#if t.proxima_alta_valor}
						<div class="text-[11px] text-accent/90 border-t border-border pt-2 mt-0.5">
							<span class="text-muted">Próximo:</span> {t.proxima_alta_valor}
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
