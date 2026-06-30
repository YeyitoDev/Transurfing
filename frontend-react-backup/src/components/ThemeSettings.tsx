import { X, RotateCcw, Palette, Check } from "lucide-react";
import { useTheme, COLOR_LABELS, PRESETS, type ThemeColors } from "../hooks/useTheme";

interface Props {
  onClose: () => void;
}

function colorsEqual(a: ThemeColors, b: ThemeColors): boolean {
  return (Object.keys(a) as (keyof ThemeColors)[]).every((k) => a[k].toLowerCase() === b[k].toLowerCase());
}

export function ThemeSettings({ onClose }: Props) {
  const { colors, setColor, applyPreset, reset } = useTheme();

  const keys = Object.keys(COLOR_LABELS) as (keyof ThemeColors)[];

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-md max-h-[85vh] overflow-y-auto animate-slide-up">
        {/* Header */}
        <div className="sticky top-0 bg-card border-b border-border px-5 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <Palette size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text">Personalizar colores</h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-text p-1">
            <X size={20} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* Presets */}
          <div>
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Temas predefinidos</h3>
            <div className="grid grid-cols-3 gap-2">
              {PRESETS.map((preset) => {
                const active = colorsEqual(colors, preset.colors);
                return (
                  <button
                    key={preset.name}
                    onClick={() => applyPreset(preset.colors)}
                    className={`relative rounded-xl border p-2 transition-all hover:scale-[1.03] ${
                      active ? "border-accent ring-2 ring-accent/40" : "border-border"
                    }`}
                    style={{ background: preset.colors.bg }}
                  >
                    <div className="flex gap-1 mb-1.5 justify-center">
                      {[preset.colors.accent, preset.colors.green, preset.colors.red].map((c, i) => (
                        <span key={i} className="w-3 h-3 rounded-full" style={{ background: c }} />
                      ))}
                    </div>
                    <span className="text-[10px] font-medium block text-center" style={{ color: preset.colors.text }}>
                      {preset.name}
                    </span>
                    {active && (
                      <span className="absolute -top-1.5 -right-1.5 bg-accent text-white rounded-full p-0.5">
                        <Check size={10} strokeWidth={3} />
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Color pickers individuales */}
          <div>
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Ajuste personalizado</h3>
            <div className="space-y-2">
              {keys.map((key) => (
                <div key={key} className="flex items-center justify-between bg-bg rounded-xl px-3 py-2 border border-border">
                  <span className="text-sm text-text">{COLOR_LABELS[key]}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted font-mono uppercase">{colors[key]}</span>
                    <label className="relative cursor-pointer">
                      <span
                        className="block w-8 h-8 rounded-lg border-2 border-border shadow-inner"
                        style={{ background: colors[key] }}
                      />
                      <input
                        type="color"
                        value={colors[key]}
                        onChange={(e) => setColor(key, e.target.value)}
                        className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reset */}
          <button
            onClick={reset}
            className="w-full flex items-center justify-center gap-2 bg-bg border border-border rounded-xl py-2.5 text-sm text-muted hover:text-text transition-colors"
          >
            <RotateCcw size={15} />
            Restaurar colores por defecto
          </button>
        </div>
      </div>
    </div>
  );
}
