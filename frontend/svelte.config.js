import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			fallback: 'index.html',
			pages: '../web',
			assets: '../web',
			precompress: false,
			strict: false
		}),
		prerender: {
			entries: ['/', '/completadas', '/calendario', '/kanban', '/alarmas', '/agentes', '/voz', '/github', '/changelog'],
			handleHttpError: 'warn'
		}
	}
};

export default config;
