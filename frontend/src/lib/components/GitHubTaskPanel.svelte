<script lang="ts">
	import { Github, Link, Loader2, Code2, ExternalLink, X, AlertCircle, GitBranch, GitPullRequest, Rocket, Plus } from 'lucide-svelte';
	import { api } from '../api';
	import { onTaskChange } from '../stores';
	import type { Tarea, GitHubRepo } from '../types';

	let { tarea }: { tarea: Tarea } = $props();

	let repos = $state<GitHubRepo[]>([]);
	let loadingRepos = $state(false);
	let selectedRepo = $state(tarea.github_repo || '');
	let linking = $state(false);
	let creating = $state(false);
	let developing = $state(false);
	let merging = $state(false);
	let result = $state<any>(null);
	let prStatus = $state<{ url: string; state: string; merged: boolean } | null>(null);
	let prompt = $state('');
	let error = $state('');
	let config = $state<{ username: string; configured: boolean } | null>(null);

	async function loadConfig() {
		try {
			config = await api.getGitHubConfig();
		} catch {
			config = { username: '', configured: false };
		}
	}

	async function loadRepos() {
		loadingRepos = true;
		error = '';
		try {
			const r = await api.listGitHubRepos();
			repos = r.repos;
		} catch {
			error = 'No se pudieron cargar los repositorios. Verifica tu token de GitHub.';
		} finally {
			loadingRepos = false;
		}
	}

	async function linkRepo() {
		if (!selectedRepo.trim()) return;
		linking = true;
		error = '';
		try {
			const res = await api.linkGitHubRepo(tarea.id, selectedRepo.trim());
			onTaskChange(res.tarea);
			result = null;
			prStatus = null;
		} catch (e: any) {
			error = e?.message || 'No se pudo vincular el repo.';
		} finally {
			linking = false;
		}
	}

	async function crearRepo() {
		const name = selectedRepo.trim();
		if (!name) return;
		creating = true;
		error = '';
		try {
			const res = await api.createGitHubRepo(name, { private: true });
			selectedRepo = res.repo.full_name;
			const linkRes = await api.linkGitHubRepo(tarea.id, res.repo.full_name);
			onTaskChange(linkRes.tarea);
			await loadRepos();
		} catch (e: any) {
			error = e?.message || 'No se pudo crear el repositorio.';
		} finally {
			creating = false;
		}
	}

	async function unlinkRepo() {
		if (!confirm('¿Desvincular el repositorio de esta tarea?')) return;
		try {
			const res = await api.unlinkGitHubRepo(tarea.id);
			onTaskChange(res.tarea);
			result = null;
			prStatus = null;
		} catch (e: any) {
			error = e?.message || 'No se pudo desvincular.';
		}
	}

	async function develop() {
		developing = true;
		error = '';
		result = null;
		try {
			const res = await api.agenteDesarrollar(tarea.id, prompt);
			if (res.ok) {
				result = res;
				await refreshStatus();
			} else {
				error = res.error || 'El agente no pudo generar cambios.';
			}
		} catch (e: any) {
			error = e?.message || 'Error ejecutando el agente desarrollador.';
		} finally {
			developing = false;
		}
	}

	async function merge() {
		merging = true;
		error = '';
		try {
			await api.mergeGitHubPR(tarea.id);
			await refreshStatus();
		} catch (e: any) {
			error = e?.message || 'No se pudo mergear el PR.';
		} finally {
			merging = false;
		}
	}

	async function refreshStatus() {
		try {
			const res = await api.getGitHubStatus(tarea.id);
			onTaskChange(res.tarea);
			prStatus = res.pr_status;
		} catch (e) {
			console.error(e);
		}
	}

	let isLinked = $derived(!!tarea.github_repo);
	let hasOpenPR = $derived(prStatus && !prStatus.merged && prStatus.state === 'open');

	loadConfig();
	if (tarea.github_repo) refreshStatus();
</script>

