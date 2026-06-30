<script lang="ts">
	import { X, RotateCcw } from 'lucide-svelte';
	import { useTheme, PRESETS, COLOR_LABELS, DEFAULT_THEME } from '../hooks/useTheme';
	import { themeStore } from '../stores';

	let { onClose }: { onClose: () => void } = $props();
	let { setColor, applyPreset, resetTheme } = useTheme();
	let colors = $derived($themeStore);
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-fade-in p-4" onclick={onClose}>
	<div class="bg-card border border-border rounded-2xl p-5 w-full max-w-md animate-slide-up" onclick={(e) => e.stopPropagation()}>
		<div class="flex items-center justify-between mb-4">
			<h3 class="text-base font-semibold">Personalizar tema</h3>
			<button onclick={onClose} class="text-muted hover:text-text"><X size={20} /></button>
		</div>

		<div class="mb-4">
			<label class="text-xs text-muted font-medium mb-2 block">Presets</label>
			<div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
				{#each PRESETS as preset}
					<button
						onclick={() => applyPreset(preset.colors)}
						class="px-3 py-2 rounded-xl border border-border text-xs font-medium text-muted hover:text-text transition-colors text-left"
						style="background: {preset.colors.card}"
					>
						{preset.name}
					</button>
				{/each}
			</div>
		</div>

		<div class="space-y-3 mb-4">
			{#each Object.entries(COLOR_LABELS) as [key, label]}
				<div class="flex items-center justify-between gap-3">
					<label class="text-sm text-muted">{label}</label>
					<div class="flex items-center gap-2">
						<input type="color" value={colors[key as keyof typeof colors]} oninput={(e) => setColor(key as keyof typeof colors, e.currentTarget.value)} class="w-8 h-8 rounded cursor-pointer bg-transparent border-0 p-0" />
						<span class="text-xs text-muted font-mono w-16 text-right">{colors[key as keyof typeof colors]}</span>
					</div>
				</div>
			{/each}
		</div>

		<div class="flex justify-end gap-2 pt-3 border-t border-border">
			<button onclick={resetTheme} class="px-3 py-2 rounded-xl text-sm text-muted hover:text-text flex items-center gap-1.5">
				<RotateCcw size={16} /> Restablecer
			</button>
			<button onclick={onClose} class="px-4 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:opacity-90 transition-opacity">Cerrar</button>
		</div>
	</div>
</div>
