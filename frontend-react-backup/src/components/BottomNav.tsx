import { ListTodo, CheckCircle2, Bell, Columns3, Calendar } from "lucide-react";
import type { TabKey } from "../types";

const TABS: { key: TabKey; label: string; icon: typeof ListTodo }[] = [
  { key: "pendientes", label: "Pendientes", icon: ListTodo },
  { key: "completadas", label: "Completadas", icon: CheckCircle2 },
  { key: "calendario", label: "Calendario", icon: Calendar },
  { key: "alarmas", label: "Alarmas", icon: Bell },
  { key: "kanban", label: "Kanban", icon: Columns3 },
];

export function BottomNav({ tab, onChange }: { tab: TabKey; onChange: (t: TabKey) => void }) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-card border-t border-border safe-bottom">
      <div className="flex items-center justify-around max-w-lg mx-auto h-16">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors ${
              tab === key ? "text-accent" : "text-muted"
            }`}
          >
            <Icon size={22} strokeWidth={tab === key ? 2.5 : 2} />
            <span className="text-[10px] font-medium">{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
