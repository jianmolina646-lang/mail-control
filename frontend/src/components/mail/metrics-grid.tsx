import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export interface Metric {
  id: string;
  label: string;
  value: number;
  icon: LucideIcon;
  tone?: "default" | "warning" | "danger" | "primary";
  onClick?: () => void;
}

const toneClass = {
  default: "bg-slate-500/10 text-slate-600 dark:text-slate-400",
  primary: "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400",
  warning: "bg-amber-500/12 text-amber-600 dark:text-amber-400",
  danger: "bg-red-500/12 text-red-600 dark:text-red-400",
} as const;

export function MetricsGrid({ metrics, className }: { metrics: Metric[]; className?: string }) {
  return (
    <div
      className={cn(
        "mail-metrics-grid grid grid-cols-2 gap-1.5 sm:grid-cols-3 xl:grid-cols-6",
        className,
      )}
    >
      {metrics.map((m, index) => {
        const Comp = m.onClick ? "button" : "div";
        return (
          <Comp
            key={m.id}
            style={{ "--metric-index": index } as CSSProperties}
            {...(m.onClick ? { type: "button" as const, onClick: m.onClick } : {})}
            className={cn(
              `mail-metric-card mail-metric-card--${m.tone ?? "default"} flex items-center gap-2 rounded-lg border border-border bg-surface-2/40 px-2.5 py-1.5 text-left transition-colors`,
              m.onClick && "hover:border-border-strong hover:bg-surface-2",
            )}
          >
            <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg", toneClass[m.tone ?? "default"])}>
              <m.icon className="size-3.5" strokeWidth={2} />
            </span>
            <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
              {m.label}
            </span>
            <span className="text-[13px] font-semibold tabular-nums text-foreground">
              {m.value}
            </span>
          </Comp>
        );
      })}
    </div>
  );
}
