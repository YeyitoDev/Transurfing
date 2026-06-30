<script lang="ts">
	import { onMount } from 'svelte';
	import { Timer, Play, Pause, RotateCcw, X, Brain, Coffee } from 'lucide-svelte';

	let open = $state(false);
	let mode = $state<'work' | 'break'>('work');
	let workMin = $state(25);
	let breakMin = $state(5);
	let remaining = $state(25 * 60);
	let running = $state(false);
	let completed = $state(0);
	let label = $state('');
	let intervalo: ReturnType<typeof setInterval> | null = null;

	let mm = $derived(String(Math.floor(remaining / 60)).padStart(2, '0'));
	let ss = $derived(String(remaining % 60).padStart(2, '0'));
	let total = $derived((mode === 'work' ? workMin : breakMin) * 60);
	let pct = $derived(total > 0 ? Math.round((1 - remaining / total) * 100) : 0);

	function beep() {
		try {
			const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
			const ctx = new Ctx();
			const o = ctx.createOscillator();
			const g = ctx.createGain();
			o.connect(g);
			g.connect(ctx.destination);
			o.frequency.value = 880;
			o.start();
			g.gain.setValueAtTime(0.001, ctx.currentTime);
			g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
			g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
			o.stop(ctx.currentTime + 0.6);
		} catch {
			/* sin audio */
		}
	}

	function notify(text: string) {
		try {
			if ('Notification' in window && Notification.permission === 'granted') new Notification('Pomodoro', { body: text });
		} catch {
			/* ignore */
		}
	}

	function tick() {
		if (remaining > 0) {
			remaining -= 1;
			return;
		}
		beep();
		if (mode === 'work') {
			completed += 1;
			notify('¡Tiempo! Toma un descanso ☕');
			mode = 'break';
			remaining = breakMin * 60;
		} else {
			notify('Descanso terminado. A enfocarse 🧠');
			mode = 'work';
			remaining = workMin * 60;
		}
	}

	function start() {
		if (running) return;
		running = true;
		intervalo = setInterval(tick, 1000);
	}
	function pause() {
		running = false;
		if (intervalo) {
			clearInterval(intervalo);
			intervalo = null;
		}
	}
	function reset() {
		pause();
		remaining = (mode === 'work' ? workMin : breakMin) * 60;
	}
	function setMode(m: 'work' | 'break') {
		mode = m;
		reset();
	}

	onMount(() => {
		const toggle = () => (open = !open);
		const openWith = (e: Event) => {
			const d = (e as CustomEvent).detail;
			if (d && d.label) label = d.label;
			open = true;
		};
		window.addEventListener('pomodoro:toggle', toggle);
		window.addEventListener('pomodoro:open', openWith as EventListener);
		return () => {
			window.removeEventListener('pomodoro:toggle', toggle);
			window.removeEventListener('pomodoro:open', openWith as EventListener);
			if (intervalo) clearInterval(intervalo);
		};
	});
</script>

{#if open}
	<div class="fixed bottom-24 right-4 z-[90] w-60 bg-card border border-border rounded-2xl shadow-2xl p-4 animate-slide-up">
		<div class="flex items-center justify-between mb-2">
			<div class="flex items-center gap-1.5 text-sm font-semibold text-text">
				<Timer size={15} class="text-accent" /> Enfoque
			</div>
			<button onclick={() => (open = false)} class="text-muted hover:text-text"><X size={16} /></button>
		</div>

		{#if label}
			<div class="text-[11px] text-muted truncate mb-2" title={label}>En: {label}</div>
		{/if}

		<div class="flex gap-1 mb-3">
			<button
				onclick={() => setMode('work')}
				class="flex-1 text-[11px] py-1 rounded-lg border flex items-center justify-center gap-1 {mode === 'work' ? 'bg-accent text-white border-accent' : 'bg-bg border-border text-muted hover:text-text'}"
			>
				<Brain size={12} /> Trabajo
			</button>
			<button
				onclick={() => setMode('break')}
				class="flex-1 text-[11px] py-1 rounded-lg border flex items-center justify-center gap-1 {mode === 'break' ? 'bg-accent text-white border-accent' : 'bg-bg border-border text-muted hover:text-text'}"
			>
				<Coffee size={12} /> Descanso
			</button>
		</div>

		<div class="text-center text-4xl font-bold tabular-nums text-text tracking-tight">{mm}:{ss}</div>
		<div class="h-1.5 bg-bg rounded-full overflow-hidden my-3">
			<div class="h-full bg-accent transition-all" style="width: {pct}%"></div>
		</div>

		<div class="flex items-center gap-2">
			{#if running}
				<button onclick={pause} class="flex-1 bg-card2 border border-border text-text rounded-lg py-2 text-sm flex items-center justify-center gap-1 hover:bg-bg">
					<Pause size={14} /> Pausa
				</button>
			{:else}
				<button onclick={start} class="flex-1 bg-accent text-white rounded-lg py-2 text-sm flex items-center justify-center gap-1 hover:opacity-90">
					<Play size={14} /> Iniciar
				</button>
			{/if}
			<button onclick={reset} class="p-2 rounded-lg border border-border text-muted hover:text-text" title="Reiniciar"><RotateCcw size={14} /></button>
		</div>

		<div class="text-[11px] text-muted text-center mt-2">Pomodoros completados: <span class="text-text font-semibold">{completed}</span></div>
	</div>
{/if}
