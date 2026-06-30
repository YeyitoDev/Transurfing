export function ProgressBar({ pct }: { pct: number }) {
  const full = pct >= 100;
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${full ? "bg-green" : "bg-accent"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] text-muted min-w-[30px] text-right">{Math.round(pct)}%</span>
    </div>
  );
}
