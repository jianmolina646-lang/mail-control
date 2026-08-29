import { Bookmark } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  folderGroupLabels,
  folders,
  savedViews,
  type FolderGroup,
  type FolderId,
} from "@/lib/mail-data";

interface FolderNavProps {
  activeFolder: FolderId;
  onSelect: (id: FolderId) => void;
  counts: Record<string, number>;
  onApplyView?: (query: string) => void;
  activeView?: string | null;
  className?: string;
}

const groupOrder: FolderGroup[] = ["principal", "categorias", "sistema"];

const folderIconClass: Record<FolderId, string> = {
  todos: "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400",
  "no-leidos": "bg-cyan-500/12 text-cyan-600 dark:text-cyan-400",
  destacados: "bg-amber-500/14 text-amber-600 dark:text-amber-400",
  criticos: "bg-red-500/12 text-red-600 dark:text-red-400",
  pagos: "bg-blue-500/12 text-blue-600 dark:text-blue-400",
  renovaciones: "bg-violet-500/12 text-violet-600 dark:text-violet-400",
  seguridad: "bg-teal-500/12 text-teal-600 dark:text-teal-400",
  codigos: "bg-orange-500/12 text-orange-600 dark:text-orange-400",
  facturas: "bg-indigo-500/12 text-indigo-600 dark:text-indigo-400",
  promociones: "bg-pink-500/12 text-pink-600 dark:text-pink-400",
  archivados: "bg-slate-500/12 text-slate-600 dark:text-slate-400",
  papelera: "bg-rose-500/12 text-rose-600 dark:text-rose-400",
  vistas: "bg-purple-500/12 text-purple-600 dark:text-purple-400",
};

export function FolderNav({
  activeFolder,
  onSelect,
  counts,
  onApplyView,
  activeView,
  className,
}: FolderNavProps) {
  return (
    <nav className={cn("scroll-slim space-y-4 overflow-y-auto p-2", className)}>
      {groupOrder.map((group) => (
        <div key={group} className="space-y-0.5">
          <p className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70">
            {folderGroupLabels[group]}
          </p>
          {folders
            .filter((f) => f.group === group)
            .map((folder) => {
              const active = folder.id === activeFolder;
              const count = counts[folder.id] ?? 0;
              const showCount = folder.showCount && count > 0;
              return (
                <button
                  key={folder.id}
                  type="button"
                  onClick={() => onSelect(folder.id)}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "mail-folder-item grid w-full grid-cols-[26px_minmax(0,1fr)_auto] items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                    active
                      ? "bg-primary/12 font-semibold text-primary"
                      : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
                  )}
                >
                  <span className={cn("grid size-[26px] shrink-0 place-items-center rounded-lg", folderIconClass[folder.id])}>
                    <folder.icon className="size-3.5" strokeWidth={2} />
                  </span>
                  <span className="truncate text-left">{folder.label}</span>
                  {showCount && (
                    <span
                      className={cn(
                        "rounded px-1 text-[11px] tabular-nums",
                        active ? "text-primary" : "text-muted-foreground/80",
                      )}
                    >
                      {count > 999 ? "999+" : count}
                    </span>
                  )}
                </button>
              );
            })}
          {group === "sistema" && onApplyView && (
            <div className="space-y-0.5 pt-1">
              {savedViews.map((view) => (
                <button
                  key={view.id}
                  type="button"
                  onClick={() => onApplyView(view.query)}
                  className={cn(
                    "grid w-full grid-cols-[26px_minmax(0,1fr)] items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] transition-colors",
                    activeView === view.query
                      ? "bg-primary/12 font-semibold text-primary"
                      : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
                  )}
                >
                  <span className="grid size-[26px] shrink-0 place-items-center rounded-lg bg-purple-500/12 text-purple-600 dark:text-purple-400">
                    <Bookmark className="size-3.5" strokeWidth={2} />
                  </span>
                  <span className="truncate text-left">{view.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </nav>
  );
}
