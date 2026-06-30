import { writable, derived } from 'svelte/store';
import type { Tarea, Recordatorio } from './types';

export const tareasStore = writable<Tarea[]>([]);
export const recordatoriosStore = writable<Recordatorio[]>([]);
export const loadingStore = writable(true);

export function onTaskChange(tarea: Tarea | null, deletedId?: string) {
	tareasStore.update((prev) => {
		if (deletedId) return prev.filter((t) => t.id !== deletedId);
		if (!tarea) return prev;
		return prev.map((t) => (t.id === tarea.id ? tarea : t));
	});
}

export function onRecordatorioChange(recordatorio: Recordatorio | null, deletedId?: string) {
	recordatoriosStore.update((prev) => {
		if (deletedId) return prev.filter((r) => r.id !== deletedId);
		if (!recordatorio) return prev;
		return prev.map((r) => (r.id === recordatorio.id ? recordatorio : r));
	});
}

export const wsStore = writable<{ type: 'tareas_changed' | 'recordatorios_changed' } | null>(null);

export const themeStore = writable<{
	bg: string;
	card: string;
	card2: string;
	border: string;
	accent: string;
	green: string;
	red: string;
	yellow: string;
	muted: string;
	text: string;
}>({
	bg: '#0a0a0b',
	card: '#18181b',
	card2: '#1e1e24',
	border: '#27272a',
	accent: '#667eea',
	green: '#22c55e',
	red: '#ef4444',
	yellow: '#eab308',
	muted: '#71717a',
	text: '#e4e4e7'
});

export const notifEnabledStore = writable(false);

export const filteredTareasStore = derived(tareasStore, ($tareas) => $tareas);

export const pendientesCount = derived(tareasStore, ($tareas) => $tareas.filter((t) => t.estado !== 'completada').length);
export const completadasCount = derived(tareasStore, ($tareas) => $tareas.filter((t) => t.estado === 'completada').length);
