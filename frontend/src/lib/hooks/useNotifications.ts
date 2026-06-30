import { browser } from '$app/environment';
import { onMount } from 'svelte';
import { get } from 'svelte/store';
import { notifEnabledStore } from '../stores';
import type { Recordatorio } from '../types';

const notifiedIds = new Set<string>();

export function requestPermission() {
	if (!browser || !('Notification' in window)) return;
	if (Notification.permission === 'default') {
		Notification.requestPermission().then((perm) => {
			notifEnabledStore.set(perm === 'granted');
		});
	}
}

export function useNotifications(recordatorios: Recordatorio[]) {
	onMount(() => {
		if (!browser || !('Notification' in window)) return;
		notifEnabledStore.set(Notification.permission === 'granted');

		const check = () => {
			const ahora = new Date().toISOString().slice(0, 16);
			recordatorios.forEach((r) => {
				if (r.estado !== 'completado' && r.fecha_hora <= ahora && !notifiedIds.has(r.id)) {
					notifiedIds.add(r.id);
					const n = new Notification('⏰ Recordatorio', {
						body: r.titulo + (r.tarea_titulo ? ` — ${r.tarea_titulo}` : ''),
						tag: r.id,
						requireInteraction: true
					});
					n.onclick = () => {
						window.focus();
						n.close();
					};
				}
			});
		};

		let unsubscribe = notifEnabledStore.subscribe((enabled) => {
			if (!enabled) return;
			check();
		});

		const id = setInterval(() => {
			if (get(notifEnabledStore)) check();
		}, 30000);

		return () => {
			unsubscribe();
			clearInterval(id);
		};
	});

	return { enabled: notifEnabledStore, requestPermission };
}
