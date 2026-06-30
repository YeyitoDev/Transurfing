<script lang="ts">
	let { pct }: { pct: number } = $props();
	const full = pct >= 100;
</script>

<div class="flex items-center gap-2 min-w-[100px]">
	<div class="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
		<div class="h-full rounded-full transition-all duration-300 {full ? 'bg-green' : 'bg-accent'}" style="width: {pct}%"></div>
	</div>
	<span class="text-[11px] text-muted min-w-[30px] text-right">{Math.round(pct)}%</span>
</div>
