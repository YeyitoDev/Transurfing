<script lang="ts">
	import { api } from '$lib/api';
	import type { ChangelogEntry } from '$lib/types';
	import { FileText, Plus, Sparkles, Loader2, Save, CheckCircle, AlertCircle, Calendar, Tag, ChevronDown, ChevronUp, Clock, Zap, ShieldAlert, AlertTriangle, Info } from 'lucide-svelte';

	let entries = $state<ChangelogEntry[]>([]);
	let loading = $state(false);
	let saving = $state(false);
	let generating = $state(false);
	let error = $state('');
	let success = $state('');

	let version = $state('Unreleased');
	let seccion = $state('General');
	let fecha = $state(new Date().toISOString().slice(0, 10));
	let impacto = $state<'medio' | 'bajo' | 'alto' | 'critico'>('medio');
	let cambiosTexto = $state('');
	let qaTexto = $state('');

	let agentVersion = $state('Unreleased');
	let agentSeccion = $state('General');
	let agentImpacto = $state<'medio' | 'bajo' | 'alto' | 'critico'>('medio');
	let agentChanges = $state('');

	let expanded = $state<Set<string>>(new Set());
	let showRaw = $state(false);
	let rawMarkdown = $state('');

	const impactoConfig = {
		critico: { label: 'Crítico', color: 'text-red-400 bg-red-500/10 border-red-500/20', icon: ShieldAlert, bar: 'bg-red-500' },
		alto: { label: 'Alto', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20', icon: AlertTriangle, bar: 'bg-orange-500' },
		medio: { label: 'Medio', color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20', icon: Zap, bar: 'bg-yellow-500' },
		bajo: { label: 'Bajo', color: 'text-green-400 bg-green-500/10 border-green-500/20', icon: Info, bar: 'bg-green-500' }
	};

	async function cargar() {
		loading = true;
		try {
			const [res, md] = await Promise.all([api.getChangelogEntries(), api.getChangelog()]);
			entries = res.entries.sort((a, b) => b.fecha.localeCompare(a.fecha) || impactoOrder(b.impacto) - impactoOrder(a.impacto));
			rawMarkdown = md.content;
		} catch (e: any) {
			error = e?.message || 'No se pudo cargar el changelog.';
		} finally {
			loading = false;
		}
	}

	function impactoOrder(i: string): number {
		return { critico: 3, alto: 2, medio: 1, bajo: 0 }[i] ?? 0;
	}

	function formatearFecha(fechaStr: string): string {
		const d = new Date(fechaStr + 'T00:00:00');
		return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
	}

	function toggleExpanded(id: string) {
		const next = new Set(expanded);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		expanded = next;
	}

	async function agregarManual() {
		saving = true;
		error = '';
		success = '';
		try {
			const cambios = cambiosTexto.split('\n').map(s => s.trim()).filter(Boolean);
			const casos = qaTexto.split('\n').map(s => s.trim()).filter(Boolean);
			if (!version || !seccion || cambios.length === 0) {
				error = 'Completa versión, sección y al menos un cambio.';
				return;
			}
			await api.addChangelogEntry(version, seccion, cambios, casos, fecha, impacto);
			success = 'Entrada añadida al changelog.';
			cambiosTexto = '';
			qaTexto = '';
			await cargar();
		} catch (e: any) {
			error = e?.message || 'Error guardando la entrada.';
		} finally {
			saving = false;
		}
	}

	async function generar() {
		generating = true;
		error = '';
		success = '';
		try {
			await api.ensureChangelogSkill();
			const res = await api.generateChangelog(agentChanges, agentVersion, agentSeccion, agentImpacto);
			if (!res.ok) {
				error = res.raw || 'El agente no generó cambios válidos.';
				return;
			}
			success = 'Changelog generado por el agente y guardado.';
			agentChanges = '';
			await cargar();
		} catch (e: any) {
			error = e?.message || 'Error generando el changelog.';
		} finally {
			generating = false;
		}
	}

	cargar();
</script>

<div class="min-h-screen bg-bg p-4 pb-24">
	<div class="max-w-4xl mx-auto">
		<header class="flex items-center justify-between mb-6">
			<div>
				<h1 class="text-xl font-semibold text-text flex items-center gap-2">
					<FileText size={22} /> Changelog & QA
				</h1>
				<p class="text-xs text-muted mt-1">Cronograma de cambios, fechas e impacto para facilitar QA.</p>
			</div>
			<button onclick={() => history.back()} class="text-sm text-muted hover:text-text">Volver</button>
		</header>

		{#if error}
			<div class="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-start gap-2">
				<AlertCircle size={14} class="mt-0.5 shrink-0" /> {error}
			</div>
		{/if}
		{#if success}
			<div class="mb-4 p-3 rounded-xl bg-green-500/10 border border-green-500/20 text-xs text-green-400 flex items-start gap-2">
				<CheckCircle size={14} class="mt-0.5 shrink-0" /> {success}
			</div>
		{/if}

		<div class="grid lg:grid-cols-2 gap-4 mb-6">
			<div class="bg-card border border-border rounded-2xl p-4">
				<h2 class="text-sm font-semibold text-text mb-3 flex items-center gap-1.5"><Plus size={14} /> Añadir entrada manual</h2>
				<div class="space-y-3">
					<div class="grid grid-cols-2 gap-2">
						<div>
							<label for="cl-version" class="text-[10px] text-muted uppercase tracking-wide">Versión</label>
							<input id="cl-version" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={version} />
						</div>
						<div>
							<label for="cl-seccion" class="text-[10px] text-muted uppercase tracking-wide">Sección</label>
							<input id="cl-seccion" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={seccion} />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div>
							<label for="cl-fecha" class="text-[10px] text-muted uppercase tracking-wide">Fecha</label>
							<input id="cl-fecha" type="date" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={fecha} />
						</div>
						<div>
							<label for="cl-impacto" class="text-[10px] text-muted uppercase tracking-wide">Impacto</label>
							<select id="cl-impacto" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={impacto}>
								<option value="bajo">Bajo</option>
								<option value="medio">Medio</option>
								<option value="alto">Alto</option>
								<option value="critico">Crítico</option>
							</select>
						</div>
					</div>
					<div>
						<label for="cl-cambios" class="text-[10px] text-muted uppercase tracking-wide">Cambios (uno por línea)</label>
						<textarea id="cl-cambios" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text min-h-[80px]" bind:value={cambiosTexto}></textarea>
					</div>
					<div>
						<label for="cl-qa" class="text-[10px] text-muted uppercase tracking-wide">Casos QA (uno por línea)</label>
						<textarea id="cl-qa" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text min-h-[60px]" bind:value={qaTexto}></textarea>
					</div>
					<button onclick={agregarManual} disabled={saving} class="w-full bg-accent text-white rounded-lg px-3 py-2 text-sm font-medium flex items-center justify-center gap-1.5 disabled:opacity-50">
						{#if saving}<Loader2 class="animate-spin" size={14} />{:else}<Save size={14} />{/if}
						{saving ? 'Guardando...' : 'Añadir al changelog'}
					</button>
				</div>
			</div>

			<div class="bg-card border border-border rounded-2xl p-4">
				<h2 class="text-sm font-semibold text-text mb-3 flex items-center gap-1.5"><Sparkles size={14} /> Generar con agente</h2>
				<p class="text-xs text-muted mb-3">Pega una lista de cambios y el agente generará fecha, impacto, bullets y casos QA.</p>
				<div class="space-y-3">
					<div class="grid grid-cols-2 gap-2">
						<div>
							<label for="agent-version" class="text-[10px] text-muted uppercase tracking-wide">Versión</label>
							<input id="agent-version" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={agentVersion} />
						</div>
						<div>
							<label for="agent-seccion" class="text-[10px] text-muted uppercase tracking-wide">Sección</label>
							<input id="agent-seccion" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={agentSeccion} />
						</div>
					</div>
					<div>
						<label for="agent-impacto" class="text-[10px] text-muted uppercase tracking-wide">Impacto esperado</label>
						<select id="agent-impacto" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text" bind:value={agentImpacto}>
							<option value="bajo">Bajo</option>
							<option value="medio">Medio</option>
							<option value="alto">Alto</option>
							<option value="critico">Crítico</option>
						</select>
					</div>
					<div>
						<label for="agent-cambios" class="text-[10px] text-muted uppercase tracking-wide">Cambios (uno por línea)</label>
						<textarea id="agent-cambios" class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text min-h-[100px]" placeholder="- Integración OAuth con GitHub\n- Nuevo panel de hábitos..." bind:value={agentChanges}></textarea>
					</div>
					<button onclick={generar} disabled={generating || !agentChanges.trim()} class="w-full bg-card2 text-text border border-border rounded-lg px-3 py-2 text-sm font-medium flex items-center justify-center gap-1.5 disabled:opacity-50">
						{#if generating}<Loader2 class="animate-spin" size={14} />{:else}<Sparkles size={14} />{/if}
						{generating ? 'Generando...' : 'Generar con agente'}
					</button>
				</div>
			</div>
		</div>

		<div class="bg-card border border-border rounded-2xl p-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-sm font-semibold text-text flex items-center gap-1.5"><Clock size={14} /> Cronograma de cambios</h2>
				<button onclick={() => showRaw = !showRaw} class="text-xs text-muted hover:text-text">
					{showRaw ? 'Ver cronograma' : 'Ver markdown'}
				</button>
			</div>

			{#if loading}
				<div class="text-sm text-muted py-8 text-center">Cargando changelog...</div>
			{:else if showRaw}
				<pre class="text-xs text-muted whitespace-pre-wrap bg-bg rounded-xl p-3 border border-border">{rawMarkdown}</pre>
			{:else if entries.length === 0}
				<div class="text-sm text-muted py-8 text-center">No hay entradas en el changelog.</div>
			{:else}
				<div class="relative pl-2">
					{#each entries as entry, idx (entry.id)}
						{@const cfg = impactoConfig[entry.impacto] || impactoConfig.medio}
						{@const Icon = cfg.icon}
						{@const isExpanded = expanded.has(entry.id)}
						<div class="relative flex gap-4 pb-6 last:pb-0">
							<div class="flex flex-col items-center">
								<div class="w-3 h-3 rounded-full {cfg.bar} ring-4 ring-bg"></div>
								{#if idx < entries.length - 1}
									<div class="w-0.5 flex-1 bg-border mt-2"></div>
								{/if}
							</div>
							<div class="flex-1 -mt-1">
								<div class="flex flex-wrap items-center gap-2 mb-2">
									<div class="flex items-center gap-1 text-xs text-muted">
										<Calendar size={12} /> {formatearFecha(entry.fecha)}
									</div>
									<div class="px-2 py-0.5 rounded-full text-[10px] font-medium border {cfg.color} flex items-center gap-1">
										<Icon size={10} /> {cfg.label}
									</div>
									<div class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-card2 text-muted border border-border flex items-center gap-1">
										<Tag size={10} /> {entry.version}
									</div>
								</div>
								<h3 class="text-sm font-semibold text-text mb-1">{entry.seccion}</h3>
								<ul class="space-y-1 mb-2">
									{#each entry.cambios as cambio}
										<li class="text-sm text-muted flex items-start gap-2">
											<span class="mt-1.5 w-1 h-1 rounded-full {cfg.bar} shrink-0"></span>
											<span>{cambio}</span>
										</li>
									{/each}
								</ul>
								{#if entry.casos_qa.length > 0}
									<button onclick={() => toggleExpanded(entry.id)} class="flex items-center gap-1 text-xs text-accent hover:opacity-80 mb-2">
										{#if isExpanded}<ChevronUp size={12} />{:else}<ChevronDown size={12} />{/if}
										{entry.casos_qa.length} caso{entry.casos_qa.length === 1 ? '' : 's'} de prueba QA
									</button>
									{#if isExpanded}
										<ol class="space-y-1.5 bg-card2 rounded-xl p-3 border border-border">
											{#each entry.casos_qa as caso, i}
												<li class="text-xs text-muted flex items-start gap-2">
													<span class="font-medium text-text shrink-0">{i + 1}.</span>
													<span>{caso}</span>
												</li>
											{/each}
										</ol>
									{/if}
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
