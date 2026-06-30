/// <reference types="@sveltejs/kit" />
// Service worker idiomático de SvelteKit: se registra automáticamente en build.
// Precachea los assets de build y aplica network-first para navegación.
import { build, files, version } from '$service-worker';

const CACHE = `transurfing-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => self.skipWaiting())
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.map((k) => (k !== CACHE ? caches.delete(k) : undefined))))
			.then(() => self.clients.claim())
	);
});

self.addEventListener('fetch', (event) => {
	const { request } = event;
	if (request.method !== 'GET') return;

	const url = new URL(request.url);
	if (url.origin !== self.location.origin) return;
	// Nunca interceptar la API ni el WebSocket en tiempo real.
	if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws')) return;

	// Assets de build conocidos: cache-first.
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
		return;
	}

	// Resto (navegación/recursos): network-first con respaldo en caché.
	event.respondWith(
		fetch(request)
			.then((response) => {
				const copy = response.clone();
				caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
				return response;
			})
			.catch(() => caches.match(request).then((cached) => cached || caches.match('/')))
	);
});
