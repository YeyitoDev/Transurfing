import { browser } from '$app/environment';
import { themeStore } from '../stores';

export type ThemeColors = {
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
};

export const COLOR_LABELS: Record<keyof ThemeColors, string> = {
	bg: 'Fondo',
	card: 'Tarjetas',
	card2: 'Tarjetas (2)',
	border: 'Bordes',
	accent: 'Acento',
	text: 'Texto',
	muted: 'Texto tenue',
	green: 'Éxito',
	red: 'Error / Alerta',
	yellow: 'Advertencia'
};

const CSS_VAR: Record<keyof ThemeColors, string> = {
	bg: '--c-bg',
	card: '--c-card',
	card2: '--c-card2',
	border: '--c-border',
	accent: '--c-accent',
	green: '--c-green',
	red: '--c-red',
	yellow: '--c-yellow',
	muted: '--c-muted',
	text: '--c-text'
};

export const DEFAULT_THEME: ThemeColors = {
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
};

export const PRESETS: { name: string; colors: ThemeColors }[] = [
	{ name: 'Midnight', colors: DEFAULT_THEME },
	{
		name: 'Océano',
		colors: {
			bg: '#0b1622',
			card: '#13243a',
			card2: '#1a2f4a',
			border: '#244060',
			accent: '#38bdf8',
			green: '#34d399',
			red: '#fb7185',
			yellow: '#fbbf24',
			muted: '#64829e',
			text: '#e2eefc'
		}
	},
	{
		name: 'Bosque',
		colors: {
			bg: '#0c1410',
			card: '#16241c',
			card2: '#1d3026',
			border: '#2a4534',
			accent: '#4ade80',
			green: '#22c55e',
			red: '#f87171',
			yellow: '#facc15',
			muted: '#6b8576',
			text: '#e3f2e8'
		}
	},
	{
		name: 'Atardecer',
		colors: {
			bg: '#1a1015',
			card: '#2a1a22',
			card2: '#37222e',
			border: '#4d2f3e',
			accent: '#fb7185',
			green: '#34d399',
			red: '#ef4444',
			yellow: '#fbbf24',
			muted: '#9c7480',
			text: '#fce8ef'
		}
	},
	{
		name: 'Claro',
		colors: {
			bg: '#f8fafc',
			card: '#ffffff',
			card2: '#f1f5f9',
			border: '#e2e8f0',
			accent: '#6366f1',
			green: '#16a34a',
			red: '#dc2626',
			yellow: '#ca8a04',
			muted: '#94a3b8',
			text: '#1e293b'
		}
	},
	{
		name: 'Púrpura',
		colors: {
			bg: '#120b1f',
			card: '#1e1330',
			card2: '#281a40',
			border: '#3b2960',
			accent: '#a855f7',
			green: '#34d399',
			red: '#fb7185',
			yellow: '#fbbf24',
			muted: '#7c6a9c',
			text: '#ede4fc'
		}
	}
];

const STORAGE_KEY = 'app_theme_colors';

function hexToRgbChannels(hex: string): string {
	let h = hex.replace('#', '');
	if (h.length === 3) h = h.split('').map((c) => c + c).join('');
	const r = parseInt(h.slice(0, 2), 16);
	const g = parseInt(h.slice(2, 4), 16);
	const b = parseInt(h.slice(4, 6), 16);
	return `${r} ${g} ${b}`;
}

export function applyTheme(colors: ThemeColors) {
	const root = document.documentElement;
	(Object.keys(colors) as (keyof ThemeColors)[]).forEach((key) => {
		root.style.setProperty(CSS_VAR[key], hexToRgbChannels(colors[key]));
	});
}

export function loadTheme(): ThemeColors {
	if (!browser) return DEFAULT_THEME;
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw);
			return { ...DEFAULT_THEME, ...parsed };
		}
	} catch {
		// ignore
	}
	return DEFAULT_THEME;
}

export function saveTheme(colors: ThemeColors) {
	if (!browser) return;
	localStorage.setItem(STORAGE_KEY, JSON.stringify(colors));
}

export function setColor(key: keyof ThemeColors, value: string) {
	themeStore.update((prev) => {
		const next = { ...prev, [key]: value };
		if (browser) applyTheme(next);
		if (browser) saveTheme(next);
		return next;
	});
}

export function applyPreset(preset: ThemeColors) {
	themeStore.set(preset);
	if (browser) applyTheme(preset);
	if (browser) saveTheme(preset);
}

export function resetTheme() {
	applyPreset(DEFAULT_THEME);
}

export function useTheme() {
	if (browser) {
		const loaded = loadTheme();
		themeStore.set(loaded);
		applyTheme(loaded);
	}
	return { themeStore, setColor, applyPreset, resetTheme };
}
