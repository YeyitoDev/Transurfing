<script lang="ts">
	import { X, Type, Lightbulb, Code, Image, Table, Workflow, Sparkles, Loader2, Save, MousePointer2 } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import type { Tarea, TareaCanvas, CanvasBloque, CanvasLink } from '../types';
	import mermaid from 'mermaid';

	let { tarea, onClose }: { tarea: Tarea; onClose: () => void } = $props();


	const TIPOS: { key: CanvasBloque['tipo']; label: string; icon: typeof Type }[] = [
		{ key: 'texto', label: 'Texto', icon: Type },
		{ key: 'idea', label: 'Idea', icon: Lightbulb },
		{ key: 'codigo', label: 'Código', icon: Code },
		{ key: 'json', label: 'JSON', icon: Code },
		{ key: 'diagrama', label: 'Diagrama', icon: Workflow },
		{ key: 'imagen', label: 'Imagen', icon: Image },
		{ key: 'tabla', label: 'Tabla', icon: Table },
	];

	const DEFAULTS: Record<CanvasBloque['tipo'], { width: number; height: number; texto: string }> = {
		texto: { width: 220, height: 120, texto: '' },
		idea: { width: 240, height: 130, texto: 'Idea clave...' },
		codigo: { width: 320, height: 180, texto: '// código' },
		diagrama: { width: 420, height: 280, texto: 'graph TD\n  A[Inicio] --> B{Decisión}\n  B -->|Sí| C[Acción]\n  B -->|No| D[Fin]' },
		json: { width: 320, height: 180, texto: '{\n  "clave": "valor"\n}' },
		imagen: { width: 240, height: 160, texto: 'https://' },
		tabla: { width: 320, height: 160, texto: '' },
	};

	let canvas = $state<TareaCanvas>(
		tarea.canvas ? JSON.parse(JSON.stringify(tarea.canvas)) : { bloques: [], links: [] }
	);
	let selectedTipo = $state<CanvasBloque['tipo']>('texto');
	let dragging = $state<{ id: string; offsetX: number; offsetY: number } | null>(null);
	let resizing = $state<{ id: string; dir: string; startX: number; startY: number; startW: number; startH: number; startBX: number; startBY: number } | null>(null);
	let canvasEl: HTMLDivElement | null = $state(null);
	let diagramSvg = $state<Record<string, string>>({});
	let interpretacion = $state<import('../types').CanvasInterpretacion | null>(null);
	let interpretando = $state(false);
	let guardando = $state(false);
	let selectedId = $state<string | null>(null);
	let linkMode = $state(false);
	let linkSource = $state<string | null>(null);

	mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });

	function uid() {
		return 'b_' + Math.random().toString(36).slice(2, 9) + Date.now().toString(36).slice(-3);
	}

	function saveCanvas() {
		guardando = true;
		api
			.guardarCanvas(tarea.id, canvas)
			.then((t) => onTaskChange(t))
			.finally(() => setTimeout(() => (guardando = false), 400));
	}

	function handleCanvasClick(e: MouseEvent) {
		if (!canvasEl || dragging || resizing) return;
		if ((e.target as HTMLElement) !== canvasEl) return;
		const rect = canvasEl.getBoundingClientRect();
		const x = e.clientX - rect.left + canvasEl.scrollLeft;
		const y = e.clientY - rect.top + canvasEl.scrollTop;
		const def = DEFAULTS[selectedTipo];
		const b: CanvasBloque = {
			id: uid(),
			tipo: selectedTipo,
			x: Math.round(x - def.width / 2),
			y: Math.round(y - def.height / 2),
			width: def.width,
			height: def.height,
			texto: def.texto,
		};
		canvas.bloques = [...canvas.bloques, b];
		selectedId = b.id;
		saveCanvas();
	}

	function deleteBlock(id: string) {
		canvas.bloques = canvas.bloques.filter((b) => b.id !== id);
		canvas.links = (canvas.links || []).filter((l) => l.a !== id && l.b !== id);
		selectedId = null;
		delete diagramSvg[id];
		saveCanvas();
	}

	function updateBlock(id: string, patch: Partial<CanvasBloque>) {
		canvas.bloques = canvas.bloques.map((b) => (b.id === id ? { ...b, ...patch } : b));
	}

	function onMouseDownBlock(e: MouseEvent, block: CanvasBloque) {
		if (linkMode) {
			e.stopPropagation();
			if (!linkSource) {
				linkSource = block.id;
			} else if (linkSource !== block.id) {
				const exists = (canvas.links || []).some(
					(l) => (l.a === linkSource && l.b === block.id) || (l.a === block.id && l.b === linkSource)
				);
				if (!exists) {
					canvas.links = [...(canvas.links || []), { id: uid(), a: linkSource, b: block.id }];
					saveCanvas();
				}
				linkSource = null;
			}
			return;
		}
		e.stopPropagation();
		selectedId = block.id;
		if (!canvasEl) return;
		const rect = canvasEl.getBoundingClientRect();
		dragging = {
			id: block.id,
			offsetX: e.clientX - rect.left + canvasEl.scrollLeft - block.x,
			offsetY: e.clientY - rect.top + canvasEl.scrollTop - block.y,
		};
	}

	function onResizeMouseDown(e: MouseEvent, block: CanvasBloque, dir: string) {
		e.stopPropagation();
		resizing = {
			id: block.id,
			dir,
			startX: e.clientX,
			startY: e.clientY,
			startW: block.width,
			startH: block.height,
			startBX: block.x,
			startBY: block.y,
		};
	}

	function onWindowMouseMove(e: MouseEvent) {
		if (dragging && canvasEl) {
			const rect = canvasEl.getBoundingClientRect();
			const x = e.clientX - rect.left + canvasEl.scrollLeft - dragging.offsetX;
			const y = e.clientY - rect.top + canvasEl.scrollTop - dragging.offsetY;
			updateBlock(dragging.id, { x, y });
		}
		if (resizing) {
			const r = resizing;
			const dx = e.clientX - r.startX;
			const dy = e.clientY - r.startY;
			const block = canvas.bloques.find((b) => b.id === r.id);
			if (!block) return;
			let w = block.width;
			let h = block.height;
			let x = block.x;
			let y = block.y;
			if (resizing.dir.includes('e')) w = Math.max(120, resizing.startW + dx);
			if (resizing.dir.includes('s')) h = Math.max(80, resizing.startH + dy);
			if (resizing.dir.includes('w')) {
				w = Math.max(120, resizing.startW - dx);
				x = resizing.startBX + (resizing.startW - w);
			}
			if (resizing.dir.includes('n')) {
				h = Math.max(80, resizing.startH - dy);
				y = resizing.startBY + (resizing.startH - h);
			}
			updateBlock(resizing.id, { x, y, width: w, height: h });
		}
	}

	function onWindowMouseUp() {
		if (dragging) {
			dragging = null;
			saveCanvas();
		}
		if (resizing) {
			resizing = null;
			saveCanvas();
		}
	}

	async function renderizarDiagramas() {
		for (const b of canvas.bloques.filter((b) => b.tipo === 'diagrama')) {
			try {
				const id = 'mermaid-' + b.id;
				const { svg } = await mermaid.render(id, b.texto || 'graph TD\n  A[?]');
				diagramSvg[b.id] = svg;
			} catch (err) {
				diagramSvg[b.id] = `<div class="text-red-400 text-xs p-2">Diagrama inválido<br/>${(err as Error).message}</div>`;
			}
		}
	}

	$effect(() => {
		if (canvas.bloques.some((b) => b.tipo === 'diagrama')) {
			renderizarDiagramas();
		}
	});

	async function interpretar() {
		interpretando = true;
		try {
			interpretacion = await api.interpretarCanvas(tarea.id);
		} catch (e) {
			interpretacion = { ok: false, interpretacion: 'No pude interpretar el lienzo.', oportunidades: [], ideas: [], riesgos: [] };
		} finally {
			interpretando = false;
		}
	}

	function pathForLink(link: CanvasLink): string | null {
		const a = canvas.bloques.find((b) => b.id === link.a);
		const b = canvas.bloques.find((b) => b.id === link.b);
		if (!a || !b || !canvasEl) return null;
		const ax = a.x + a.width / 2;
		const ay = a.y + a.height / 2;
		const bx = b.x + b.width / 2;
		const by = b.y + b.height / 2;
		return `M ${ax} ${ay} L ${bx} ${by}`;
	}

	function tableRows(block: CanvasBloque): string[][] {
		if (block.contenido && Array.isArray(block.contenido.rows)) return block.contenido.rows;
		return [['', ''], ['', '']];
	}

	function updateTable(bloque: CanvasBloque, rows: string[][]) {
		updateBlock(bloque.id, { contenido: { rows } });
		saveCanvas();
	}

	function addTableRow(bloque: CanvasBloque) {
		const rows = tableRows(bloque);
		const cols = rows[0]?.length || 2;
		updateTable(bloque, [...rows, Array(cols).fill('')]);
	}

	function addTableCol(bloque: CanvasBloque) {
		const rows = tableRows(bloque).map((r) => [...r, '']);
		updateTable(bloque, rows);
	}
