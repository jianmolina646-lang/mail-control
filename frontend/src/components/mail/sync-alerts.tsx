import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Pause,
  Play,
  RefreshCw,
  Settings2,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ProviderIcon } from "@/components/mail/provider-icon";
import {
  attentionStatuses,
  syncStatusLabels,
  type MailAccount,
  type SyncStatus,
} from "@/lib/mail-data";

const statusTone: Record<SyncStatus, string> = {
  conectada: "text-primary",
  sincronizando: "text-primary",
  "requiere-autorizacion": "text-warning",
  "credenciales-vencidas": "text-warning",
  error: "text-destructive",
  pausada: "text-muted-foreground",
};

export function SyncAlerts({
  accounts,
  onSelectAccount,
  onRetry,
  onReauthorize,
  onConfigure,
  className,
}: {
  accounts: MailAccount[];
  onSelectAccount: (id: string) => void;
  onRetry?: (id: string) => void;
  onReauthorize?: (id: string) => void;
  onConfigure?: () => void;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const needsAttention = accounts.filter((a) => attentionStatuses.includes(a.status));
  if (needsAttention.length === 0) return null;

  return (
    <section className={cn("space-y-1.5", className)} aria-label="Cuentas que requieren atención">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 rounded-lg border border-warning/25 bg-warning/[0.07] px-2.5 py-1.5 text-[12px] text-warning md:hidden"
      >
        <AlertTriangle className="size-3.5" />
        {needsAttention.length} cuentas requieren atención
        <ChevronDown className={cn("ml-auto size-3.5 transition-transform", expanded && "rotate-180")} />
      </button>
      <div className={cn("space-y-1.5", expanded ? "block" : "hidden md:block")}>
      {needsAttention.map((a) => (
        <div
          key={a.id}
          className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-2 rounded-lg border border-border bg-surface-2/40 px-2.5 py-2 sm:flex sm:items-center sm:gap-3"
        >
          <span className="flex items-center gap-2">
            <ProviderIcon provider={a.provider} className="size-4" />
            {a.status === "error" ? (
              <ShieldAlert className="size-3.5 shrink-0 text-destructive" />
            ) : (
              <AlertTriangle className={cn("size-3.5 shrink-0", statusTone[a.status])} />
            )}
          </span>
          <div className="min-w-0 sm:flex-1">
            <p className="truncate text-[12.5px] font-medium text-foreground">
              {a.alias}{" "}
              <span className={cn("font-normal", statusTone[a.status])}>
                · {syncStatusLabels[a.status]}
              </span>
            </p>
            <p className="truncate text-[11px] text-muted-foreground">
              {a.statusDetail ?? a.email}
            </p>
          </div>
          <div className="col-span-2 flex flex-wrap items-center gap-1 sm:col-auto sm:shrink-0">
            {a.status === "requiere-autorizacion" && <Action icon={ShieldAlert} label="Reautorizar" onClick={() => onReauthorize?.(a.id)} />}
            {(a.status === "error" || a.status === "credenciales-vencidas") && (
              <Action icon={RefreshCw} label="Reintentar" onClick={() => onRetry?.(a.id)} />
            )}
            {a.status === "error" && <Action icon={AlertTriangle} label="Ver error" />}
            {a.status === "pausada" ? (
              <Action icon={Play} label="Reanudar" />
            ) : (
              <Action icon={Pause} label="Pausar" />
            )}
            <Action icon={Settings2} label="Configurar" onClick={() => { onSelectAccount(a.id); onConfigure?.(); }} />
          </div>
        </div>
      ))}
      </div>
    </section>
  );
}

function Action({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof RefreshCw;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-7 items-center gap-1.5 rounded-md border border-border bg-surface-3/50 px-2 text-[11px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <Icon className="size-3" />
      {label}
    </button>
  );
}
