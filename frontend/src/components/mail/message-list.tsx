import type { CSSProperties } from "react";
import { Archive, Mail, MailOpen, Paperclip, Star, Trash2 } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { ProviderIcon } from "@/components/mail/provider-icon";
import { categoryLabels, type MailAccount, type MailMessage } from "@/lib/mail-data";

export interface MessageRowData {
  message: MailMessage;
  account?: MailAccount | undefined;
  /** number of messages in the same conversation */
  threadCount: number;
}

interface MessageListProps {
  rows: MessageRowData[];
  selectedId: string | null;
  checkedIds: Set<string>;
  loading?: boolean;
  onOpen: (id: string) => void;
  onToggleCheck: (id: string) => void;
  onToggleStar: (id: string) => void;
  onToggleRead: (id: string, unread: boolean) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onPrefetch?: (id: string) => void;
  emptyHint?: string;
}

function categoryOf(message: MailMessage) {
  const main = message.categories.find((c) => c !== "criticos") ?? message.categories[0];
  return main ? (categoryLabels[main] ?? main) : "General";
}

export function MessageRow({
  data,
  selected,
  checked,
  onOpen,
  onToggleCheck,
  onToggleStar,
  onToggleRead,
  onArchive,
  onDelete,
  onPrefetch,
  animationIndex = 0,
}: {
  data: MessageRowData;
  selected: boolean;
  checked: boolean;
  onOpen: () => void;
  onToggleCheck: () => void;
  onToggleStar: () => void;
  onToggleRead: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onPrefetch?: () => void;
  animationIndex?: number;
}) {
  const { message, account, threadCount } = data;
  const unread = message.unread;

  return (
    <div
      role="button"
      style={{ "--mail-row-index": Math.min(animationIndex, 14) } as CSSProperties}
      tabIndex={0}
      onClick={onOpen}
      onMouseEnter={onPrefetch}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className={cn(
        "mail-message-row group relative flex cursor-pointer items-start gap-2 border-l-2 px-3 py-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50 md:items-center md:gap-2.5 md:px-4 md:py-2",
        selected
          ? "border-l-primary bg-primary/[0.07]"
          : message.critical
            ? "border-l-destructive/70 hover:bg-surface-2/70"
            : unread
              ? "border-l-primary/40 hover:bg-surface-2/70"
              : "border-l-transparent hover:bg-surface-2/50",
      )}
    >
      <div className="pt-0.5 md:pt-0" onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={checked}
          onCheckedChange={onToggleCheck}
          aria-label={`Seleccionar mensaje de ${message.senderName}`}
        />
      </div>

      <button
        type="button"
        aria-label={message.starred ? "Quitar destacado" : "Destacar"}
        onClick={(e) => {
          e.stopPropagation();
          onToggleStar();
        }}
        className="mt-0.5 grid size-4 shrink-0 place-items-center text-muted-foreground/60 transition-colors hover:text-warning md:mt-0"
      >
        <Star className={cn("size-3.5", message.starred && "fill-warning text-warning")} />
      </button>

      <div className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 md:grid-cols-[minmax(140px,0.8fr)_minmax(0,2.4fr)_auto] md:items-center md:gap-x-5">
        <div className="col-start-1 row-start-1 flex min-w-0 items-center gap-2">
          {account && <ProviderIcon provider={account.provider} className="size-4 shrink-0" />}
          <span className={cn("truncate text-[13px]", unread ? "font-semibold text-foreground" : "text-foreground/75")}>
            {message.senderName}
          </span>
          {threadCount > 1 && (
            <span className="shrink-0 rounded bg-surface-3 px-1 text-[10px] tabular-nums text-muted-foreground">
              {threadCount}
            </span>
          )}
        </div>

        <div className="col-span-2 col-start-1 row-start-2 flex min-w-0 items-baseline gap-1 md:col-span-1 md:col-start-2 md:row-start-1">
          <span className={cn("shrink-0 truncate text-[13px] md:max-w-[45%]", unread ? "font-semibold text-foreground" : "text-foreground/85")}>
            {message.subject}
          </span>
          <span className="min-w-0 flex-1 truncate text-[12.5px] text-muted-foreground">
            <span aria-hidden>— </span>{message.preview}
          </span>
          {message.attachments.length > 0 && <Paperclip className="size-3.5 shrink-0 text-muted-foreground" aria-label="Tiene adjuntos" />}
          {message.critical && <span className="hidden shrink-0 rounded bg-destructive/12 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-destructive lg:inline">Crítico</span>}
          {!message.critical && message.categories.length > 0 && <span className="hidden shrink-0 rounded bg-surface-3 px-1.5 py-0.5 text-[9px] text-muted-foreground xl:inline">{categoryOf(message)}</span>}
        </div>

        <div className="col-start-2 row-start-1 flex shrink-0 items-center gap-1 md:col-start-3">
        <div className="hidden items-center rounded-md bg-card shadow-sm ring-1 ring-border group-hover:flex group-focus-within:flex">
          <QuickAction icon={unread ? MailOpen : Mail} label={unread ? "Marcar como leído" : "Marcar como no leído"} onClick={onToggleRead} />
          <QuickAction icon={Archive} label="Archivar" onClick={onArchive} />
          <QuickAction icon={Trash2} label="Eliminar" onClick={onDelete} />
        </div>
        <span
          className={cn(
            "text-[11px] tabular-nums md:hidden",
            unread ? "font-semibold text-foreground" : "text-muted-foreground",
          )}
        >
          {message.time}
        </span>
        <span className={cn("hidden whitespace-nowrap text-[11px] tabular-nums md:inline", unread ? "font-semibold text-foreground" : "text-muted-foreground")}>{message.date}</span>
        {unread && <span className="size-1.5 rounded-full bg-primary" />}
        </div>
      </div>
    </div>
  );
}

