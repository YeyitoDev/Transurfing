/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	safelist: [
		{ pattern: /bg-(red|amber|green|indigo|slate|pink|cyan)-500\/(15|20)/ },
		{ pattern: /border-(red|amber|green|indigo|slate|pink|cyan)-500\/(50)/ },
		{ pattern: /text-(red|amber|green|indigo|slate|pink|cyan)-300/ },
		{ pattern: /border-l-(indigo|slate|pink|cyan)-500/ },
		{ pattern: /border-l-slate-400/ }
	],
	theme: {
		extend: {
			colors: {
				bg: 'rgb(var(--c-bg) / <alpha-value>)',
				card: 'rgb(var(--c-card) / <alpha-value>)',
				card2: 'rgb(var(--c-card2) / <alpha-value>)',
				border: 'rgb(var(--c-border) / <alpha-value>)',
				accent: 'rgb(var(--c-accent) / <alpha-value>)',
				green: 'rgb(var(--c-green) / <alpha-value>)',
				red: 'rgb(var(--c-red) / <alpha-value>)',
				yellow: 'rgb(var(--c-yellow) / <alpha-value>)',
				muted: 'rgb(var(--c-muted) / <alpha-value>)',
				text: 'rgb(var(--c-text) / <alpha-value>)'
			},
			fontFamily: {
				sans: ['Inter', 'system-ui', 'sans-serif']
			},
			animation: {
				'slide-up': 'slideUp 0.3s ease-out',
				'fade-in': 'fadeIn 0.2s ease-out',
				pulse: 'pulse 1.5s infinite'
			},
			keyframes: {
				slideUp: {
					'0%': { transform: 'translateY(100%)', opacity: '0' },
					'100%': { transform: 'translateY(0)', opacity: '1' }
				},
				fadeIn: {
					'0%': { opacity: '0' },
					'100%': { opacity: '1' }
				}
			}
		}
	},
	plugins: []
};
