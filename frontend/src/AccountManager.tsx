import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, Bell, CheckCircle2, Clock, Inbox, LayoutList, LogOut, Mail,
  MailOpen, PanelLeft, Pause, Plus, RefreshCw, Rows3, Search, ShieldAlert,
  Users, X,
} from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { AccountsTable, type AccountSortKey } from "@/components/mail/accounts-table";
import { MetricsGrid, type Metric } from "@/components/mail/metrics-grid";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession, currentUser } from "@/lib/api";
import type { Account } from "@/lib/types";
import {
  attentionStatuses, providerLabels, syncStatusLabels, type MailAccount,
  type Provider, type SyncStatus,
} from "@/lib/mail-data";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 40;
type StatusFilter = SyncStatus | "atencion";
const statusChips: { id: StatusFilter; label: string }[] = [
  { id: "conectada", label: "Conectadas" },
  { id: "sincronizando", label: "Sincronizando" },
  { id: "atencion", label: "Críticas" },
  { id: "error", label: "Error" },
  { id: "requiere-autorizacion", label: "Pendientes" },
  { id: "pausada", label: "Pausadas" },
];

export function AccountManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const canManage = currentUser()?.role !== "viewer";
  const accountQuery = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/v1/mail/accounts") });
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [providerFilter, setProviderFilter] = useState<Set<Provider>>(new Set());
  const [statusFilter, setStatusFilter] = useState<Set<StatusFilter>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<AccountSortKey>("cuenta");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [density, setDensity] = useState<"comoda" | "compacta">("comoda");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(rawQuery), 200);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  const rawAccounts = useMemo(() => accountQuery.data ?? [], [accountQuery.data]);
  const accounts = useMemo(() => rawAccounts.map(mapAccount), [rawAccounts]);
  const rawById = useMemo(() => new Map(rawAccounts.map((account) => [account.id, account])), [rawAccounts]);
  const stats = useCallback((account: MailAccount) => {
    const source = rawById.get(account.id);
    return { messages: source?.message_count ?? 0, unread: 0, alerts: source?.alert_count ?? 0 };
  }, [rawById]);
  const providersPresent = useMemo(() => [...new Set(accounts.map((account) => account.provider))], [accounts]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const list = accounts.filter((account) => {
      if (providerFilter.size && !providerFilter.has(account.provider)) return false;
      if (statusFilter.size && ![...statusFilter].some((status) => status === "atencion" ? attentionStatuses.includes(account.status) : account.status === status)) return false;
      if (!normalizedQuery) return true;
      const domain = account.email.split("@")[1] ?? "";
      return [account.alias, account.email, domain, account.client, account.group, account.platform, account.country, providerLabels[account.provider], syncStatusLabels[account.status], account.lastSync, ...account.labels].some((value) => value.toLowerCase().includes(normalizedQuery));
    });
    const direction = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === "proveedor") return direction * (a.client + a.provider).localeCompare(b.client + b.provider);
      if (sortKey === "estado") return direction * syncStatusLabels[a.status].localeCompare(syncStatusLabels[b.status]);
      if (sortKey === "sync") return direction * a.lastSync.localeCompare(b.lastSync);
      if (sortKey === "mensajes") return direction * (stats(a).messages - stats(b).messages);
      if (sortKey === "alertas") return direction * (stats(a).alerts - stats(b).alerts);
      return direction * a.alias.localeCompare(b.alias);
    });
  }, [accounts, providerFilter, query, sortDir, sortKey, statusFilter, stats]);

  const visible = filtered.slice(0, pageSize);
  const totals = useMemo(() => ({
    total: accounts.length,
    connected: accounts.filter((account) => account.status === "conectada").length,
    errors: accounts.filter((account) => account.status === "error" || account.status === "credenciales-vencidas").length,
    pending: accounts.filter((account) => account.status === "requiere-autorizacion" || account.status === "pausada").length,
    synced: rawAccounts.reduce((sum, account) => sum + account.message_count, 0),
    unread: 0,
  }), [accounts, rawAccounts]);
  const metrics: Metric[] = [
    { id: "total", label: "Cuentas", value: totals.total, icon: Users },
    { id: "ok", label: "Conectadas", value: totals.connected, icon: CheckCircle2, tone: "primary" },
    { id: "err", label: "Con errores", value: totals.errors, icon: ShieldAlert, tone: "danger" },
    { id: "pend", label: "Pendientes", value: totals.pending, icon: Pause, tone: "warning" },
    { id: "msg", label: "Sincronizados", value: totals.synced, icon: Inbox },
    { id: "unread", label: "Sin leer", value: totals.unread, icon: MailOpen, tone: "primary" },
  ];

  const toggle = (id: string) => setSelected((previous) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const toggleAll = () => setSelected((previous) => visible.every((account) => previous.has(account.id)) ? new Set() : new Set(visible.map((account) => account.id)));
  const toggleProvider = (provider: Provider) => setProviderFilter((previous) => { const next = new Set(previous); if (next.has(provider)) next.delete(provider); else next.add(provider); return next; });
  const toggleStatus = (status: StatusFilter) => setStatusFilter((previous) => { const next = new Set(previous); if (next.has(status)) next.delete(status); else next.add(status); return next; });
  const activeFilters = providerFilter.size + statusFilter.size;

  async function connect(provider: "gmail" | "microsoft") {
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(`/v1/providers/${provider}/authorize`, { method: "POST" });
      window.location.assign(result.authorization_url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo iniciar la conexión."); }
  }
  async function syncAccount(account: MailAccount) {
    const raw = rawById.get(account.id); if (!raw) return;
    setError("");
    try {
      await api(`/v1/providers/${raw.provider}/${raw.id}/sync`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo sincronizar la cuenta."); }
  }
  async function reauthorize(account: MailAccount) {
    const raw = rawById.get(account.id); if (!raw) return;
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(`/v1/providers/${raw.provider}/authorize`, { method: "POST" });
      window.location.assign(result.authorization_url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo reautorizar la cuenta."); }
  }
  async function runSync(targets = accounts.filter((account) => account.status === "conectada")) {
    if (!canManage || syncing) return;
    setSyncing(true); setError("");
    try { await Promise.all(targets.map(syncAccount)); }
    finally { setSyncing(false); }
  }
  function logout() { clearSession(); queryClient.clear(); navigate("/login", { replace: true }); }
  const selectedAccounts = accounts.filter((account) => selected.has(account.id));

  return (
    <main className="sleek-mail clear-accounts fixed inset-0 z-[70] flex h-[100dvh] min-w-0 overflow-hidden bg-background text-foreground">
      <AppSidebar className="hidden lg:flex" />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="accounts-command-bar grid shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 border-b border-border bg-card px-4 py-4 lg:px-6">
          <div className="flex items-center gap-2"><Sheet><SheetTrigger asChild><button type="button" aria-label="Abrir navegación" className="grid size-9 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground lg:hidden"><PanelLeft className="size-4" /></button></SheetTrigger><SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0"><SheetTitle className="sr-only">Navegación</SheetTitle><AppSidebar className="w-full border-r-0" /></SheetContent></Sheet><span className="hidden min-w-0 lg:block"><span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workspace</span><span className="block truncate text-[13px] font-semibold">Cuentas</span></span></div>
          <div className="relative min-w-0"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><input value={rawQuery} onChange={(event) => { setRawQuery(event.target.value); setPageSize(PAGE_SIZE); }} placeholder="Buscar por correo, cliente, proveedor, dominio, estado o etiqueta…" aria-label="Buscar cuentas" className="h-9 w-full rounded-xl border border-border bg-surface-2 pl-9 pr-9 text-[12.5px] text-foreground placeholder:text-muted-foreground/75 focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring/25" />{rawQuery && <button type="button" onClick={() => setRawQuery("")} aria-label="Limpiar búsqueda" className="absolute right-2 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-surface-3 hover:text-foreground"><X className="size-3.5" /></button>}</div>
          <div className="flex items-center gap-1.5"><button type="button" onClick={() => runSync()} disabled={!canManage || syncing} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-2 px-2.5 text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground disabled:opacity-50"><RefreshCw className={cn("size-3.5", syncing && "animate-spin text-primary")} /><span className="hidden sm:inline">{syncing ? "Sincronizando" : "Sincronizar"}</span></button><button type="button" aria-label="Alertas" className="hidden size-9 place-items-center rounded-xl border border-border text-muted-foreground hover:text-foreground sm:grid"><Bell className="size-4" /></button>{canManage && <DropdownMenu><DropdownMenuTrigger asChild><Button className="h-9 gap-1.5 rounded-xl px-3 text-[12.5px] font-semibold shadow-[0_10px_30px_-14px_var(--primary)]"><Plus className="size-4" /><span className="hidden sm:inline">Agregar cuenta</span></Button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-48"><DropdownMenuItem onSelect={() => connect("gmail")}>Conectar Gmail</DropdownMenuItem><DropdownMenuItem onSelect={() => connect("microsoft")}>Conectar Microsoft</DropdownMenuItem></DropdownMenuContent></DropdownMenu>}<button type="button" onClick={logout} aria-label="Salir" className="hidden size-9 place-items-center rounded-xl border border-border text-muted-foreground hover:text-foreground xl:grid"><LogOut className="size-4" /></button></div>
        </header>
        <div className="scroll-slim min-w-0 flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="mx-auto flex min-w-0 max-w-[1600px] flex-col gap-5">
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-end gap-3"><div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">Proveedores</p><h1 className="truncate text-[20px] font-semibold tracking-tight lg:text-[24px]">Cuentas conectadas</h1><p className="truncate text-[12px] text-muted-foreground">{filtered.length.toLocaleString("es")} de {totals.total.toLocaleString("es")} buzones · sincronización, estado y volumen en tiempo real.</p></div><div className="flex shrink-0 items-center gap-1 rounded-xl border border-border bg-surface-2 p-1"><DensityButton active={density === "comoda"} onClick={() => setDensity("comoda")} icon={Rows3} label="Cómoda" /><DensityButton active={density === "compacta"} onClick={() => setDensity("compacta")} icon={LayoutList} label="Compacta" /></div></div>
            <MetricsGrid metrics={metrics} />
            {error && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">{error}</div>}
            <div className="scroll-slim flex min-w-0 items-center gap-1.5 overflow-x-auto pb-0.5">{providersPresent.map((provider) => <Chip key={provider} active={providerFilter.has(provider)} onClick={() => { toggleProvider(provider); setPageSize(PAGE_SIZE); }} label={providerLabels[provider]} />)}<span className="mx-1 h-5 w-px shrink-0 bg-border" />{statusChips.map((status) => <Chip key={status.id} active={statusFilter.has(status.id)} onClick={() => { toggleStatus(status.id); setPageSize(PAGE_SIZE); }} label={status.label} tone={status.id === "error" || status.id === "atencion" ? "danger" : undefined} />)}{activeFilters > 0 && <button type="button" onClick={() => { setProviderFilter(new Set()); setStatusFilter(new Set()); }} className="ml-1 flex h-7 shrink-0 items-center gap-1 rounded-full px-2 text-[11.5px] text-muted-foreground hover:text-foreground"><X className="size-3" />Limpiar ({activeFilters})</button>}</div>
            {selected.size > 0 && <div className="scroll-slim flex items-center gap-1.5 overflow-x-auto rounded-xl border border-primary/25 bg-primary/[0.07] px-2.5 py-1.5"><span className="shrink-0 rounded bg-primary/15 px-1.5 py-0.5 text-[11px] font-semibold text-primary">{selected.size}</span><BulkBtn icon={RefreshCw} label="Sincronizar" onClick={() => runSync(selectedAccounts)} disabled={!canManage} /><BulkBtn icon={ShieldAlert} label="Reautorizar" onClick={() => selectedAccounts[0] && reauthorize(selectedAccounts[0])} disabled={!canManage || selectedAccounts.length !== 1} /><BulkBtn icon={Pause} label="Pausar" disabled /><BulkBtn icon={Users} label="Asignar cliente" disabled /><BulkBtn icon={Mail} label="Ver bandeja" onClick={() => navigate("/correos")} /><BulkBtn icon={AlertTriangle} label="Desconectar" tone="danger" disabled /><button type="button" onClick={() => setSelected(new Set())} aria-label="Cancelar selección" className="ml-auto grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-surface-3 hover:text-foreground"><X className="size-3.5" /></button></div>}
            <AccountsTable accounts={visible} stats={stats} selected={selected} onToggle={toggle} onToggleAll={toggleAll} sortKey={sortKey} sortDir={sortDir} onSort={(key) => { if (key === sortKey) setSortDir((direction) => direction === "asc" ? "desc" : "asc"); else { setSortKey(key); setSortDir("asc"); } }} density={density} canManage={canManage} actions={{ sync: syncAccount, inbox: () => navigate("/correos"), reauthorize }} />
            {accountQuery.isLoading && <p className="py-8 text-center text-[12.5px] text-muted-foreground">Cargando cuentas…</p>}
            {accountQuery.isError && <button type="button" onClick={() => accountQuery.refetch()} className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-[12px] text-destructive">No se pudieron cargar las cuentas. Reintentar</button>}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-4 text-[11.5px] text-muted-foreground"><span className="flex items-center gap-1.5"><Clock className="size-3.5" />Mostrando {visible.length.toLocaleString("es")} de {filtered.length.toLocaleString("es")} cuentas</span>{visible.length < filtered.length && <button type="button" onClick={() => setPageSize((size) => size + PAGE_SIZE)} className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-[12px] text-foreground transition-colors hover:border-border-strong">Cargar más</button>}</div>
          </div>
        </div>
      </div>
    </main>
  );
}

function Chip({ label, active, onClick, tone }: { label: string; active: boolean; onClick: () => void; tone?: "danger"; }) {
  return <button type="button" onClick={onClick} aria-pressed={active} className={cn("h-7 shrink-0 rounded-full border px-2.5 text-[11.5px] font-medium transition-colors", active ? tone === "danger" ? "border-destructive/40 bg-destructive/12 text-destructive" : "border-primary/40 bg-primary/12 text-primary" : "border-border bg-surface-2/60 text-muted-foreground hover:border-border-strong hover:text-foreground")}>{label}</button>;
}
function DensityButton({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Rows3; label: string; }) {
  return <button type="button" onClick={onClick} title={label} aria-pressed={active} className={cn("flex h-7 items-center gap-1.5 rounded-lg px-2 text-[11.5px] transition-colors", active ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground")}><Icon className="size-3.5" /><span className="hidden sm:inline">{label}</span></button>;
}
function BulkBtn({ icon: Icon, label, tone, disabled, onClick }: { icon: typeof RefreshCw; label: string; tone?: "danger"; disabled?: boolean; onClick?: () => void; }) {
  return <button type="button" onClick={onClick} disabled={disabled} className={cn("flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-[11.5px] text-muted-foreground transition-colors hover:bg-surface-3 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40", tone === "danger" && "hover:bg-destructive/12 hover:text-destructive")}><Icon className="size-3.5" />{label}</button>;
}
function providerFor(account: Account): Provider {
  if (account.provider === "gmail") return "gmail";
  const domain = account.email.split("@")[1]?.toLowerCase() ?? "";
  if (domain.includes("hotmail")) return "hotmail";
  if (domain.includes("live")) return "live";
  return "outlook";
}
function statusFor(status: Account["status"]): SyncStatus {
  return ({ connected: "conectada", syncing: "sincronizando", error: "error", reauth_required: "requiere-autorizacion", disconnected: "pausada" } as const)[status];
}
function mapAccount(account: Account): MailAccount {
  const provider = providerFor(account);
  return { id: account.id, alias: account.email.split("@")[0] || account.email, email: account.email, provider, client: "Sin asignar", platform: provider === "gmail" ? "Google Gmail" : "Microsoft Mail", group: "Workspace", country: "—", labels: [], favorite: false, status: statusFor(account.status), lastSync: account.last_synced_at ? new Date(account.last_synced_at).toLocaleString("es-PE") : "Pendiente", messageCount: account.message_count, statusDetail: account.last_error ?? (account.status === "error" ? "La última sincronización falló." : undefined) };
}
