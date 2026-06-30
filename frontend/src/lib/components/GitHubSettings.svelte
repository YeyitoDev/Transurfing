<script lang="ts">
	import { Github, X, Loader2, Save, CheckCircle, AlertCircle, ExternalLink, ChevronDown, ChevronUp, Shield, Key, LogIn } from 'lucide-svelte';
	import { page } from '$app/stores';
	import { api } from '../api';

	interface Props {
		onClose?: () => void;
	}

	let { onClose }: Props = $props();

	let pat = $state('');
	let username = $state('');
	let repos = $state<{ full_name: string; name: string }[]>([]);
	let loading = $state(false);
	let testing = $state(false);
	let connecting = $state(false);
	let mensaje = $state('');
	let error = $state('');
	let showManual = $state(false);
	let configOk = $state(false);
	let oauthAvailable = $state(false);
	let diagnostico = $state<{ callback_url: string; oauth_configurado: boolean; tareas_url: string; mensaje: string; problemas: string[] } | null>(null);
	let redirectUri = $state('');
	let testCallbackMsg = $state('');
	let testCallbackOk = $state<boolean | null>(null);

	const SCOPES = ['repo', 'workflow', 'read:user'];
	const TOKEN_URL = `https://github.com/settings/tokens/new?description=Jarvis%20Tareas&scopes=${SCOPES.join('%2C')}`;

	async function cargar() {
		try {
			const [config, diag] = await Promise.all([api.getGitHubConfig(), api.getGitHubDiagnostico()]);
			if (config.username) username = config.username;
			oauthAvailable = config.oauth_available;
			diagnostico = diag;
			if (config.configured) {
				configOk = true;
				const r = await api.listGitHubRepos();
				repos = r.repos;
			}
			// Manejar retorno de OAuth
			const params = new URLSearchParams($page.url.search);
			if (params.has('success')) {
				mensaje = 'GitHub conectado correctamente.';
				configOk = true;
				const r = await api.listGitHubRepos();
				repos = r.repos;
			} else if (params.has('error')) {
				error = `Error de OAuth: ${params.get('error')}`;
			}
		} catch (e) {
			console.error(e);
		}
	}

	async function connectOAuth() {
		connecting = true;
		error = '';
		try {
			const res = await api.startGitHubOAuth();
			redirectUri = res.redirect_uri;
			window.location.href = res.url;
		} catch (e: any) {
			connecting = false;
			error = e?.message || 'No se pudo iniciar el login con GitHub.';
		}
	}

	async function probarCallback() {
		testCallbackMsg = 'Probando...';
		testCallbackOk = null;
		try {
			const res = await api.testGitHubCallback();
			testCallbackOk = true;
			testCallbackMsg = res.mensaje;
		} catch (e: any) {
			testCallbackOk = false;
			testCallbackMsg = e?.message || 'No se pudo alcanzar el endpoint de callback.';
		}
	}

	async function copiarCallback() {
		if (!diagnostico) return;
		try {
			await navigator.clipboard.writeText(diagnostico.callback_url);
			mensaje = 'Callback URL copiada al portapapeles.';
		} catch {
			error = 'No se pudo copiar automáticamente.';
		}
	}

	async function guardar() {
		if (!pat.trim()) {
			error = 'Pega el token de GitHub.';
			return;
		}
		loading = true;
		mensaje = '';
		error = '';
		try {
			const res = await api.setGitHubConfig(pat, username);
			configOk = true;
			mensaje = `Conectado como ${res.username} con permisos: ${res.scopes.join(', ')}`;
			await cargar();
		} catch (e: any) {
			console.error(e);
			error = e?.message || 'El token no es válido o no tiene permisos suficientes.';
		} finally {
			loading = false;
		}
	}

	async function probar() {
		testing = true;
		error = '';
		mensaje = '';
		try {
			const r = await api.listGitHubRepos();
			repos = r.repos;
			configOk = true;
			mensaje = `Conexión OK: ${r.repos.length} repositorios encontrados.`;
		} catch (e: any) {
			error = e?.message || 'No se pudo conectar. Revisa el token y los permisos.';
		} finally {
			testing = false;
		}
	}

	function close() {
		onClose?.();
		history.back();
	}

	cargar();
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onclick={close}>
	<div class="bg-card border border-border rounded-2xl p-5 w-full max-w-md max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
		<div class="flex items-center justify-between mb-4">
			<h3 class="text-base font-semibold flex items-center gap-2">
				<Github size={20} /> GitHub
			</h3>
			<button onclick={close} class="text-muted hover:text-text"><X size={20} /></button>
		</div>

		{#if configOk}
			<div class="mb-4 p-3 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-xs flex items-start gap-2">
				<CheckCircle size={16} class="mt-0.5 shrink-0" />
				<div>
					<div class="font-medium">GitHub conectado</div>
					{#if username}<div class="text-green-300/70">@{username}</div>{/if}
				</div>
			</div>
		{/if}

		{#if mensaje}
			<div class="mb-3 p-3 rounded-xl bg-green-500/10 border border-green-500/20 text-xs text-green-400 flex items-start gap-2">
				<CheckCircle size={14} class="mt-0.5 shrink-0" /> {mensaje}
			</div>
		{/if}
		{#if error}
			<div class="mb-3 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-start gap-2">
				<AlertCircle size={14} class="mt-0.5 shrink-0" /> {error}
			</div>
		{/if}

		{#if oauthAvailable}
			<div class="mb-4 space-y-3">
				<p class="text-xs text-muted">
					Pulsa el botón para autorizar a la app. GitHub te pedirá permisos para leer tus repositorios y crear pull requests.
				</p>
				{#if diagnostico}
					<div class="bg-bg border border-border rounded-lg p-3 text-xs space-y-2">
						<div class="text-muted">Callback URL:</div>
						<div class="font-mono text-text break-all">{diagnostico.callback_url}</div>
						{#if diagnostico.problemas.length > 0}
							<ul class="space-y-1">
								{#each diagnostico.problemas as p}
									<li class="text-[10px] text-red-400 flex items-start gap-1">
										<span class="mt-0.5">⚠</span> {p}
									</li>
								{/each}
							</ul>
						{/if}
						<div class="flex gap-2">
							<button onclick={copiarCallback} class="text-[10px] px-2 py-1 rounded-lg bg-card border border-border text-muted hover:text-text">Copiar URL</button>
							<button onclick={probarCallback} class="text-[10px] px-2 py-1 rounded-lg bg-card border border-border text-muted hover:text-text">Probar callback</button>
						</div>
						{#if testCallbackMsg}
							<div class="text-[10px] {testCallbackOk ? 'text-green-400' : 'text-red-400'}">{testCallbackMsg}</div>
						{/if}
						<div class="text-[10px] text-muted">Registra esta URL en tu GitHub OAuth App (Settings → Developer settings → OAuth Apps → Authorization callback URL).</div>
					</div>
				{/if}
				<button onclick={connectOAuth} disabled={connecting} class="w-full bg-accent text-white rounded-xl px-4 py-3 text-sm font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-50">
					{#if connecting}<Loader2 class="animate-spin" size={18} />{:else}<LogIn size={18} />{/if}
					{connecting ? 'Redirigiendo a GitHub...' : 'Conectar con GitHub'}
				</button>
			</div>
		{:else if diagnostico}
			<div class="mb-4 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-300">
				<div class="font-medium mb-1">OAuth no configurado en el servidor</div>
				{#if diagnostico.problemas.length > 0}
					<ul class="space-y-1 mt-1">
						{#each diagnostico.problemas as p}
							<li class="text-[10px] text-red-300 flex items-start gap-1"><span class="mt-0.5">⚠</span> {p}</li>
						{/each}
					</ul>
				{/if}
				<div class="text-muted mt-1">{diagnostico.mensaje}</div>
			</div>
		{/if}

		<div class="mb-4 rounded-xl border border-border overflow-hidden">
			<button onclick={() => (showManual = !showManual)} class="w-full px-4 py-3 flex items-center justify-between text-sm font-medium bg-card2 hover:bg-card2/80 transition-colors">
				<span class="flex items-center gap-2"><Key size={14} /> {oauthAvailable ? 'Prefiero usar token manual' : 'Configurar con token'}</span>
				{#if showManual}<ChevronUp size={14} />{:else}<ChevronDown size={14} />{/if}
			</button>
			{#if showManual}
				<div class="p-4 space-y-3 text-xs text-muted bg-bg/50">
					<p>
						Crea un token clásico en GitHub con los permisos necesarios y pégalo aquí.
						{#if oauthAvailable}Usa esta opción si no quieres usar OAuth.{/if}
					</p>
					<div class="space-y-1">
						{#each SCOPES as scope}
							<div class="flex items-center gap-1.5">
								<Shield size={10} class="text-accent" /> <span class="font-mono text-text">{scope}</span>
							</div>
						{/each}
					</div>
					<a href={TOKEN_URL} target="_blank" rel="noreferrer" class="inline-flex items-center gap-1.5 bg-card border border-border rounded-lg px-3 py-2 text-text hover:border-accent transition-colors">
						<ExternalLink size={12} /> Crear token en GitHub
					</a>
				</div>
			{/if}
		</div>

		{#if showManual || !oauthAvailable}
			<div class="mb-3">
				<label class="text-xs text-muted font-medium mb-1.5 block">Token de acceso personal (PAT)</label>
				<input type="password" class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted focus:border-accent focus:outline-none" placeholder="ghp_..." bind:value={pat} />
			</div>
			<div class="mb-4">
				<label class="text-xs text-muted font-medium mb-1.5 block">Usuario de GitHub (opcional)</label>
				<input class="w-full bg-bg border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted focus:border-accent focus:outline-none" placeholder="usuario" bind:value={username} />
			</div>

			<div class="flex gap-2 mb-4">
				<button onclick={guardar} class="flex-1 bg-accent text-white rounded-xl px-4 py-2.5 text-sm font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5" disabled={loading || !pat.trim()}>
					{#if loading}<Loader2 class="animate-spin" size={16} />{:else}<Save size={16} />{/if}
					Guardar
				</button>
				<button onclick={probar} class="px-4 py-2.5 rounded-xl bg-card border border-border text-text text-sm font-medium hover:border-accent transition-colors flex items-center gap-1.5" disabled={testing}>
					{#if testing}<Loader2 class="animate-spin" size={16} />{:else}<CheckCircle size={16} />{/if}
					Probar
				</button>
			</div>
		{/if}

		<div>
			<h4 class="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Repositorios accesibles ({repos.length})</h4>
			{#if repos.length === 0}
				<div class="text-sm text-muted">Aún no hay repositorios cargados. Conecta tu cuenta o pulsa Probar.</div>
			{:else}
				<div class="space-y-1 max-h-40 overflow-y-auto pr-1">
					{#each repos.slice(0, 20) as repo}
						<div class="text-sm text-text truncate">{repo.full_name}</div>
					{/each}
					{#if repos.length > 20}
						<div class="text-xs text-muted">+ {repos.length - 20} más</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>


