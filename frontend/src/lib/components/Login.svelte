<script lang="ts">
	import { Lock, Loader2, AlertCircle } from 'lucide-svelte';
	import { api } from '../api';

	let token = $state('');
	let error = $state('');
	let loading = $state(false);

	async function entrar() {
		const t = token.trim();
		if (!t || loading) return;
		loading = true;
		error = '';
		try {
			api.setToken(t);
			await api.authCheck();
			location.reload();
		} catch {
			api.clearToken();
			error = 'Clave incorrecta. Inténtalo de nuevo.';
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-bg text-text flex items-center justify-center px-4">
	<form
		onsubmit={(e) => {
			e.preventDefault();
			entrar();
		}}
		class="w-full max-w-sm bg-card border border-border rounded-2xl p-6 shadow-xl"
	>
		<div class="flex flex-col items-center text-center mb-5">
			<div class="w-12 h-12 rounded-2xl bg-accent/15 text-accent flex items-center justify-center mb-3">
				<Lock size={22} />
			</div>
			<h1 class="text-lg font-bold">Acceso al portal</h1>
			<p class="text-xs text-muted mt-1">Introduce tu clave para continuar.</p>
		</div>

		<input
			bind:value={token}
			type="password"
			autocomplete="current-password"
			placeholder="Clave de acceso"
			class="w-full bg-bg border border-border rounded-xl px-3 py-2.5 text-sm outline-none focus:border-accent transition-colors"
		/>

		{#if error}
			<div class="mt-2 flex items-center gap-1.5 text-xs text-red-400">
				<AlertCircle size={14} />
				{error}
			</div>
		{/if}

		<button
			type="submit"
			disabled={loading || !token.trim()}
			class="mt-4 w-full bg-accent text-white rounded-xl py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50 hover:opacity-90 transition-opacity"
		>
			{#if loading}
				<Loader2 size={15} class="animate-spin" /> Verificando…
			{:else}
				Entrar
			{/if}
		</button>
	</form>
</div>
