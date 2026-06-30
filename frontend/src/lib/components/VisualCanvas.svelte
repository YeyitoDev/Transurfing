<script lang="ts">
	import { X, Type, Lightbulb, Code, Image, Table, Workflow, Sparkles, Loader2, Save, MousePointer2, Star, Undo2, Clock, Bell, Terminal, LayoutGrid, History, Maximize2, Trash2, ZoomIn, ZoomOut } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import type { Tarea, TareaCanvas, CanvasBloque, CanvasLink } from '../types';
	import mermaid from 'mermaid';
	import { onMount } from 'svelte';

	let { tarea, onClose }: { tarea: Tarea; onClose: () => void } = $props();


	const TIPOS: { key: CanvasBloque['tipo']; label: string; icon: typeof Type }[] = [
		{ key: 'texto', label: 'Texto', icon: Type },
		{ key: 'idea', label: 'Idea', icon: Lightbulb },
		{ key: 'codigo', label: 'Código', icon: Code },
		{ key: 'json', label: 'JSON', icon: Code },
		{ key: 'curl', label: 'cURL', icon: Terminal },
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
		curl: { width: 360, height: 150, texto: 'curl -X GET https://api.ejemplo.com' },
		imagen: { width: 240, height: 160, texto: 'https://' },
		tabla: { width: 320, height: 160, texto: '' },
	};

	let canvas = $state<TareaCanvas>(
		tarea.canvas ? JSON.parse(JSON.stringify(tarea.canvas)) : { bloques: [], links: [] }
	);
	let selectedTipo = $state<CanvasBloque['tipo']>('texto');
	let dragging = $state<{ id: string; startX: number; startY: number } | null>(null);
	let resizing = $state<{ id: string; dir: string; startX: number; startY: number; startW: number; startH: number; startBX: number; startBY: number } | null>(null);
	let canvasEl: HTMLDivElement | null = $state(null);
	let diagramSvg = $state<Record<string, string>>({});
	let interpretacion = $state<import('../types').CanvasInterpretacion | null>(null);
	let interpretando = $state(false);
	let guardando = $state(false);
	let selectedId = $state<string | null>(null);
	let linkMode = $state(false);
	let linkSource = $state<string | null>(null);
	let undoStack = $state<TareaCanvas[]>([]);
	let pendingSnapshot = false;
	let reminderPickerId = $state<string | null>(null);
	let pickerFecha = $state('');
	let pickerRepeat = $state('none');
	let alarms = $state<{ id: string; texto: string; at: number }[]>([]);
	let selectedIds = $state<Record<string, boolean>>({});
	let zoom = $state(1);
	let radial = $state<{ x: number; y: number; cx: number; cy: number } | null>(null);
	let marquee = $state<{ x: number; y: number; w: number; h: number } | null>(null);
	let mergeTargetId = $state<string | null>(null);
	let showHistorial = $state(false);
	let showKanban = $state(false);
	let expandId = $state<string | null>(null);
	let contentEl: HTMLDivElement | null = $state(null);
	let dragMoved = false;
	let dragStarts: Record<string, { x: number; y: number }> = {};
	let marqueeStart: { x: number; y: number } | null = null;
	let bgModifier = false;

	function snapshot() {
		undoStack.push(JSON.parse(JSON.stringify(canvas)));
		if (undoStack.length > 50) undoStack.shift();
	}

	function undo() {
		const prev = undoStack.pop();
		if (!prev) return;
		canvas = prev;
		clearSelection();
		saveCanvas();
	}

	function toggleImportante(id: string) {
		const actual = canvas.bloques.find((b) => b.id === id)?.importante;
		snapshot();
		updateBlock(id, { importante: !actual });
		saveCanvas();
	}

	function onWindowKeyDown(e: KeyboardEvent) {
		const t = e.target as HTMLElement | null;
		const editing = !!t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable);
		if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !editing) {
			e.preventDefault();
			undo();
			return;
		}
		if (e.key === 'Delete' && !editing && Object.keys(selectedIds).length) {
			e.preventDefault();
			deleteSelection();
			return;
		}
		if (e.key === 'Escape') {
			closeRadial();
			showHistorial = false;
			showKanban = false;
			expandId = null;
			reminderPickerId = null;
		}
	}

	// ---------- Recordatorios ----------
	function fmtShort(ts: number): string {
		const d = new Date(ts);
		const hoy = new Date();
		const mismoDia = d.getFullYear() === hoy.getFullYear() && d.getMonth() === hoy.getMonth() && d.getDate() === hoy.getDate();
		const hm = d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
		return mismoDia ? hm : d.toLocaleDateString('es', { day: '2-digit', month: 'short' }) + ' ' + hm;
	}

	function fmtWhen(ts: number): string {
		return new Date(ts).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
	}

	function toLocalInput(ts: number): string {
		const d = new Date(ts);
		const p = (n: number) => String(n).padStart(2, '0');
		return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
	}

	function reminderTexto(b: CanvasBloque): string {
		const t = (b.texto || '').replace(/\s+/g, ' ').trim();
		return t ? (t.length > 48 ? t.slice(0, 48) + '…' : t) : b.tipo;
	}

	function pedirPermisoNotif() {
		try {
			if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
		} catch (e) {
			/* noop */
		}
	}

	function openReminderPicker(b: CanvasBloque) {
		reminderPickerId = b.id;
		const base = b.recordatorio?.at ?? Date.now() + 3600000;
		pickerFecha = toLocalInput(base);
		pickerRepeat = b.recordatorio?.repeat ?? 'none';
	}

	function setQuickReminder(id: string, minutos: number) {
		snapshot();
		updateBlock(id, { recordatorio: { at: Date.now() + minutos * 60000, repeat: 'none', done: false } });
		pedirPermisoNotif();
		saveCanvas();
		reminderPickerId = null;
	}

	function saveReminder(id: string, valor: string, repeat: string) {
		const at = new Date(valor).getTime();
		if (isNaN(at)) return;
		snapshot();
		updateBlock(id, { recordatorio: { at, repeat, done: false } });
		pedirPermisoNotif();
		saveCanvas();
		reminderPickerId = null;
	}

	function removeReminder(id: string) {
		snapshot();
		updateBlock(id, { recordatorio: null });
		saveCanvas();
		reminderPickerId = null;
	}

	function nextOccurrence(at: number, repeat: string): number {
		const d = new Date(at);
		const ahora = Date.now();
		const step = () => {
			if (repeat === 'daily') d.setDate(d.getDate() + 1);
			else if (repeat === 'weekly') d.setDate(d.getDate() + 7);
			else if (repeat === 'monthly') d.setMonth(d.getMonth() + 1);
			else if (repeat === 'weekdays') {
				do {
					d.setDate(d.getDate() + 1);
				} while (d.getDay() === 0 || d.getDay() === 6);
			} else d.setFullYear(d.getFullYear() + 50);
		};
		do {
			step();
		} while (d.getTime() <= ahora);
		return d.getTime();
	}

	function playBeep() {
		try {
			const Ctx = window.AudioContext || (window as any).webkitAudioContext;
			if (!Ctx) return;
			const ctx = new Ctx();
			[880, 1175, 1568].forEach((f, i) => {
				const o = ctx.createOscillator();
				const g = ctx.createGain();
				const at = ctx.currentTime + i * 0.18;
				o.type = 'sine';
				o.frequency.value = f;
				g.gain.setValueAtTime(0.0001, at);
				g.gain.exponentialRampToValueAtTime(0.22, at + 0.02);
				g.gain.exponentialRampToValueAtTime(0.0001, at + 0.16);
				o.connect(g);
				g.connect(ctx.destination);
				o.start(at);
				o.stop(at + 0.18);
			});
		} catch (e) {
			/* noop */
		}
	}

	function notifShow(titulo: string, cuerpo: string) {
		try {
			if ('Notification' in window && Notification.permission === 'granted') new Notification(titulo, { body: cuerpo });
		} catch (e) {
			/* noop */
		}
	}

	function checkReminders() {
		const ahora = Date.now();
		const due = canvas.bloques.filter(
			(b) => b.recordatorio && !b.recordatorio.done && typeof b.recordatorio.at === 'number' && b.recordatorio.at <= ahora
		);
		if (!due.length) return;
		const disparados = due.map((b) => ({ id: b.id, texto: reminderTexto(b), at: b.recordatorio!.at }));
		for (const b of due) {
			const r = b.recordatorio!;
			if (r.repeat && r.repeat !== 'none') {
				updateBlock(b.id, { recordatorio: { at: nextOccurrence(r.at, r.repeat), repeat: r.repeat, done: false } });
			} else {
				updateBlock(b.id, { recordatorio: { at: r.at, repeat: r.repeat, done: true } });
			}
		}
		saveCanvas();
		disparados.forEach((d) => notifShow('⏰ Recordatorio', d.texto));
		playBeep();
		alarms = [...alarms, ...disparados];
	}

	function snoozeAlarm(a: { id: string; texto: string; at: number }, minutos: number) {
		updateBlock(a.id, { recordatorio: { at: Date.now() + minutos * 60000, repeat: 'none', done: false } });
		saveCanvas();
		alarms = alarms.filter((x) => x !== a);
	}

	function dismissAlarm(a: { id: string; texto: string; at: number }) {
		alarms = alarms.filter((x) => x !== a);
	}

	// ---------- Imágenes ----------
	function fileToDataURL(file: File, cb: (url: string) => void) {
		const reader = new FileReader();
		reader.onload = () => {
			const img = new window.Image();
			img.onload = () => {
				const MAX = 1400;
				const scale = Math.min(1, MAX / Math.max(img.width, img.height));
				const w = Math.max(1, Math.round(img.width * scale));
				const hh = Math.max(1, Math.round(img.height * scale));
				const c = document.createElement('canvas');
				c.width = w;
				c.height = hh;
				const ctx = c.getContext('2d');
				if (ctx) {
					ctx.drawImage(img, 0, 0, w, hh);
					cb(c.toDataURL('image/jpeg', 0.82));
				} else {
					cb(reader.result as string);
				}
			};
			img.onerror = () => cb(reader.result as string);
			img.src = reader.result as string;
		};
		reader.readAsDataURL(file);
	}

	function setImagen(id: string, file: File) {
		fileToDataURL(file, (url) => {
			snapshot();
			updateBlock(id, { texto: url });
			saveCanvas();
		});
	}

	function onImagenPaste(id: string, e: ClipboardEvent) {
		const items = e.clipboardData?.items;
		if (!items) return;
		for (let i = 0; i < items.length; i++) {
			const it = items[i];
			if (it.kind === 'file' && it.type.startsWith('image/')) {
				const f = it.getAsFile();
				if (f) {
					e.preventDefault();
					setImagen(id, f);
					return;
				}
			}
		}
	}

	onMount(() => {
		checkReminders();
		const loop = setInterval(checkReminders, 20000);
		return () => clearInterval(loop);
	});

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

	function toContent(clientX: number, clientY: number) {
		if (!canvasEl) return { x: 0, y: 0 };
		const rect = canvasEl.getBoundingClientRect();
		return {
			x: (clientX - rect.left + canvasEl.scrollLeft) / zoom,
			y: (clientY - rect.top + canvasEl.scrollTop) / zoom
		};
	}

	function logChange(action: string, detail = '') {
		const entry = { id: uid(), ts: Date.now(), action, detail };
		canvas.log = [entry, ...(canvas.log || [])].slice(0, 300);
	}

	function clearSelection() {
		selectedIds = {};
		selectedId = null;
	}

	function selectOnly(id: string) {
		selectedIds = { [id]: true };
		selectedId = id;
	}

	function addBlockAt(clientX: number, clientY: number, tipo: CanvasBloque['tipo']) {
		const def = DEFAULTS[tipo];
		const p = toContent(clientX, clientY);
		const b: CanvasBloque = {
			id: uid(),
			tipo,
			x: Math.round(p.x - def.width / 2),
			y: Math.round(p.y - def.height / 2),
			width: def.width,
			height: def.height,
			texto: def.texto
		};
		snapshot();
		canvas.bloques = [...canvas.bloques, b];
		logChange('Bloque añadido', tipo);
		selectOnly(b.id);
		saveCanvas();
		return b;
	}

	function combineBlocks(targetId: string, sourceId: string) {
		if (targetId === sourceId) return;
		const t = canvas.bloques.find((b) => b.id === targetId);
		const s = canvas.bloques.find((b) => b.id === sourceId);
		if (!t || !s) return;
		snapshot();
		const src = (s.texto || '').trim();
		if (src) {
			const base = (t.texto || '').replace(/\s+$/, '');
			updateBlock(targetId, { texto: base ? base + '\n\n' + src : src });
		}
		canvas.bloques = canvas.bloques.filter((b) => b.id !== sourceId);
		canvas.links = (canvas.links || []).filter((l) => l.a !== sourceId && l.b !== sourceId);
		logChange('Bloques combinados');
		selectOnly(targetId);
		saveCanvas();
	}

	function openRadial(clientX: number, clientY: number) {
		const p = toContent(clientX, clientY);
		radial = { x: clientX, y: clientY, cx: p.x, cy: p.y };
	}

	function closeRadial() {
		radial = null;
	}

	function radialPick(tipo: CanvasBloque['tipo']) {
		if (!radial) return;
		const def = DEFAULTS[tipo];
		const b: CanvasBloque = {
			id: uid(),
			tipo,
			x: Math.round(radial.cx - def.width / 2),
			y: Math.round(radial.cy - def.height / 2),
			width: def.width,
			height: def.height,
			texto: def.texto
		};
		snapshot();
		canvas.bloques = [...canvas.bloques, b];
		logChange('Bloque añadido', tipo);
		selectOnly(b.id);
		saveCanvas();
		closeRadial();
	}

	function setZoom(z: number) {
		zoom = Math.min(2.5, Math.max(0.3, Math.round(z * 100) / 100));
	}
	function zoomIn() {
		setZoom(zoom * 1.2);
	}
	function zoomOut() {
		setZoom(zoom / 1.2);
	}
	function resetZoom() {
		setZoom(1);
	}
	function fitView() {
		if (!canvasEl || !canvas.bloques.length) {
			setZoom(1);
			return;
		}
		let minX = Infinity,
			minY = Infinity,
			maxX = -Infinity,
			maxY = -Infinity;
		for (const b of canvas.bloques) {
			minX = Math.min(minX, b.x);
			minY = Math.min(minY, b.y);
			maxX = Math.max(maxX, b.x + b.width);
			maxY = Math.max(maxY, b.y + b.height);
		}
		const pad = 80;
		const bw = maxX - minX + pad * 2;
		const bh = maxY - minY + pad * 2;
		const z = Math.min(canvasEl.clientWidth / bw, canvasEl.clientHeight / bh);
		setZoom(z);
		requestAnimationFrame(() => {
			if (!canvasEl) return;
			canvasEl.scrollLeft = Math.max(0, (minX - pad) * zoom);
			canvasEl.scrollTop = Math.max(0, (minY - pad) * zoom);
		});
	}
	function onCanvasWheel(e: WheelEvent) {
		if (e.ctrlKey || e.metaKey) {
			e.preventDefault();
			setZoom(zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1));
		}
	}

	const KAN: { key: 'todo' | 'doing' | 'done'; label: string }[] = [
		{ key: 'todo', label: 'Por hacer' },
		{ key: 'doing', label: 'En progreso' },
		{ key: 'done', label: 'Hecho' }
	];
	function kanbanItems(status: 'todo' | 'doing' | 'done') {
		return canvas.bloques.filter((b) => b.kanban === status);
	}
	function setKanban(id: string, status: 'todo' | 'doing' | 'done' | null) {
		snapshot();
		updateBlock(id, { kanban: status });
		logChange(status ? 'Enviado a Kanban' : 'Quitado del Kanban', status || '');
		saveCanvas();
	}

	function formatJson(b: CanvasBloque) {
		try {
			const txt = JSON.stringify(JSON.parse(b.texto || 'null'), null, 2);
			updateBlock(b.id, { texto: txt });
			saveCanvas();
		} catch (err) {
			/* JSON inválido: ignorar */
		}
	}
	function onCodeKeydown(e: KeyboardEvent, b: CanvasBloque) {
		if (e.key === 'Tab') {
			e.preventDefault();
			const ta = e.target as HTMLTextAreaElement;
			const s = ta.selectionStart;
			const en = ta.selectionEnd;
			ta.value = ta.value.slice(0, s) + '  ' + ta.value.slice(en);
			ta.selectionStart = ta.selectionEnd = s + 2;
			updateBlock(b.id, { texto: ta.value });
		}
	}

	function selectInRect(x: number, y: number, w: number, h: number) {
		const sel: Record<string, boolean> = {};
		for (const b of canvas.bloques) {
			if (b.x + b.width >= x && b.x <= x + w && b.y + b.height >= y && b.y <= y + h) sel[b.id] = true;
		}
		selectedIds = sel;
		selectedId = Object.keys(sel)[0] ?? null;
	}

	function onBgMouseDown(e: MouseEvent) {
		if (e.target !== contentEl) return;
		closeRadial();
		marqueeStart = toContent(e.clientX, e.clientY);
		marquee = null;
		bgModifier = e.ctrlKey || e.metaKey || e.altKey;
		if (!e.shiftKey) clearSelection();
	}

	function deleteBlock(id: string) {
		snapshot();
		canvas.bloques = canvas.bloques.filter((b) => b.id !== id);
		canvas.links = (canvas.links || []).filter((l) => l.a !== id && l.b !== id);
		if (selectedIds[id]) {
			const { [id]: _omit, ...rest } = selectedIds;
			selectedIds = rest;
		}
		if (selectedId === id) selectedId = null;
		delete diagramSvg[id];
		logChange('Bloque eliminado');
		saveCanvas();
	}

	function deleteSelection() {
		const ids = Object.keys(selectedIds);
		if (!ids.length) return;
		snapshot();
		const set = new Set(ids);
		canvas.bloques = canvas.bloques.filter((b) => !set.has(b.id));
		canvas.links = (canvas.links || []).filter((l) => !set.has(l.a) && !set.has(l.b));
		ids.forEach((id) => delete diagramSvg[id]);
		clearSelection();
		logChange('Selección eliminada', ids.length + ' bloques');
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
					snapshot();
					canvas.links = [...(canvas.links || []), { id: uid(), a: linkSource, b: block.id }];
					saveCanvas();
				}
				linkSource = null;
			}
			return;
		}
		e.stopPropagation();
		closeRadial();
		if (!selectedIds[block.id]) {
			if (!e.shiftKey) clearSelection();
			selectedIds = { ...selectedIds, [block.id]: true };
		}
		selectedId = block.id;
		if (!canvasEl) return;
		pendingSnapshot = true;
		dragMoved = false;
		const ids = Object.keys(selectedIds);
		dragStarts = {};
		for (const id of ids) {
			const b = canvas.bloques.find((x) => x.id === id);
			if (b) dragStarts[id] = { x: b.x, y: b.y };
		}
		dragging = { id: block.id, startX: e.clientX, startY: e.clientY };
	}

	function onResizeMouseDown(e: MouseEvent, block: CanvasBloque, dir: string) {
		e.stopPropagation();
		pendingSnapshot = true;
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
		if ((dragging || resizing) && pendingSnapshot) {
			snapshot();
			pendingSnapshot = false;
		}
		if (dragging) {
			const ddx = (e.clientX - dragging.startX) / zoom;
			const ddy = (e.clientY - dragging.startY) / zoom;
			if (Math.abs(e.clientX - dragging.startX) > 2 || Math.abs(e.clientY - dragging.startY) > 2) dragMoved = true;
			for (const id of Object.keys(dragStarts)) {
				const st = dragStarts[id];
				updateBlock(id, { x: Math.max(0, st.x + ddx), y: Math.max(0, st.y + ddy) });
			}
			if (Object.keys(dragStarts).length === 1) {
				const p = toContent(e.clientX, e.clientY);
				const over = canvas.bloques.find(
					(b) => b.id !== dragging!.id && p.x >= b.x && p.x <= b.x + b.width && p.y >= b.y && p.y <= b.y + b.height
				);
				mergeTargetId = over ? over.id : null;
			}
		}
		if (resizing) {
			const r = resizing;
			const dx = (e.clientX - r.startX) / zoom;
			const dy = (e.clientY - r.startY) / zoom;
			const block = canvas.bloques.find((b) => b.id === r.id);
			if (!block) return;
			let w = block.width;
			let h = block.height;
			let x = block.x;
			let y = block.y;
			if (r.dir.includes('e')) w = Math.max(120, r.startW + dx);
			if (r.dir.includes('s')) h = Math.max(80, r.startH + dy);
			if (r.dir.includes('w')) {
				w = Math.max(120, r.startW - dx);
				x = r.startBX + (r.startW - w);
			}
			if (r.dir.includes('n')) {
				h = Math.max(80, r.startH - dy);
				y = r.startBY + (r.startH - h);
			}
			updateBlock(r.id, { x, y, width: w, height: h });
		}
		if (marqueeStart) {
			const p = toContent(e.clientX, e.clientY);
			const x = Math.min(marqueeStart.x, p.x);
			const y = Math.min(marqueeStart.y, p.y);
			const w = Math.abs(p.x - marqueeStart.x);
			const h = Math.abs(p.y - marqueeStart.y);
			if (w > 3 || h > 3) {
				marquee = { x, y, w, h };
				selectInRect(x, y, w, h);
			}
		}
	}

	function onWindowMouseUp(e: MouseEvent) {
		if (dragging) {
			if (mergeTargetId && Object.keys(dragStarts).length === 1 && dragMoved) {
				combineBlocks(mergeTargetId, dragging.id);
			} else {
				for (const id of Object.keys(dragStarts)) {
					const b = canvas.bloques.find((x) => x.id === id);
					if (b) updateBlock(id, { x: Math.round(b.x), y: Math.round(b.y) });
				}
				if (dragMoved) saveCanvas();
			}
			dragging = null;
			mergeTargetId = null;
			dragStarts = {};
		}
		if (resizing) {
			resizing = null;
			saveCanvas();
		}
		if (marqueeStart) {
			const moved = !!marquee;
			marquee = null;
			marqueeStart = null;
			if (!moved) {
				if (bgModifier) {
					openRadial(e.clientX, e.clientY);
				} else {
					addBlockAt(e.clientX, e.clientY, selectedTipo);
				}
			}
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

<svelte:window onmousemove={onWindowMouseMove} onmouseup={onWindowMouseUp} onkeydown={onWindowKeyDown} />

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
					onclick={undo}
					disabled={undoStack.length === 0}
					title="Deshacer (Ctrl+Z)"
					class="text-[10px] px-2 py-1.5 rounded-lg border bg-card border-border text-muted hover:text-text disabled:opacity-40 flex items-center gap-1"
				>
					<Undo2 size={10} /> Deshacer
				</button>
				<button
					onclick={() => (linkMode = !linkMode)}
					class="text-[10px] px-2 py-1.5 rounded-lg border flex items-center gap-1 {linkMode
						? 'bg-accent text-white border-accent'
						: 'bg-card border-border text-muted hover:text-text'}"
				>
					{linkMode ? 'Modo enlace' : 'Enlazar'}
					{#if linkSource}<span class="text-[9px] opacity-80">origen</span>{/if}
				</button>
				<div class="flex items-center gap-0.5 bg-card border border-border rounded-lg px-1">
					<button onclick={zoomOut} title="Alejar" class="p-1 text-muted hover:text-text"><ZoomOut size={12} /></button>
					<button onclick={resetZoom} title="Restablecer zoom" class="text-[10px] text-muted hover:text-text w-9 text-center">{Math.round(zoom * 100)}%</button>
					<button onclick={zoomIn} title="Acercar" class="p-1 text-muted hover:text-text"><ZoomIn size={12} /></button>
					<button onclick={fitView} title="Ajustar a contenido" class="p-1 text-muted hover:text-text"><Maximize2 size={12} /></button>
				</div>
				<button onclick={() => (showKanban = true)} title="Kanban de ideas" class="text-[10px] px-2 py-1.5 rounded-lg border bg-card border-border text-muted hover:text-text flex items-center gap-1"><LayoutGrid size={10} /> Kanban</button>
				<button onclick={() => (showHistorial = true)} title="Historial" class="text-[10px] px-2 py-1.5 rounded-lg border bg-card border-border text-muted hover:text-text flex items-center gap-1"><History size={10} /> Historial</button>
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
				style="background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: {20 * zoom}px {20 * zoom}px;"
				onwheel={onCanvasWheel}
			>
				<div style="width: {3000 * zoom}px; height: {2000 * zoom}px;">
				<div
					bind:this={contentEl}
					class="relative origin-top-left"
					style="width: 3000px; height: 2000px; transform: scale({zoom});"
					onmousedown={onBgMouseDown}
					role="presentation"
				>
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
							class="absolute group border rounded-xl shadow-sm flex flex-col overflow-hidden transition-shadow {mergeTargetId === bloque.id
								? 'ring-2 ring-emerald-400 border-emerald-400'
								: selectedIds[bloque.id]
									? 'ring-2 ring-accent border-accent'
									: bloque.importante
										? 'border-amber-400/60 ring-1 ring-amber-400/40 hover:shadow-md'
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
									{#if bloque.recordatorio && !bloque.recordatorio.done}
										<span class="flex items-center gap-0.5 text-[9px] text-emerald-400" title={fmtWhen(bloque.recordatorio.at)}>
											<Clock size={9} /> {fmtShort(bloque.recordatorio.at)}
										</span>
									{/if}
									{#if bloque.kanban}
										<span class="flex items-center gap-0.5 text-[9px] text-purple-300" title="Kanban"><LayoutGrid size={9} /> {bloque.kanban}</span>
									{/if}
								</div>
								<div class="flex items-center gap-1">
									<button
										onclick={(e) => {
											e.stopPropagation();
											if (reminderPickerId === bloque.id) reminderPickerId = null;
											else openReminderPicker(bloque);
										}}
										class="{bloque.recordatorio && !bloque.recordatorio.done ? 'text-emerald-400' : 'text-muted hover:text-emerald-400 opacity-0 group-hover:opacity-100'} transition-all"
										title="Recordatorio"
									>
										<Clock size={12} />
									</button>
									<button
										onclick={(e) => {
											e.stopPropagation();
											toggleImportante(bloque.id);
										}}
										class="{bloque.importante ? 'text-amber-400' : 'text-muted hover:text-amber-400 opacity-0 group-hover:opacity-100'} transition-all"
										title={bloque.importante ? 'Quitar importante' : 'Marcar como importante'}
									>
										<Star size={12} fill={bloque.importante ? 'currentColor' : 'none'} />
									</button>
									<button
										onclick={(e) => {
											e.stopPropagation();
											expandId = bloque.id;
										}}
										class="text-muted hover:text-text opacity-0 group-hover:opacity-100 transition-opacity"
										title="Expandir"
									>
										<Maximize2 size={12} />
									</button>
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
									{#if bloque.texto?.startsWith('http') || bloque.texto?.startsWith('data:')}
										<img src={bloque.texto} alt="" class="max-w-full max-h-[55%] object-contain rounded border border-border mb-1" />
									{/if}
									<input
										class="w-full bg-bg border border-border rounded px-2 py-1 text-[10px] text-text mb-1"
										placeholder="URL de imagen (o pega/sube)"
										bind:value={bloque.texto}
										onchange={saveCanvas}
										onpaste={(e) => onImagenPaste(bloque.id, e)}
										onmousedown={(e) => e.stopPropagation()}
									/>
									<label class="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text cursor-pointer w-fit" onmousedown={(e) => e.stopPropagation()}>
										<Image size={9} /> Subir imagen
										<input
											type="file"
											accept="image/*"
											class="hidden"
											onchange={(e) => {
												const inp = e.target as HTMLInputElement;
												const f = inp.files && inp.files[0];
												if (f) setImagen(bloque.id, f);
												inp.value = '';
											}}
										/>
									</label>
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
								{:else if bloque.tipo === 'codigo' || bloque.tipo === 'json' || bloque.tipo === 'curl'}
									<div class="flex flex-col h-full gap-1">
										<textarea
											class="w-full flex-1 bg-bg border border-border rounded px-2 py-1 text-[10px] text-text font-mono resize-none"
											spellcheck="false"
											bind:value={bloque.texto}
											onkeydown={(e) => onCodeKeydown(e, bloque)}
											onchange={saveCanvas}
											onmousedown={(e) => e.stopPropagation()}
										></textarea>
										{#if bloque.tipo === 'json'}
											<button onclick={() => formatJson(bloque)} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text w-fit">Formatear JSON</button>
										{/if}
									</div>
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
					{#if marquee}
						<div class="absolute border-2 border-accent/70 bg-accent/10 pointer-events-none rounded" style="left: {marquee.x}px; top: {marquee.y}px; width: {marquee.w}px; height: {marquee.h}px;"></div>
					{/if}
				</div>
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

	{#if radial}
		<div class="fixed inset-0 z-[86]" role="button" tabindex="-1" onclick={(e) => { e.stopPropagation(); closeRadial(); }}>
			<div
				class="absolute bg-card border border-border rounded-xl shadow-2xl p-1 grid grid-cols-2 gap-1"
				style="left: {radial.x}px; top: {radial.y}px;"
				role="menu"
				tabindex="-1"
				onclick={(e) => e.stopPropagation()}
			>
				{#each TIPOS as t}
					{@const Icon = t.icon}
					<button onclick={() => radialPick(t.key)} class="text-[10px] px-2 py-1.5 rounded-lg bg-card2 border border-border text-text hover:border-accent flex items-center gap-1"><Icon size={12} /> {t.label}</button>
				{/each}
			</div>
		</div>
	{/if}

	{#if Object.keys(selectedIds).length > 1}
		<div class="fixed bottom-4 left-1/2 -translate-x-1/2 z-[85] bg-card border border-border rounded-full shadow-2xl px-3 py-1.5 flex items-center gap-2" role="toolbar" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<span class="text-[11px] text-text">{Object.keys(selectedIds).length} seleccionados</span>
			<button onclick={deleteSelection} class="text-[10px] px-2 py-1 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 flex items-center gap-1"><Trash2 size={11} /> Eliminar</button>
		</div>
	{/if}

	{#if showKanban}
		<div class="fixed inset-0 z-[87] flex items-center justify-center bg-black/60 p-4" role="button" tabindex="-1" onclick={(e) => { e.stopPropagation(); showKanban = false; }}>
			<div class="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()}>
				<div class="flex items-center justify-between px-4 py-3 border-b border-border bg-card2">
					<div class="text-sm font-semibold text-text flex items-center gap-2"><LayoutGrid size={16} class="text-accent" /> Kanban de ideas</div>
					<button onclick={() => (showKanban = false)} class="p-1 text-muted hover:text-text"><X size={16} /></button>
				</div>
				<div class="flex-1 overflow-auto p-3 grid grid-cols-3 gap-3">
					{#each KAN as col, ci}
						<div class="bg-bg border border-border rounded-xl p-2 flex flex-col gap-2">
							<div class="text-[11px] font-semibold text-muted flex items-center justify-between"><span>{col.label}</span><span>{kanbanItems(col.key).length}</span></div>
							{#each kanbanItems(col.key) as b}
								<div class="bg-card border border-border rounded-lg p-2">
									<div class="text-[11px] text-text line-clamp-3">{b.texto || b.tipo}</div>
									<div class="flex items-center justify-between mt-1.5">
										<div class="flex gap-1">
											{#if ci > 0}<button onclick={() => setKanban(b.id, KAN[ci - 1].key)} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text">←</button>{/if}
											{#if ci < KAN.length - 1}<button onclick={() => setKanban(b.id, KAN[ci + 1].key)} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text">→</button>{/if}
										</div>
										<button onclick={() => setKanban(b.id, null)} class="text-[9px] text-red-400 hover:underline">Quitar</button>
									</div>
								</div>
							{/each}
							{#if kanbanItems(col.key).length === 0}<div class="text-[10px] text-muted text-center py-2">Vacío</div>{/if}
						</div>
					{/each}
				</div>
				{#if canvas.bloques.some((b) => !b.kanban)}
					<div class="border-t border-border p-2 max-h-32 overflow-auto">
						<div class="text-[10px] text-muted mb-1">Sin asignar</div>
						<div class="flex flex-wrap gap-1">
							{#each canvas.bloques.filter((b) => !b.kanban) as b}
								<button onclick={() => setKanban(b.id, 'todo')} class="text-[9px] px-1.5 py-0.5 rounded bg-card2 border border-border text-muted hover:text-text">+ {(b.texto || b.tipo).slice(0, 18)}</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	{#if showHistorial}
		<div class="fixed inset-0 z-[87] flex items-center justify-center bg-black/60 p-4" role="button" tabindex="-1" onclick={(e) => { e.stopPropagation(); showHistorial = false; }}>
			<div class="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] overflow-hidden flex flex-col" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()}>
				<div class="flex items-center justify-between px-4 py-3 border-b border-border bg-card2">
					<div class="text-sm font-semibold text-text flex items-center gap-2"><History size={16} class="text-accent" /> Historial</div>
					<button onclick={() => (showHistorial = false)} class="p-1 text-muted hover:text-text"><X size={16} /></button>
				</div>
				<div class="flex-1 overflow-auto p-3 flex flex-col gap-1">
					{#if (canvas.log || []).length === 0}
						<div class="text-[11px] text-muted text-center py-4">Sin cambios registrados.</div>
					{:else}
						{#each canvas.log || [] as entry}
							<div class="flex items-start gap-2 text-[11px]">
								<span class="text-[9px] text-muted whitespace-nowrap pt-0.5">{fmtShort(entry.ts)}</span>
								<span class="text-text">{entry.action}{#if entry.detail} <span class="text-muted">· {entry.detail}</span>{/if}</span>
							</div>
						{/each}
					{/if}
				</div>
			</div>
		</div>
	{/if}

	{#if expandId}
		{@const eb = canvas.bloques.find((b) => b.id === expandId)}
		<div class="fixed inset-0 z-[89] flex items-center justify-center bg-black/70 p-4" role="button" tabindex="-1" onclick={(e) => { e.stopPropagation(); expandId = null; }}>
			<div class="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-3xl h-[80vh] flex flex-col overflow-hidden" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()}>
				<div class="flex items-center justify-between px-4 py-3 border-b border-border bg-card2">
					<div class="text-sm font-semibold text-text capitalize flex items-center gap-2"><Maximize2 size={16} class="text-accent" /> {eb?.tipo ?? 'Bloque'}</div>
					<button onclick={() => (expandId = null)} class="p-1 text-muted hover:text-text"><X size={16} /></button>
				</div>
				{#if eb}
					<textarea class="flex-1 w-full bg-bg p-4 text-sm text-text resize-none outline-none font-mono" bind:value={eb.texto} onchange={saveCanvas}></textarea>
				{/if}
			</div>
		</div>
	{/if}

	{#if reminderPickerId}
		{@const rb = canvas.bloques.find((b) => b.id === reminderPickerId)}
		<div
			class="fixed inset-0 z-[88] flex items-center justify-center bg-black/50"
			role="button"
			tabindex="-1"
			onclick={(e) => {
				e.stopPropagation();
				reminderPickerId = null;
			}}
		>
			<div class="bg-card border border-border rounded-xl shadow-2xl w-72 p-3 flex flex-col gap-2" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()}>
				<div class="text-xs font-semibold text-text flex items-center gap-1.5"><Bell size={14} class="text-accent" /> Recordatorio</div>
				{#if rb}<div class="text-[10px] text-muted truncate">{reminderTexto(rb)}</div>{/if}
				<div class="flex gap-1">
					<button class="flex-1 text-[10px] px-2 py-1 rounded bg-card2 border border-border text-text hover:border-accent" onclick={() => reminderPickerId && setQuickReminder(reminderPickerId, 15)}>15 min</button>
					<button class="flex-1 text-[10px] px-2 py-1 rounded bg-card2 border border-border text-text hover:border-accent" onclick={() => reminderPickerId && setQuickReminder(reminderPickerId, 60)}>1 h</button>
					<button class="flex-1 text-[10px] px-2 py-1 rounded bg-card2 border border-border text-text hover:border-accent" onclick={() => reminderPickerId && setQuickReminder(reminderPickerId, 180)}>3 h</button>
				</div>
				<label class="text-[10px] text-muted">Fecha y hora</label>
				<input type="datetime-local" class="bg-bg border border-border rounded px-2 py-1 text-[11px] text-text" bind:value={pickerFecha} />
				<label class="text-[10px] text-muted">Repetir</label>
				<select class="bg-bg border border-border rounded px-2 py-1 text-[11px] text-text" bind:value={pickerRepeat}>
					<option value="none">Una vez</option>
					<option value="daily">Cada día</option>
					<option value="weekdays">Días laborables</option>
					<option value="weekly">Cada semana</option>
					<option value="monthly">Cada mes</option>
				</select>
				<div class="flex justify-between items-center mt-1">
					{#if rb?.recordatorio}
						<button class="text-[10px] text-red-400 hover:underline" onclick={() => reminderPickerId && removeReminder(reminderPickerId)}>Quitar</button>
					{:else}
						<span></span>
					{/if}
					<button class="text-[10px] px-3 py-1 rounded bg-accent text-white" onclick={() => reminderPickerId && saveReminder(reminderPickerId, pickerFecha, pickerRepeat)}>Guardar</button>
				</div>
			</div>
		</div>
	{/if}

	{#if alarms.length}
		<div class="fixed bottom-4 right-4 z-[90] w-72 bg-card border border-amber-400/40 rounded-xl shadow-2xl p-3 flex flex-col gap-2" role="alert" onclick={(e) => e.stopPropagation()}>
			<div class="text-xs font-semibold text-amber-300 flex items-center gap-1.5"><Bell size={14} /> Recordatorios</div>
			{#each alarms as a}
				<div class="bg-card2 border border-border rounded-lg p-2">
					<div class="text-[11px] text-text">{a.texto}</div>
					<div class="text-[9px] text-muted flex items-center gap-1 mt-0.5"><Clock size={9} /> {fmtWhen(a.at)}</div>
					<div class="flex gap-1 mt-1.5">
						<button class="text-[9px] px-2 py-0.5 rounded bg-card border border-border text-muted hover:text-text" onclick={() => snoozeAlarm(a, 5)}>Posponer 5 min</button>
						<button class="text-[9px] px-2 py-0.5 rounded bg-accent text-white" onclick={() => dismissAlarm(a)}>Listo</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
