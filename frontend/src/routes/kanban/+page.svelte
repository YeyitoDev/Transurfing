<script lang="ts">
	import { tareasStore } from '../../lib/stores';
	import KanbanBoard from '../../lib/components/KanbanBoard.svelte';
</script>

<KanbanBoard tareas={$tareasStore} />