<div class="bg-card2 border border-border rounded-xl p-2.5 space-y-2">
	{#if config && !config.configured}
		<div class="text-[10px] text-red-400">Configura tu token en /github</div>
	{/if}

	{#if !isLinked}
		<div class="flex gap-2 items-center">
			<Github size={14} class="text-muted shrink-0" />
			<input
				class="flex-1 min-w-0 bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted"
				placeholder="owner/repo o nombre nuevo"
				list="repos-{tarea.id}"
				bind:value={selectedRepo}
				onfocus={() => repos.length === 0 && loadRepos()}
			/>
			<datalist id="repos-{tarea.id}">
				{#each repos as repo}<option value={repo.full_name}></option>{/each}
			</datalist>
			<button
				onclick={linkRepo}
				disabled={!selectedRepo.trim() || linking}
				class="px-3 py-2 rounded-lg bg-accent text-white text-xs font-medium flex items-center gap-1 disabled:opacity-50 whitespace-nowrap"
				title="Vincular repositorio existente"
			>
				{#if linking}<Loader2 size={14} class="animate-spin" />{:else}<Link size={14} />{/if}
				Vincular
			</button>
			<button
				onclick={crearRepo}
				disabled={!selectedRepo.trim() || creating}
				class="px-3 py-2 rounded-lg bg-card border border-border text-text text-xs font-medium flex items-center gap-1 disabled:opacity-50 whitespace-nowrap"
				title="Crear un repositorio nuevo con ese nombre"
			>
				{#if creating}<Loader2 size={14} class="animate-spin" />{:else}<Plus size={14} />{/if}
				Crear
			</button>
		</div>
	{:else}
		<div class="space-y-3">
			<div class="flex items-center justify-between gap-2">
				<a
					href="https://github.com/{tarea.github_repo}"
					target="_blank"
					rel="noreferrer"
					class="flex items-center gap-1 text-xs text-accent hover:underline truncate"
				>
					<Github size={12} /> {tarea.github_repo}
				</a>
				<button onclick={unlinkRepo} class="text-[10px] text-muted hover:text-red-400">
					<X size={12} />
				</button>
			</div>

			{#if prStatus}
				<div class="flex items-center gap-2 text-xs">
					<GitPullRequest size={12} class={prStatus.merged ? 'text-purple-400' : 'text-green-400'} />
					<span class={prStatus.merged ? 'text-purple-400' : 'text-green-400'}>
						{prStatus.merged ? 'Mergeado' : prStatus.state === 'open' ? 'PR abierto' : prStatus.state}
					</span>
					<a href={prStatus.url} target="_blank" rel="noreferrer" class="text-accent hover:underline flex items-center gap-0.5">
						Ver PR <ExternalLink size={10} />
					</a>
				</div>
			{/if}

			{#if !hasOpenPR}
				<div class="space-y-2">
					<textarea
						class="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted resize-none"
						rows={2}
						placeholder="Instrucciones opcionales para el agente (ej: 'crea un endpoint GET /health')"
						bind:value={prompt}
					/>
					<button
						onclick={develop}
						disabled={developing}
						class="w-full bg-slate-700 text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
					>
						{#if developing}<Loader2 size={14} class="animate-spin" />{:else}<Code2 size={14} />{/if}
						{developing ? 'Agente desarrollando...' : 'Desarrollar con agente'}
					</button>
				</div>
			{/if}

			{#if hasOpenPR}
				<button
					onclick={merge}
					disabled={merging}
					class="w-full bg-green-600 text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
				>
					{#if merging}<Loader2 size={14} class="animate-spin" />{:else}<Rocket size={14} />{/if}
					{merging ? 'Mergeando...' : 'Aprobar y mergear PR'}
				</button>
			{/if}
		</div>
	{/if}

	{#if result && result.ok}
		<div class="bg-bg border border-border rounded-lg p-3 space-y-2 text-xs">
			<div class="font-medium text-text flex items-center gap-1">
				<GitBranch size={12} /> Rama {result.branch}
			</div>
			<div class="text-muted">{result.resumen}</div>
			<div>
				<span class="text-[10px] uppercase text-muted">Archivos</span>
				<div class="mt-1 space-y-0.5">
					{#each result.archivos as path}
						<div class="text-[10px] font-mono text-accent">{path}</div>
					{/each}
				</div>
			</div>
			{#if result.pros?.length > 0}
				<div>
					<span class="text-[10px] uppercase text-green-400">Pros</span>
					<ul class="mt-1 space-y-0.5">
						{#each result.pros as p}
							<li class="text-[10px] text-muted flex items-start gap-1"><span class="text-green-400">✓</span> {p}</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if result.contras?.length > 0}
				<div>
					<span class="text-[10px] uppercase text-red-400">Contras</span>
					<ul class="mt-1 space-y-0.5">
						{#each result.contras as c}
							<li class="text-[10px] text-muted flex items-start gap-1"><span class="text-red-400">!</span> {c}</li>
						{/each}
					</ul>
				</div>
			{/if}
			<a href={result.pr.url} target="_blank" rel="noreferrer" class="inline-flex items-center gap-1 text-accent hover:underline">
				Ver pull request <ExternalLink size={10} />
			</a>
		</div>
	{/if}

	{#if error}
		<div class="bg-red-500/10 text-red-400 text-xs p-2 rounded-lg flex items-start gap-1.5">
			<AlertCircle size={14} class="mt-0.5" /> {error}
		</div>
	{/if}
</div>
