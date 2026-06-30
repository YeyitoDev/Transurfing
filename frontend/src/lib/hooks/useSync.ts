import { onMount } from 'svelte';
import { api } from '../api';
import { WebSocketClient } from '../ws';
import {
	tareasStore,
	recordatoriosStore,
	loadingStore,
	wsStore,
	onTaskChange,
	onRecordatorioChange
} from '../stores';
import type { WSMessage } from '../types';

export { onTaskChange, onRecordatorioChange };

const wsClient = new WebSocketClient();

export async function cargarTareas() {
	try {
		const t = await api.listarTareas();
		tareasStore.set(t);
	} catch (e) {
		console.error('Error cargando tareas:', e);
	}
}

export async function cargarRecordatorios() {
	try {
		const r = await api.listarRecordatorios();
		recordatoriosStore.set(r);
	} catch (e) {
		console.error('Error cargando recordatorios:', e);
	}
}

export async function cargarTodo() {
	loadingStore.set(true);
	await Promise.all([cargarTareas(), cargarRecordatorios()]);
	loadingStore.set(false);
}

export function useSync() {
	onMount(() => {
		cargarTodo();
		wsClient.connect();
		const unsub = wsClient.onMessage((msg: WSMessage) => {
			wsStore.set(msg);
			if (msg.type === 'tareas_changed') cargarTareas();
			if (msg.type === 'recordatorios_changed') cargarRecordatorios();
		});

		const pollId = window.setInterval(() => {
			if (document.visibilityState === 'visible') {
				cargarTareas();
				cargarRecordatorios();
			}
		}, 15000);

		return () => {
			unsub();
			clearInterval(pollId);
		};
	});

	return { tareasStore, recordatoriosStore, loadingStore, cargarTareas, cargarRecordatorios, wsStore };
}

export { wsClient };
