import { Volume2, Volume1, VolumeX, Sparkles, Settings2 } from "lucide-react";
import type { TTSVoiceSettings } from "../hooks/useVoice";

interface Props {
  voices: SpeechSynthesisVoice[];
  settings: TTSVoiceSettings;
  onChange: (patch: Partial<TTSVoiceSettings>) => void;
  premiumAvailable: boolean;
}

export function VoiceSettings({ voices, settings, onChange, premiumAvailable }: Props) {
  const esVoces = voices.filter((v) => v.lang.toLowerCase().startsWith("es"));

  return (
    <div className="bg-bg border border-border rounded-xl p-3 mb-3 space-y-3">
      <div className="flex items-center gap-2 text-accent text-xs font-semibold">
        <Settings2 size={14} />
        Configuración de voz
      </div>

      {/* Premium toggle */}
      {premiumAvailable && (
        <label className="flex items-center justify-between cursor-pointer">
          <span className="flex items-center gap-1.5 text-sm text-text">
            <Sparkles size={14} className="text-accent" />
            Voz premium (OpenAI TTS)
          </span>
          <input
            type="checkbox"
            checked={settings.usePremium}
            onChange={(e) => onChange({ usePremium: e.target.checked })}
            className="accent-accent w-4 h-4"
          />
        </label>
      )}
      {!premiumAvailable && (
        <p className="text-[10px] text-muted">
          Voz premium no disponible. Añade OPENAI_API_KEY en el backend para activar TTS más natural.
        </p>
      )}

      {/* Voice selector */}
      <div>
        <label className="text-[10px] text-muted uppercase tracking-wide block mb-1">Voz del navegador</label>
        <select
          value={settings.voiceURI || ""}
          onChange={(e) => onChange({ voiceURI: e.target.value || null })}
          className="w-full bg-card2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
          disabled={settings.usePremium}
        >
          <option value="">Auto (mejor español)</option>
          {esVoces.map((v) => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {v.name} ({v.lang}){v.default ? " ★" : ""}
            </option>
          ))}
        </select>
      </div>

      {/* Rate */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-[10px] text-muted uppercase tracking-wide">Velocidad</label>
          <span className="text-[10px] text-accent font-mono">{settings.rate.toFixed(1)}x</span>
        </div>
        <input
          type="range"
          min={0.5}
          max={1.5}
          step={0.1}
          value={settings.rate}
          onChange={(e) => onChange({ rate: parseFloat(e.target.value) })}
          className="w-full accent-accent"
          disabled={settings.usePremium}
        />
      </div>

      {/* Pitch */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-[10px] text-muted uppercase tracking-wide">Tono</label>
          <span className="text-[10px] text-accent font-mono">{settings.pitch.toFixed(1)}</span>
        </div>
        <input
          type="range"
          min={0.5}
          max={1.5}
          step={0.1}
          value={settings.pitch}
          onChange={(e) => onChange({ pitch: parseFloat(e.target.value) })}
          className="w-full accent-accent"
          disabled={settings.usePremium}
        />
      </div>

      {/* Preview button */}
      <button
        onClick={() => {
          const u = new SpeechSynthesisUtterance("Hola, soy Jarvis. Así suena mi voz ahora.");
          u.lang = "es-ES";
          u.rate = settings.rate;
          u.pitch = settings.pitch;
          if (settings.voiceURI) {
            const v = voices.find((v) => v.voiceURI === settings.voiceURI);
            if (v) u.voice = v;
          } else {
            const v = voices.find((v) => v.lang.toLowerCase().startsWith("es"));
            if (v) u.voice = v;
          }
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(u);
        }}
        disabled={settings.usePremium}
        className="w-full flex items-center justify-center gap-2 bg-card2 border border-border rounded-lg py-2 text-sm text-muted hover:text-text disabled:opacity-40 transition-colors"
      >
        <Volume2 size={14} />
        Escuchar voz nativa
      </button>
    </div>
  );
}
