import type { CSSProperties } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, ChevronsUpDown, MoreHorizontal, Star } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AccountProviderLogo, ProviderBrandLogo } from "@/components/mail/brand-logos";
import { cn } from "@/lib/utils";
import { providerLabels, syncStatusLabels, type MailAccount, type SyncStatus } from "@/lib/mail-data";

export type AccountSortKey = "cuenta" | "proveedor" | "estado" | "sync" | "mensajes" | "alertas";
export interface AccountStats { messages: number; unread: number; alerts: number; }
export interface AccountActions {
  sync: (account: MailAccount) => void;
  inbox: (account: MailAccount) => void;
  reauthorize: (account: MailAccount) => void;
}

interface AccountsTableProps {
  accounts: MailAccount[];
  stats: (account: MailAccount) => AccountStats;
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  sortKey: AccountSortKey;
  sortDir: "asc" | "desc";
  onSort: (key: AccountSortKey) => void;
  density: "comoda" | "compacta";
  actions: AccountActions;
  canManage: boolean;
  className?: string;
}

const statusTone: Record<SyncStatus, string> = {
  conectada: "border-primary/30 bg-primary/10 text-primary",
  sincronizando: "border-chart-2/30 bg-chart-2/10 text-chart-2",
  "requiere-autorizacion": "border-warning/30 bg-warning/10 text-warning",
  "credenciales-vencidas": "border-warning/30 bg-warning/10 text-warning",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  pausada: "border-border-strong bg-surface-3/60 text-muted-foreground",
};
const statusDot: Record<SyncStatus, string> = {
  conectada: "bg-primary",
  sincronizando: "bg-chart-2 animate-pulse",
  "requiere-autorizacion": "bg-warning",
  "credenciales-vencidas": "bg-warning",
  error: "bg-destructive",
  pausada: "bg-muted-foreground",
};
const gridCols = "grid-cols-[28px_minmax(0,1fr)_84px] md:grid-cols-[28px_minmax(0,1.6fr)_minmax(0,1fr)_120px_72px_64px_32px] xl:grid-cols-[28px_minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,0.9fr)_140px_150px_84px_70px_32px]";

