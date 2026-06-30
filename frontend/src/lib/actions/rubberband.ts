/**
 * Acción Svelte para selección por arrastre (rubber-band / marquee).
 *
 * Uso:
 *   <div use:rubberband={{ itemSelector: '[data-taskid]', onChange: (ids) => seleccion = ids }}>
 *     {#each items as it}<div data-taskid={it.id}>...</div>{/each}
 *   </div>
 *
 * - El arrastre (>6px) dibuja un recuadro y selecciona los items que toca.
 * - Un clic simple (sin arrastre) NO selecciona: deja pasar el click del item.
 * - Tras un arrastre, suprime el click siguiente para no disparar el item (abrir detalle, etc.).
 * - Ignora arranques sobre controles de formulario o elementos draggable.
 */
interface RubberbandOptions {
	itemSelector: string;
	onChange: (ids: string[]) => void;
	threshold?: number;
}

export function rubberband(node: HTMLElement, options: RubberbandOptions) {
	let opts = options;
	let startX = 0;
	let startY = 0;
	let selecting = false;
	let box: HTMLDivElement | null = null;
	let suppressClick = false;

	function collectIds(l: number, t: number, r: number, b: number): string[] {
		const ids: string[] = [];
		node.querySelectorAll<HTMLElement>(opts.itemSelector).forEach((el) => {
			const cr = el.getBoundingClientRect();
			if (cr.left < r && cr.right > l && cr.top < b && cr.bottom > t) {
				const id = el.dataset.taskid;
				if (id) ids.push(id);
			}
		});
		return ids;
	}

	function onMove(e: MouseEvent) {
		const dx = e.clientX - startX;
		const dy = e.clientY - startY;
		if (!selecting && Math.sqrt(dx * dx + dy * dy) < (opts.threshold ?? 6)) return;
		if (!selecting) {
			selecting = true;
			box = document.createElement('div');
			box.style.cssText =
				'position:fixed;z-index:45;pointer-events:none;border:1.5px solid rgb(var(--c-accent));background:rgb(var(--c-accent)/0.15);border-radius:6px;';
			document.body.appendChild(box);
			document.body.style.userSelect = 'none';
		}
		const l = Math.min(startX, e.clientX);
		const r = Math.max(startX, e.clientX);
		const t = Math.min(startY, e.clientY);
		const b = Math.max(startY, e.clientY);
		if (box) {
			box.style.left = l + 'px';
			box.style.top = t + 'px';
			box.style.width = r - l + 'px';
			box.style.height = b - t + 'px';
		}
		opts.onChange(collectIds(l, t, r, b));
	}

	function onUp() {
		window.removeEventListener('mousemove', onMove);
		window.removeEventListener('mouseup', onUp);
		document.body.style.userSelect = '';
		if (box) {
			box.remove();
			box = null;
		}
		if (selecting) {
			suppressClick = true;
			setTimeout(() => (suppressClick = false), 50);
		}
		selecting = false;
	}

	function onDown(e: MouseEvent) {
		if (e.button !== 0) return;
		const target = e.target as HTMLElement;
		if (target.closest('input, textarea, select, [contenteditable="true"], [draggable="true"]')) return;
		startX = e.clientX;
		startY = e.clientY;
		selecting = false;
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function onClickCapture(e: MouseEvent) {
		if (suppressClick) {
			e.stopPropagation();
			e.preventDefault();
			suppressClick = false;
		}
	}

	node.addEventListener('mousedown', onDown);
	node.addEventListener('click', onClickCapture, true);

	return {
		update(newOpts: RubberbandOptions) {
			opts = newOpts;
		},
		destroy() {
			node.removeEventListener('mousedown', onDown);
			node.removeEventListener('click', onClickCapture, true);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			document.body.style.userSelect = '';
			if (box) box.remove();
		}
	};
}
