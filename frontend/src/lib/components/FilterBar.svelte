<script lang="ts">
	import type { EtiquetaKey } from '../types';

	const CHIPS: { key: EtiquetaKey; label: string }[] = [
		{ key: 'todas', label: 'Todas' },
		{ key: 'emprendimiento', label: 'Emprendimiento' },
		{ key: 'tarea', label: 'Tarea' },
		{ key: 'habito', label: 'Hábito' },
		{ key: 'investigacion', label: 'Investigación' },
		{ key: 'idea', label: 'Idea' }
	];

	let { value = $bindable('todas'), onChange }: { value?: EtiquetaKey; onChange?: (e: EtiquetaKey) => void } = $props();

	function select(key: EtiquetaKey) {
		value = key;
		onChange?.(key);
	}
</script>

<div class="flex gap-2 overflow-x-auto no-scrollbar py-1">
	{#each CHIPS as chip}
		<button
			onclick={() => select(chip.key)}
			class="px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors {value === chip.key
				? 'bg-accent text-white'
				: 'bg-card2 text-muted border border-border hover:text-text'}"
		>
			{chip.label}
		</button>
	{/each}
</div>
