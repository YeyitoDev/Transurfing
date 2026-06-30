import { useEffect, useState } from "react";
import { X, Github, Check, AlertCircle, Loader2, Save } from "lucide-react";
import { api } from "../api";

interface Props {
  onClose: () => void;
}

export function GitHubSettings({ onClose }: Props) {
  const [pat, setPat] = useState("");
  const [username, setUsername] = useState("");
  const [config, setConfig] = useState<{ username: string; configured: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    api.getGitHubConfig().then(setConfig).catch(() => setConfig({ username: "", configured: false }));
  }, []);

  const save = async () => {
    if (!pat.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await api.setGitHubConfig(pat, username);
      setConfig({ username: res.username, configured: true });
      setMessage({ type: "ok", text: `Conectado como @${res.username} (scopes: ${res.scopes.join(", ") || "repo"})` });
      setPat("");
    } catch (e: any) {
      setMessage({ type: "error", text: e?.message || "No se pudo validar el token. Revisa el PAT." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Github size={18} className="text-text" /> Configuración GitHub
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-card2 text-muted">
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="text-xs text-muted leading-relaxed">
            Conecta tu cuenta de GitHub con un token personal (PAT) para que los agentes puedan crear ramas y pull requests.
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted">GitHub Personal Access Token</label>
            <input
              type="password"
              className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text placeholder-muted"
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              value={pat}
              onChange={(e) => setPat(e.target.value)}
            />
            <p className="text-[10px] text-muted">
              Crea uno en Settings → Developer settings → Personal access tokens → Tokens (classic). Scopes: <span className="text-accent">repo</span>.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted">Usuario GitHub (opcional)</label>
            <input
              className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text placeholder-muted"
              placeholder="tu-usuario"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          {message && (
            <div className={`flex items-start gap-2 p-2 rounded-lg text-xs ${message.type === "ok" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
              {message.type === "ok" ? <Check size={14} className="mt-0.5" /> : <AlertCircle size={14} className="mt-0.5" />}
              {message.text}
            </div>
          )}

          {config?.configured && (
            <div className="flex items-center gap-2 text-xs text-green-400">
              <Check size={14} /> Actualmente conectado como @{config.username || "?"}
            </div>
          )}

          <button
            onClick={save}
            disabled={!pat.trim() || loading}
            className="w-full bg-accent text-white rounded-xl py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Guardar y validar
          </button>
        </div>
      </div>
    </div>
  );
}
