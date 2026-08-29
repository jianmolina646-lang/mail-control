import {
  Archive,
  BellPlus,
  Check,
  Clock,
  Download,
  Mail,
  MailOpen,
  RefreshCw,
  Star,
  Tag,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface BulkActionsProps {
  count: number;
  onClear: () => void;
  onRead: () => void;
  onUnread: () => void;
  onStar: () => void;
  onArchive: () => void;
  onDelete: () => void;
  className?: string;
}

export function BulkActions({
  count,
  onClear,
  onRead,
  onUnread,
  onStar,
  onArchive,
  onDelete,
  className,
}: BulkActionsProps) {
  if (count === 0) return null;
  return (
    <div
      className={cn(
        "scroll-slim flex items-center gap-1 overflow-x-auto border-b border-border bg-surface-2/50 px-3 py-2",
        className,
      )}
    >
      <span className="mr-1 shrink-0 rounded bg-primary/15 px-1.5 py-0.5 text-[11px] font-semibold text-primary">
        {count}
      </span>
      <Item icon={MailOpen} label="Leído" onClick={onRead} />
      <Item icon={Mail} label="No leído" onClick={onUnread} />
      <Item icon={Star} label="Destacar" onClick={onStar} />
      <Item icon={Archive} label="Archivar" onClick={onArchive} />
      <Item icon={Check} label="Revisado" />
      <Item icon={Clock} label="Posponer" />
      <Item icon={UserPlus} label="Asignar" />
      <Item icon={Tag} label="Etiqueta" />
      <Item icon={BellPlus} label="Alerta" />
      <Item icon={RefreshCw} label="Reprocesar" />
      <Item icon={Download} label="Exportar" />
      <Item icon={Trash2} label="Eliminar" onClick={onDelete} tone="destructive" />
      <button
        type="button"
        onClick={onClear}
        aria-label="Cancelar selección"
        className="ml-auto grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-surface-3 hover:text-foreground"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

function Item({
  icon: Icon,
  label,
  onClick,
  tone,
}: {
  icon: typeof Mail;
  label: string;
  onClick?: () => void;
  tone?: "destructive";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-[11.5px] text-muted-foreground transition-colors hover:bg-surface-3 hover:text-foreground",
        tone === "destructive" && "hover:bg-destructive/12 hover:text-destructive",
      )}
    >
      <Icon className="size-3.5" />
      {label}
    </button>
  );
}