export function MessageListSkeleton() {
  return (
    <div className="divide-y divide-border/60">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex gap-3 px-4 py-3">
          <div className="size-4 animate-pulse rounded bg-surface-2" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-1/3 animate-pulse rounded bg-surface-2" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-surface-2" />
            <div className="h-2.5 w-1/2 animate-pulse rounded bg-surface-2/70" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function MessageList({
  rows,
  selectedId,
  checkedIds,
  loading,
  onOpen,
  onToggleCheck,
  onToggleStar,
  onToggleRead,
  onArchive,
  onDelete,
  onPrefetch,
  emptyHint,
}: MessageListProps) {
  if (loading) {
    return (
      <div className="scroll-slim flex-1 overflow-y-auto">
        <MessageListSkeleton />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="mail-empty-list flex flex-1 flex-col items-center justify-center gap-2 p-10 text-center">
        <p className="text-sm font-medium text-foreground">Sin mensajes</p>
        <p className="max-w-xs text-[12.5px] leading-relaxed text-muted-foreground">
          {emptyHint ?? "No hay correos que coincidan con esta vista, cuenta o búsqueda."}
        </p>
      </div>
    );
  }

  return (
    <div className="mail-message-list scroll-slim flex-1 divide-y divide-border/60 overflow-y-auto">
      {rows.map((row, index) => (
        <MessageRow
          key={row.message.id}
          data={row}
          selected={selectedId === row.message.id}
          checked={checkedIds.has(row.message.id)}
          onOpen={() => onOpen(row.message.id)}
          onToggleCheck={() => onToggleCheck(row.message.id)}
          onToggleStar={() => onToggleStar(row.message.id)}
          onToggleRead={() => onToggleRead(row.message.id, row.message.unread)}
          onArchive={() => onArchive(row.message.id)}
          onDelete={() => onDelete(row.message.id)}
          onPrefetch={() => onPrefetch?.(row.message.id)}
          animationIndex={index}
        />
      ))}
    </div>
  );
}

function QuickAction({ icon: Icon, label, onClick }: { icon: typeof Archive; label: string; onClick: () => void }) {
  return <button type="button" title={label} aria-label={label} onClick={(event) => { event.stopPropagation(); onClick(); }} className="grid size-8 place-items-center text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"><Icon className="size-3.5" /></button>;
}
