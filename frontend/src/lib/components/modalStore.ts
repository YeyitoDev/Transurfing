import { writable, derived } from 'svelte/store';
import { tareasStore } from '../stores';
import type { Tarea, Subtarea } from '../types';

const detailModalId = writable<string | null>(null);
export const detailModalStore = derived([detailModalId, tareasStore], ([$id, $tareas]) => {
	if (!$id) return null;
	return $tareas.find((t) => t.id === $id) || null;
});

const editModalId = writable<string | null>(null);
export const editModalStore = derived([editModalId, tareasStore], ([$id, $tareas]) => {
	if (!$id) return null;
	return $tareas.find((t) => t.id === $id) || null;
});

export const reminderModalStore = writable<{ tarea?: Tarea; subtarea?: Subtarea } | null>(null);

export const modalStore = {
	openDetail(tarea: Tarea) {
		detailModalId.set(tarea.id);
	},
	closeDetail() {
		detailModalId.set(null);
	},
	openEdit(tarea: Tarea) {
		editModalId.set(tarea.id);
	},
	closeEdit() {
		editModalId.set(null);
	},
	openReminder(target: { tarea?: Tarea; subtarea?: Subtarea }) {
		reminderModalStore.set(target);
	},
	closeReminder() {
		reminderModalStore.set(null);
	}
};