export function AccountsTable({ accounts, stats, selected, onToggle, onToggleAll, sortKey, sortDir, onSort, density, actions, canManage, className }: AccountsTableProps) {
  const allChecked = accounts.length > 0 && accounts.every((account) => selected.has(account.id));
  const rowPad = density === "compacta" ? "py-2" : "py-3";
  return (
    <div className={cn("accounts-table-live min-w-0 overflow-hidden rounded-2xl border border-border bg-card shadow-sm", className)}>
      <div role="row" className={cn("accounts-table-head sticky top-0 z-10 grid items-center gap-3 border-b border-border bg-secondary/50 px-4 py-3", gridCols)}>
        <Checkbox checked={allChecked} onCheckedChange={onToggleAll} aria-label="Seleccionar todas las cuentas" className="size-4" />
        <SortHead label="Cuenta" k="cuenta" sortKey={sortKey} dir={sortDir} onSort={onSort} />
        <SortHead label="Cliente / grupo" k="proveedor" sortKey={sortKey} dir={sortDir} onSort={onSort} className="hidden md:flex" />
        <SortHead label="Proveedor" k="proveedor" sortKey={sortKey} dir={sortDir} onSort={onSort} className="hidden xl:flex" />
        <SortHead label="Estado" k="estado" sortKey={sortKey} dir={sortDir} onSort={onSort} className="hidden md:flex" />
        <SortHead label="Última sinc." k="sync" sortKey={sortKey} dir={sortDir} onSort={onSort} className="hidden xl:flex" />
        <SortHead label="Mensajes" k="mensajes" sortKey={sortKey} dir={sortDir} onSort={onSort} align="right" />
        <SortHead label="Alertas" k="alertas" sortKey={sortKey} dir={sortDir} onSort={onSort} align="right" className="hidden md:flex" />
        <span className="hidden md:block" />
      </div>
      <div className="scroll-slim max-h-[calc(100vh-330px)] min-h-40 overflow-y-auto">
        {accounts.map((account, index) => {
          const accountStats = stats(account);
          const checked = selected.has(account.id);
          return (
            <div key={account.id} role="row" style={{ "--account-row-index": Math.min(index, 16) } as CSSProperties} onClick={() => actions.inbox(account)} className={cn("account-live-row grid cursor-pointer items-center gap-3 border-b border-border px-4 text-sm transition-colors last:border-b-0", rowPad, gridCols, checked ? "bg-primary/[0.07]" : "hover:bg-secondary/50")}>
              <span onClick={(event) => event.stopPropagation()}><Checkbox checked={checked} onCheckedChange={() => onToggle(account.id)} aria-label={`Seleccionar ${account.alias}`} className="size-4" /></span>
              <span className="flex min-w-0 items-center gap-3"><AccountProviderLogo provider={account.provider} className="size-7" /><span className="min-w-0"><span className="flex min-w-0 items-center gap-1.5"><span className="truncate font-semibold text-foreground">{account.alias}</span>{account.favorite && <Star className="size-3 shrink-0 fill-warning text-warning" />}</span><span className="block truncate text-xs text-muted-foreground">{account.email}</span></span></span>
              <span className="hidden min-w-0 md:block"><span className="block truncate text-[12px] text-foreground">{account.client}</span><span className="block truncate text-[11px] text-muted-foreground">{account.group} · {account.platform}</span></span>
              <span className="hidden min-w-0 items-center gap-2 truncate text-xs text-muted-foreground xl:flex"><ProviderBrandLogo provider={account.provider} /><span className="font-medium text-foreground">{providerLabels[account.provider]}</span> · {account.country}</span>
              <span className="hidden md:block"><span title={account.statusDetail ?? syncStatusLabels[account.status]} className={cn("account-status-pill inline-flex max-w-full items-center gap-1.5 truncate rounded-full border px-2 py-0.5 text-[11px] font-medium", statusTone[account.status])}><span className={cn("account-status-dot size-1.5 shrink-0 rounded-full", statusDot[account.status])} /><span className="truncate">{syncStatusLabels[account.status]}</span></span></span>
              <span className="hidden truncate text-[11.5px] text-muted-foreground xl:block">{account.lastSync}</span>
              <span className="text-right tabular-nums"><span className="font-semibold text-foreground">{accountStats.messages}</span>{accountStats.unread > 0 && <span className="ml-1 text-[11px] text-primary">+{accountStats.unread}</span>}</span>
              <span className="hidden text-right tabular-nums md:block">{accountStats.alerts > 0 ? <span className="inline-flex items-center gap-1 text-[12px] font-semibold text-destructive"><AlertTriangle className="size-3" />{accountStats.alerts}</span> : <span className="text-[12px] text-muted-foreground">0</span>}</span>
              <span className="hidden md:block" onClick={(event) => event.stopPropagation()}><RowMenu account={account} actions={actions} canManage={canManage} /></span>
            </div>
          );
        })}
        {accounts.length === 0 && <p className="px-4 py-14 text-center text-[12.5px] text-muted-foreground">Sin cuentas que coincidan con la búsqueda o los filtros activos.</p>}
      </div>
    </div>
  );
}

function SortHead({ label, k, sortKey, dir, onSort, align, className }: { label: string; k: AccountSortKey; sortKey: AccountSortKey; dir: "asc" | "desc"; onSort: (key: AccountSortKey) => void; align?: "right"; className?: string; }) {
  const active = sortKey === k;
  const Icon = !active ? ChevronsUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return <button type="button" onClick={() => onSort(k)} className={cn("flex min-w-0 items-center gap-1 text-[10.5px] font-semibold uppercase tracking-[0.12em] transition-colors", align === "right" && "justify-end", active ? "text-foreground" : "text-muted-foreground hover:text-foreground", className)}><span className="truncate">{label}</span><Icon className="size-3 shrink-0 opacity-70" /></button>;
}

function RowMenu({ account, actions, canManage }: { account: MailAccount; actions: AccountActions; canManage: boolean }) {
  return <DropdownMenu><DropdownMenuTrigger asChild><button type="button" aria-label={`Acciones de ${account.alias}`} className="grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-surface-3 hover:text-foreground"><MoreHorizontal className="size-4" /></button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-52"><DropdownMenuItem disabled={!canManage} onSelect={() => actions.sync(account)}>Sincronizar ahora</DropdownMenuItem><DropdownMenuItem onSelect={() => actions.inbox(account)}>Ver bandeja de la cuenta</DropdownMenuItem><DropdownMenuItem disabled={!canManage} onSelect={() => actions.reauthorize(account)}>Reautorizar acceso</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled>Editar alias y etiquetas</DropdownMenuItem><DropdownMenuItem disabled>Asignar cliente o grupo</DropdownMenuItem><DropdownMenuItem disabled>{account.status === "pausada" ? "Reanudar" : "Pausar"} sincronización</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled className="text-destructive focus:text-destructive">Desconectar cuenta</DropdownMenuItem></DropdownMenuContent></DropdownMenu>;
}
