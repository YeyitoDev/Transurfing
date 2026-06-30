import { useEffect, useState } from "react";
import { Github, Link, Loader2, Code2, ExternalLink, Check, X, AlertCircle, GitBranch, GitPullRequest, Rocket } from "lucide-react";
import type { Tarea, GitHubRepo } from "../types";
import { api } from "../api";

interface Props {
  tarea: Tarea;
  onChange: (t: Tarea) => void;
}

export function GitHubTaskPanel({ tarea, onChange }: Props) {
  const [config, setConfig] = useState<{ username: string; configured: boolean } | null>(null);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(tarea.github_repo || "");
  const [linking, setLinking] = useState(false);
  const [developing, setDeveloping] = useState(false);
  const [merging, setMerging] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [prStatus, setPrStatus] = useState<{ url: string; state: string; merged: boolean } | null>(null);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getGitHubConfig().then(setConfig).catch(() => setConfig({ username: "", configured: false }));
    if (tarea.github_repo) {
      refreshStatus();
    }
  }, [tarea.github_repo]);

  const loadRepos = async () => {
    setLoadingRepos(true);
    setError(null);
    try {
      const res = await api.listGitHubRepos();
      setRepos(res.repos);
    } catch (e: any) {
      setError("No se pudieron cargar los repositorios. Verifica tu token de GitHub.");
    } finally {
      setLoadingRepos(false);
    }
  };

  const linkRepo = async () => {
    if (!selectedRepo.trim()) return;
    setLinking(true);
    setError(null);
    try {
      const res = await api.linkGitHubRepo(tarea.id, selectedRepo.trim());
      onChange(res.tarea);
    } catch (e: any) {
      setError(e?.message || "No se pudo vincular el repo.");
    } finally {
      setLinking(false);
    }
  };

  const unlinkRepo = async () => {
    if (!confirm("¿Desvincular el repositorio de esta tarea?")) return;
    try {
      const res = await api.unlinkGitHubRepo(tarea.id);
      onChange(res.tarea);
      setResult(null);
      setPrStatus(null);
    } catch (e: any) {
      setError(e?.message || "No se pudo desvincular.");
    }
  };

  const develop = async () => {
    setDeveloping(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.agenteDesarrollar(tarea.id, prompt);
      if (res.ok) {
        setResult(res);
        refreshStatus();
      } else {
        setError(res.error || "El agente no pudo generar cambios.");
      }
    } catch (e: any) {
      setError(e?.message || "Error ejecutando el agente desarrollador.");
    } finally {
      setDeveloping(false);
    }
  };

  const merge = async () => {
    setMerging(true);
    setError(null);
    try {
      await api.mergeGitHubPR(tarea.id);
      refreshStatus();
    } catch (e: any) {
      setError(e?.message || "No se pudo mergear el PR.");
    } finally {
      setMerging(false);
    }
  };

  const refreshStatus = async () => {
    try {
      const res = await api.getGitHubStatus(tarea.id);
      onChange(res.tarea);
      setPrStatus(res.pr_status);
    } catch (e) {
      console.error(e);
    }
  };

  const isLinked = !!tarea.github_repo;
  const hasOpenPR = prStatus && !prStatus.merged && prStatus.state === "open";

  return (
    <div className="bg-card2 border border-border rounded-xl p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-text flex items-center gap-1.5">
          <Github size={14} /> GitHub
        </div>
        {config && !config.configured && (
          <span className="text-[10px] text-red-400">Configura tu token en el header</span>
        )}
      </div>

      {!isLinked ? (
        <div className="space-y-2">
          <div className="text-xs text-muted">Vincula un repositorio para que el agente pueda proponer cambios.</div>
          <div className="flex gap-2">
            <input
              className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted"
              placeholder="owner/repo o URL"
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
              onFocus={() => repos.length === 0 && loadRepos()}
            />
            <button
              onClick={loadRepos}
              disabled={loadingRepos}
              className="px-2 py-2 rounded-lg bg-card border border-border text-muted hover:text-text"
              title="Recargar repos"
            >
              {loadingRepos ? <Loader2 size={14} className="animate-spin" /> : <Github size={14} />}
            </button>
          </div>
          {repos.length > 0 && (
            <select
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text"
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
            >
              <option value="">Selecciona un repositorio...</option>
              {repos.map((r) => (
                <option key={r.full_name} value={r.full_name}>
                  {r.full_name}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={linkRepo}
            disabled={!selectedRepo.trim() || linking}
            className="w-full bg-accent text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
          >
            {linking ? <Loader2 size={14} className="animate-spin" /> : <Link size={14} />}
            Vincular repositorio
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <a
              href={`https://github.com/${tarea.github_repo}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-xs text-accent hover:underline truncate"
            >
              <Github size={12} /> {tarea.github_repo}
            </a>
            <button onClick={unlinkRepo} className="text-[10px] text-muted hover:text-red-400">
              <X size={12} />
            </button>
          </div>

          {prStatus && (
            <div className="flex items-center gap-2 text-xs">
              <GitPullRequest size={12} className={prStatus.merged ? "text-purple-400" : "text-green-400"} />
              <span className={prStatus.merged ? "text-purple-400" : "text-green-400"}>
                {prStatus.merged ? "Mergeado" : prStatus.state === "open" ? "PR abierto" : prStatus.state}
              </span>
              <a href={prStatus.url} target="_blank" rel="noreferrer" className="text-accent hover:underline flex items-center gap-0.5">
                Ver PR <ExternalLink size={10} />
              </a>
            </div>
          )}

          {!hasOpenPR && (
            <div className="space-y-2">
              <textarea
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted resize-none"
                rows={2}
                placeholder="Instrucciones opcionales para el agente (ej: 'crea un endpoint GET /health')"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
              <button
                onClick={develop}
                disabled={developing}
                className="w-full bg-slate-700 text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
              >
                {developing ? <Loader2 size={14} className="animate-spin" /> : <Code2 size={14} />}
                {developing ? "Agente desarrollando..." : "Desarrollar con agente"}
              </button>
            </div>
          )}

          {hasOpenPR && (
            <button
              onClick={merge}
              disabled={merging}
              className="w-full bg-green-600 text-white rounded-lg py-2 text-xs font-medium flex items-center justify-center gap-1 disabled:opacity-50"
            >
              {merging ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
              {merging ? "Mergeando..." : "Aprobar y mergear PR"}
            </button>
          )}
        </div>
      )}

      {result && result.ok && (
        <div className="bg-bg border border-border rounded-lg p-3 space-y-2 text-xs">
          <div className="font-medium text-text flex items-center gap-1">
            <GitBranch size={12} /> Rama {result.branch}
          </div>
          <div className="text-muted">{result.resumen}</div>
          <div>
            <span className="text-[10px] uppercase text-muted">Archivos</span>
            <div className="mt-1 space-y-0.5">
              {result.archivos.map((path: string) => (
                <div key={path} className="text-[10px] font-mono text-accent">{path}</div>
              ))}
            </div>
          </div>
          {result.pros?.length > 0 && (
            <div>
              <span className="text-[10px] uppercase text-green-400">Pros</span>
              <ul className="mt-1 space-y-0.5">
                {result.pros.map((p: string, i: number) => (
                  <li key={i} className="text-[10px] text-muted flex items-start gap-1"><Check size={10} className="text-green-400 mt-0.5" /> {p}</li>
                ))}
              </ul>
            </div>
          )}
          {result.contras?.length > 0 && (
            <div>
              <span className="text-[10px] uppercase text-red-400">Contras</span>
              <ul className="mt-1 space-y-0.5">
                {result.contras.map((c: string, i: number) => (
                  <li key={i} className="text-[10px] text-muted flex items-start gap-1"><AlertCircle size={10} className="text-red-400 mt-0.5" /> {c}</li>
                ))}
              </ul>
            </div>
          )}
          <a href={result.pr.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
            Ver pull request <ExternalLink size={10} />
          </a>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 text-red-400 text-xs p-2 rounded-lg flex items-start gap-1.5">
          <AlertCircle size={14} className="mt-0.5" /> {error}
        </div>
      )}
    </div>
  );
}
