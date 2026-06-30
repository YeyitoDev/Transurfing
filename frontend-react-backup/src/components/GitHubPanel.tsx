import { useEffect, useState } from "react";
import { Github, Link, Unlink, GitPullRequest, Check, Loader2, AlertCircle, RefreshCw, Play } from "lucide-react";
import type { Tarea, GitHubRepo } from "../types";
import { api } from "../api";

interface Props {
  tarea: Tarea;
  onChange: (t: Tarea) => void;
}

export function GitHubPanel({ tarea, onChange }: Props) {
  const [config, setConfig] = useState<{ username: string; configured: boolean } | null>(null);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [loading, setLoading] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [pat, setPat] = useState("");
  const [username, setUsername] = useState("");
  const [agentePrompt, setAgentePrompt] = useState("");
  const [agenteLoading, setAgenteLoading] = useState(false);
  const [agenteResult, setAgenteResult] = useState<any>(null);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg = await api.getGitHubConfig();
      setConfig(cfg);
      if (cfg.configured) {
        const r = await api.listGitHubRepos();
        setRepos(r.repos);
      }
      if (tarea.github_repo) {
        const status = await api.getGitHubStatus(tarea.id);
        onChange(status.tarea);
      }
    } catch (e: any) {
      setError(e?.message || "Error cargando GitHub");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const guardarConfig = async () => {
    if (!pat.trim()) return;
    setLoading(true);
    try {
      const res = await api.setGitHubConfig(pat, username);
      setConfig({ username: res.username, configured: true });
      setConfigOpen(false);
      setPat("");
      await cargar();
    } catch (e: any) {
      setError(e?.message || "Error validando PAT");
    } finally {
      setLoading(false);
    }
  };

  const vincular = async (repoFullName: string) => {
    setLoading(true);
    try {
      const res = await api.linkGitHubRepo(tarea.id, repoFullName);
      onChange(res.tarea);
    } catch (e: any) {
      setError(e?.message || "Error vinculando repo");
    } finally {
      setLoading(false);
    }
  };

  const desvincular = async () => {
    if (!confirm("¿Desvincular el repositorio de esta tarea?")) return;
    setLoading(true);
    try {
      const res = await api.unlinkGitHubRepo(tarea.id);
      onChange(res.tarea);
    } catch (e: any) {
      setError(e?.message || "Error desvinculando");
    } finally {
      setLoading(false);
    }
  };

  const ejecutarAgente = async () => {
    setAgenteLoading(true);
    setAgenteResult(null);
    setError(null);
    try {
      const res = await api.agenteDesarrollar(tarea.id, agentePrompt);
      setAgenteResult(res);
      const status = await api.getGitHubStatus(tarea.id);
      onChange(status.tarea);
    } catch (e: any) {
      setError(e?.message || "Error ejecutando agente");
    } finally {
      setAgenteLoading(false);
    }
  };

  const merge = async () => {
    setMergeLoading(true);
    try {
      await api.mergeGitHubPR(tarea.id);
      const status = await api.getGitHubStatus(tarea.id);
      onChange(status.tarea);
    } catch (e: any) {
      setError(e?.message || "Error mergeando PR");
    } finally {
      setMergeLoading(false);
    }
  };

  return (
    <div className="bg-card2 border border-border rounded-2xl overflow-hidden flex flex-col h-fit lg:h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Github size={16} className="text-accent" />
          <span className="text-sm font-semibold text-text">GitHub</span>
        </div>
        <div className="flex items-center gap-2">
          {!config?.configured ? (
            <button
              onClick={() => setConfigOpen(true)}
              className="text-[10px] bg-accent text-white rounded-lg px-2.5 py-1.5"
            >
              Configurar PAT
            </button>
          ) : (
            <span className="text-[10px] text-muted flex items-center gap-1">
              <Check size={10} className="text-green" /> {config.username}
            </span>
          )}
          <button onClick={cargar} disabled={loading} className="text-muted hover:text-text disabled:opacity-50">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {error && (
          <div className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-start gap-2">
            <AlertCircle size={12} className="mt-0.5 shrink-0" /> {error}
          </div>
        )}

        {configOpen && (
          <div className="bg-bg border border-border rounded-xl p-3 space-y-2">
            <div className="text-xs font-semibold text-text">Configurar GitHub PAT</div>
            <input
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted"
              type="password"
              placeholder="ghp_xxxxxxxx"
              value={pat}
              onChange={(e) => setPat(e.target.value)}
            />
            <input
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted"
              placeholder="Usuario (opcional)"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <div className="flex gap-2">
              <button onClick={guardarConfig} disabled={loading} className="flex-1 bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-50">
                {loading ? <Loader2 size={10} className="animate-spin" /> : "Guardar"}
              </button>
              <button onClick={() => setConfigOpen(false)} className="px-3 py-2 text-xs text-muted hover:text-text border border-border rounded-lg">Cancelar</button>
            </div>
          </div>
        )}

        {!config?.configured && !configOpen && (
          <div className="text-center text-[11px] text-muted py-4">
            Configura tu PAT de GitHub para vincular repositorios.
          </div>
        )}

        {config?.configured && !tarea.github_repo && (
          <div>
            <div className="text-xs font-semibold text-text mb-2">Vincular repositorio</div>
            {repos.length === 0 ? (
              <div className="text-[10px] text-muted">No se encontraron repositorios.</div>
            ) : (
              <div className="max-h-[160px] overflow-y-auto space-y-1 pr-1">
                {repos.map((r) => (
                  <button
                    key={r.full_name}
                    onClick={() => vincular(r.full_name)}
                    className="w-full text-left px-3 py-2 rounded-lg bg-bg border border-border hover:border-accent text-xs text-text flex items-center justify-between"
                  >
                    <span className="truncate">{r.full_name}</span>
                    <Link size={12} className="text-muted shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tarea.github_repo && (
          <div className="space-y-3">
            <div className="flex items-center justify-between bg-bg border border-border rounded-lg px-3 py-2">
              <div className="text-xs text-text truncate pr-2">{tarea.github_repo}</div>
              <button onClick={desvincular} className="text-muted hover:text-red"><Unlink size={12} /></button>
            </div>

            {tarea.github_pr_url && (
              <div className="bg-accent/5 border border-accent/20 rounded-lg p-3">
                <div className="flex items-center gap-2 text-xs text-accent mb-1">
                  <GitPullRequest size={12} /> PR abierto
                </div>
                <a href={tarea.github_pr_url} target="_blank" rel="noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300 break-all">
                  {tarea.github_pr_url}
                </a>
                <div className="text-[10px] text-muted mt-1">Estado: {tarea.github_status}</div>
                {tarea.github_status === "pr_open" && (
                  <button onClick={merge} disabled={mergeLoading} className="mt-2 text-[10px] bg-green-500/15 text-green-400 border border-green-500/20 rounded-lg px-2.5 py-1.5 flex items-center gap-1 disabled:opacity-50">
                    {mergeLoading ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
                    Merge PR
                  </button>
                )}
              </div>
            )}

            <div className="bg-bg border border-border rounded-lg p-3">
              <div className="text-xs font-semibold text-text mb-2 flex items-center gap-1.5">
                <Play size={12} className="text-accent" /> Agente desarrollador
              </div>
              <textarea
                className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-text placeholder-muted mb-2"
                rows={3}
                placeholder="Instrucciones adicionales para el agente (opcional)"
                value={agentePrompt}
                onChange={(e) => setAgentePrompt(e.target.value)}
              />
              <button
                onClick={ejecutarAgente}
                disabled={agenteLoading}
                className="w-full bg-accent text-white rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {agenteLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                {agenteLoading ? "Desarrollando..." : "Crear rama y PR"}
              </button>
            </div>

            {agenteResult && (
              <div className="bg-bg border border-border rounded-lg p-3">
                <div className="text-xs font-semibold text-text mb-1">Resultado</div>
                {agenteResult.error ? (
                  <div className="text-[10px] text-red-400">{agenteResult.error}</div>
                ) : (
                  <div className="space-y-1">
                    <div className="text-[10px] text-muted">{agenteResult.resumen}</div>
                    {agenteResult.archivos && (
                      <div className="text-[10px] text-muted">
                        Archivos: {agenteResult.archivos.join(", ")}
                      </div>
                    )}
                    {agenteResult.pr && (
                      <a href={agenteResult.pr.url} target="_blank" rel="noreferrer" className="text-[10px] text-blue-400 hover:text-blue-300">
                        Ver PR #{agenteResult.pr.number}
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