</script>

<svelte:window onmousemove={onWindowMouseMove} onmouseup={onWindowMouseUp} />

<div class="fixed inset-0 z-[80] flex flex-col bg-black/85 p-3 animate-fade-in" role="button" tabindex="-1" onclick={() => onClose()}>
	<div
		class="bg-card border border-border rounded-2xl w-full max-w-7xl mx-auto flex flex-col overflow-hidden shadow-2xl"
		style="height: calc(100vh - 24px)"
		onclick={(e) => e.stopPropagation()}
	>
		<div class="flex items-center justify-between px-4 py-3 border-b border-border bg-card2">
			<div class="flex items-center gap-2">
				<Workflow size={18} class="text-accent" />
				<span class="text-sm font-semibold text-text">Lienzo visual: {tarea.titulo}</span>
				<span class="text-[10px] text-muted">{canvas.bloques.length} bloques · {(canvas.links || []).length} enlaces</span>
			</div>
			<div class="flex items-center gap-2">
				<button
					onclick={() => (linkMode = !linkMode)}
					class="text-[10px] px-2 py-1.5 rounded-lg border flex items-center gap-1 {linkMode
						? 'bg-accent text-white border-accent'
						: 'bg-card border-border text-muted hover:text-text'}"
				>
					{linkMode ? 'Modo enlace' : 'Enlazar'}
					{#if linkSource}<span class="text-[9px] opacity-80">origen</span>{/if}
				</button>
				<button
					onclick={interpretar}
					disabled={interpretando}
					class="text-[10px] px-2.5 py-1.5 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 disabled:opacity-50 flex items-center gap-1"
				>
					{#if interpretando}<Loader2 size={10} class="animate-spin" />{:else}<Sparkles size={10} />{/if}
					Interpretar
				</button>
				<button onclick={onClose} class="p-1.5 rounded-lg text-muted hover:text-text hover:bg-card"><X size={18} /></button>
			</div>
		</div>

		<div class="flex items-center gap-2 px-4 py-2 border-b border-border bg-bg/50 overflow-x-auto">
			<span class="text-[10px] text-muted flex items-center gap-1"><MousePointer2 size={10} /> Herramienta:</span>
			{#each TIPOS as t}
				{@const Icon = t.icon}
				<button
					onclick={() => (selectedTipo = t.key)}
					class="text-[10px] px-2 py-1.5 rounded-lg border flex items-center gap-1 whitespace-nowrap {selectedTipo === t.key
						? 'bg-accent text-white border-accent'
						: 'bg-card border-border text-muted hover:text-text'}"
				>
					<Icon size={12} /> {t.label}
				</button>
			{/each}
			<div class="ml-auto flex items-center gap-1 text-[10px] text-muted">
				{#if guardando}<Loader2 size={10} class="animate-spin text-accent" />{/if}
				{guardando ? 'Guardando...' : 'Guardado'}
			</div>
		</div>

		<div class="flex-1 flex overflow-hidden">
			<div
				bind:this={canvasEl}
				class="flex-1 overflow-auto relative bg-bg"
				style="background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 20px 20px;"
				onclick={handleCanvasClick}
				role="button"
				tabindex="0"
			>
				<div class="relative" style="width: 3000px; height: 2000px;">
					<svg class="absolute inset-0 pointer-events-none" width="3000" height="2000">
						{#each canvas.links || [] as link}
							{@const d = pathForLink(link)}
							{#if d}<path {d} stroke="currentColor" stroke-width="2" class="text-accent/50" marker-end="url(#arrowhead)" />{/if}
						{/each}
						<defs>
							<marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
								<polygon points="0 0, 10 3.5, 0 7" class="fill-accent/50" />
							</marker>
						</defs>
					</svg>

					{#each canvas.bloques as bloque (bloque.id)}
						<div
							class="absolute group border rounded-xl shadow-sm flex flex-col overflow-hidden transition-shadow {selectedId === bloque.id
								? 'ring-2 ring-accent border-accent'
								: 'border-border hover:shadow-md'}"
							style="left: {bloque.x}px; top: {bloque.y}px; width: {bloque.width}px; height: {bloque.height}px;"
							onmousedown={(e) => onMouseDownBlock(e, bloque)}
						>
							<div class="flex items-center justify-between px-2 py-1 bg-card2 border-b border-border cursor-grab active:cursor-grabbing">
								<div class="flex items-center gap-1 text-[10px] text-muted">
									{#if bloque.tipo === 'texto'}<Type size={10} />{/if}
									{#if bloque.tipo === 'idea'}<Lightbulb size={10} class="text-amber-400" />{/if}
									{#if bloque.tipo === 'codigo'}<Code size={10} class="text-blue-400" />{/if}
									{#if bloque.tipo === 'diagrama'}<Workflow size={10} class="text-purple-400" />{/if}
									{#if bloque.tipo === 'imagen'}<Image size={10} class="text-pink-400" />{/if}
									{#if bloque.tipo === 'tabla'}<Table size={10} class="text-green-400" />{/if}
									<span class="capitalize">{bloque.tipo}</span>
								</div>
								<button
									onclick={(e) => {
										e.stopPropagation();
										deleteBlock(bloque.id);
									}}
									class="text-muted hover:text-red opacity-0 group-hover:opacity-100 transition-opacity"
								>
									<X size={12} />
								</button>
							</div>

							<div class="flex-1 overflow-auto p-2 bg-card">
								{#if bloque.tipo === 'diagrama'}
									<div class="text-[10px]">{@html diagramSvg[bloque.id] || ''}</div>
									<textarea
										class="w-full mt-1 bg-bg border border-border rounded px-2 py-1 text-[10px] text-text font-mono resize-none"
										style="height: calc(100% - 80px);"
										bind:value={bloque.texto}
										oninput={() => renderizarDiagramas()}
										onchange={saveCanvas}
									></textarea>
								{:else if bloque.tipo === 'imagen'}
									{#if bloque.texto?.startsWith('http')}
										<img src={bloque.texto} alt="" class="max-w-full max-h-[70%] object-contain rounded border border-border mb-1" />
									{/if}
									<input
										class="w-full bg-bg border border-border rounded px-2 py-1 text-[10px] text-text"
										placeholder="URL de imagen..."
										bind:value={bloque.texto}
										onchange={saveCanvas}
									/>
								{:else if bloque.tipo === 'tabla'}
									<table class="w-full text-[10px] border-collapse">
										<tbody>
											{#each tableRows(bloque) as row, ri}
												<tr>
													{#each row as cell, ci}
														<td class="border border-border p-1">
															<input
																class="w-full bg-transparent text-text outline-none"
																value={cell}
																oninput={(e) => {
																	const rows = tableRows(bloque);
																	rows[ri][ci] = (e.target as HTMLInputElement).value;
																	updateTable(bloque, rows);
																}}
															/>
														</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
									<div class="flex gap-1 mt-1">
										<button onclick={() => addTableRow(bloque)} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text">+ fila</button>
										<button onclick={() => addTableCol(bloque)} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text">+ col</button>
									</div>
								{:else if bloque.tipo === 'codigo'}
									<textarea
										class="w-full h-full bg-bg border border-border rounded px-2 py-1 text-[10px] text-text font-mono resize-none"
										bind:value={bloque.texto}
										onchange={saveCanvas}
									></textarea>
								{:else}
									<textarea
										class="w-full h-full bg-transparent text-[11px] text-text resize-none outline-none"
										placeholder={bloque.tipo === 'idea' ? 'Escribe tu idea...' : 'Escribe aquí...'}
										bind:value={bloque.texto}
										onchange={saveCanvas}
									></textarea>
								{/if}
							</div>

							<div class="absolute -bottom-1 -right-1 w-3 h-3 cursor-nwse-resize" onmousedown={(e) => onResizeMouseDown(e, bloque, 'se')}></div>
						</div>
					{/each}
				</div>
			</div>

			{#if interpretacion}
				<div class="w-80 border-l border-border bg-card2 p-3 overflow-y-auto flex flex-col gap-3">
					<div class="text-xs font-semibold text-text flex items-center gap-1.5">
						<Sparkles size={14} class="text-accent" /> Interpretación del agente
					</div>
					<div class="text-[11px] text-indigo-200 bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-2">
						{interpretacion.interpretacion}
					</div>
					{#if interpretacion.oportunidades.length > 0}
						<div>
							<div class="text-[10px] text-muted mb-1">Oportunidades</div>
							<ul class="space-y-1">
								{#each interpretacion.oportunidades as o}
									<li class="text-[11px] text-text bg-card border border-border rounded px-2 py-1">{o}</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if interpretacion.ideas.length > 0}
						<div>
							<div class="text-[10px] text-muted mb-1">Ideas sugeridas</div>
							<ul class="space-y-1">
								{#each interpretacion.ideas as idea}
									<li class="text-[11px] text-text bg-card border border-border rounded px-2 py-1">{idea}</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if interpretacion.riesgos.length > 0}
						<div>
							<div class="text-[10px] text-muted mb-1">Riesgos</div>
							<ul class="space-y-1">
								{#each interpretacion.riesgos as r}
									<li class="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded px-2 py-1">{r}</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>
