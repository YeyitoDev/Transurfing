<script lang="ts">
	import mermaid from 'mermaid';
	import type { Tarea } from '../types';

	let { tarea }: { tarea: Tarea } = $props();
	let svg = $state('');
	let error = $state('');
	let counter = 0;

	mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });

	function esc(s: string): string {
		return (s || '')
			.replace(/"/g, "'")
			.replace(/[\n\r]+/g, ' ')
			.slice(0, 60);
	}

	function buildGraph(t: Tarea): string {
		const lines: string[] = ['graph LR'];
		lines.push(`T["${esc(t.titulo)} · ${Math.round(t.progreso)}%"]`);
		lines.push('class T root;');
		const subs = t.subtareas || [];
		if (subs.length === 0) {
			lines.push('N["Sin subtareas todavía"]');
			lines.push('T --> N');
			lines.push('class N pendiente;');
		}
		subs.forEach((s, i) => {
			const id = `S${i}`;
			lines.push(`${id}["${esc(s.titulo)}"]`);
			lines.push(`T --> ${id}`);
			const estado = s.estado || (s.completada ? 'completada' : 'pendiente');
			lines.push(`class ${id} ${estado};`);
		});
		lines.push('classDef root fill:#6366f1,stroke:#818cf8,color:#fff;');
		lines.push('classDef completada fill:#16a34a33,stroke:#22c55e,color:#dcfce7;');
		lines.push('classDef en_progreso fill:#d9770633,stroke:#f59e0b,color:#fde68a;');
		lines.push('classDef bloqueada fill:#dc262633,stroke:#ef4444,color:#fecaca;');
		lines.push('classDef pendiente fill:#33415533,stroke:#64748b,color:#cbd5e1;');
		return lines.join('\n');
	}

	$effect(() => {
		const code = buildGraph(tarea);
		mermaid
			.render('projgraph-' + tarea.id + '-' + counter++, code)
			.then(({ svg: s }) => {
				svg = s;
				error = '';
			})
			.catch((e) => {
				error = e?.message || 'No se pudo dibujar el grafo';
			});
	});
</script>

<div class="bg-card2 border border-border rounded-xl p-3 mb-4">
	<div class="flex items-center justify-between mb-2">
		<span class="text-xs font-semibold text-text">Estructura del proyecto</span>
		<span class="text-[10px] text-muted">
			{tarea.subtareas_completadas}/{tarea.subtareas_total} subtareas · {Math.round(tarea.progreso)}%
		</span>
	</div>
	{#if error}
		<div class="text-[10px] text-red-400">No se pudo dibujar el grafo: {error}</div>
	{:else}
		<div class="overflow-auto [&_svg]:max-w-none">{@html svg}</div>
	{/if}
	<div class="flex flex-wrap gap-2 mt-2 text-[9px] text-muted">
		<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500"></span> Completada</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-amber-500"></span> En progreso</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500"></span> Bloqueada</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-slate-500"></span> Pendiente</span>
	</div>
</div>
