import { useMemo, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, Bell, CheckCircle2, Clock, Filter, LogOut, PanelLeft,
  RefreshCw, Search, ShieldAlert, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { ProviderIcon } from "@/components/mail/provider-icon";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession, currentUser } from "@/lib/api";
import type { Account, Alert, Message, Page } from "@/lib/types";
import type { Provider } from "@/lib/mail-data";
import { cn } from "@/lib/utils";

type Severity = "critica" | "alta" | "media";

const severityLabel: Record<Severity, string> = {
  critica: "Crítica",
  alta: "Alta",
  media: "Media",
};

const severityTone: Record<Severity, string> = {
  critica: "border-destructive/35 bg-destructive/12 text-destructive",
  alta: "border-warning/35 bg-warning/12 text-warning",
  media: "border-border-strong bg-surface-3/60 text-muted-foreground",
};

function severityOf(alert: Alert): Severity {
  if (alert.risk_level === "critical") return "critica";
  if (alert.risk_level === "high") return "alta";
  return "media";
}

export function AlertManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const canManage = currentUser()?.role !== "viewer";
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<Set<Severity>>(new Set());
  const [syncing, setSyncing] = useState(false);
  const [actionError, setActionError] = useState("");

  const alertQuery = useInfiniteQuery({
    queryKey: ["alerts"],
    initialPageParam: "",
    queryFn: ({ pageParam }) => api<Page<Alert>>(`/v1/alerts?limit=50${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const accountQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api<Account[]>("/v1/mail/accounts"),
  });
  const messageQuery = useQuery({
    queryKey: ["messages", "alert-context"],
    queryFn: () => api<Page<Message>>("/v1/mail/messages?limit=100"),
  });
  const alerts = useMemo(() => alertQuery.data?.pages.flatMap((page) => page.items) ?? [], [alertQuery.data]);
  const messageById = useMemo(() => new Map((messageQuery.data?.items ?? []).map((message) => [message.id, message])), [messageQuery.data]);

  const resolve = useMutation({
    mutationFn: (id: string) => api(`/v1/alerts/${id}/resolve`, { method: "PATCH" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
      await queryClient.invalidateQueries({ queryKey: ["summary"] });
    },
    onError: (reason: Error) => setActionError(reason.message),
  });

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return alerts.filter((alert) => {
      const severity = severityOf(alert);
      if (severityFilter.size && !severityFilter.has(severity)) return false;
      if (!normalized) return true;
      return [alert.title, alert.detail, alert.alert_type, alert.risk_level]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized));
    });
  }, [alerts, search, severityFilter]);

  const counts = useMemo(() => ({
    critica: alerts.filter((alert) => severityOf(alert) === "critica").length,
    alta: alerts.filter((alert) => severityOf(alert) === "alta").length,
    media: alerts.filter((alert) => severityOf(alert) === "media").length,
    resueltas: alerts.filter((alert) => Boolean(alert.resolved_at)).length,
  }), [alerts]);

  function toggleSeverity(severity: Severity) {
    setSeverityFilter((previous) => {
      const next = new Set(previous);
      if (next.has(severity)) next.delete(severity); else next.add(severity);
      return next;
    });
  }

  async function analyze() {
    if (!canManage || syncing) return;
    setSyncing(true);
    setActionError("");
    try {
      const connected = (accountQuery.data ?? []).filter((account) => account.status === "connected");
      await Promise.all(connected.map((account) => api(`/v1/providers/${account.provider}/${account.id}/sync`, { method: "POST" })));
      await queryClient.invalidateQueries({ queryKey: ["accounts"] });
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "No se pudo iniciar el análisis.");
    } finally {
      setSyncing(false);
    }
  }

  async function resolveAll() {
    if (!canManage || resolve.isPending) return;
    setActionError("");
    for (const alert of filtered.filter((item) => !item.resolved_at)) {
      try { await resolve.mutateAsync(alert.id); }
      catch { break; }
    }
  }

  function logout() {
    clearSession();
    queryClient.clear();
    navigate("/login", { replace: true });
  }

  return (
    <main className="sleek-mail fixed inset-0 z-[70] flex h-[100dvh] min-w-0 overflow-hidden bg-background text-foreground">
      <AppSidebar className="hidden lg:flex" />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="grid shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-border bg-surface/70 px-3 py-2.5 backdrop-blur lg:px-5">
          <div className="flex items-center gap-2">
            <Sheet>
              <SheetTrigger asChild>
                <button type="button" aria-label="Abrir navegación" className="grid size-9 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground lg:hidden">
                  <PanelLeft className="size-4" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0">
                <SheetTitle className="sr-only">Navegación</SheetTitle>
                <AppSidebar className="w-full border-r-0" />
              </SheetContent>
            </Sheet>
            <span className="hidden min-w-0 lg:block">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workspace</span>
              <span className="block truncate text-[13px] font-semibold">Alertas</span>
            </span>
          </div>

          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar incidencia, cuenta, cliente o acción…" aria-label="Buscar alertas" className="h-9 w-full rounded-xl border border-border bg-surface-2 pl-9 pr-9 text-[12.5px] text-foreground placeholder:text-muted-foreground/75 focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring/25" />
            {search && <button type="button" onClick={() => setSearch("")} aria-label="Limpiar búsqueda" className="absolute right-2 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-surface-3 hover:text-foreground"><X className="size-3.5" /></button>}
          </div>

          <div className="flex items-center gap-1.5">
            <button type="button" onClick={analyze} disabled={!canManage || syncing} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-2 px-2.5 text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground disabled:opacity-50">
              <RefreshCw className={cn("size-3.5", syncing && "animate-spin text-primary")} />
              <span className="hidden sm:inline">{syncing ? "Analizando" : "Analizar"}</span>
            </button>
            <button type="button" aria-label="Alertas" className="hidden size-9 place-items-center rounded-xl border border-border text-muted-foreground hover:text-foreground sm:grid"><Bell className="size-4" /></button>
            <Button onClick={resolveAll} disabled={!canManage || resolve.isPending || !filtered.length} className="h-9 gap-1.5 rounded-xl px-3 text-[12.5px] font-semibold shadow-[0_10px_30px_-14px_var(--primary)]">
              <CheckCircle2 className="size-4" /><span className="hidden sm:inline">Resolver todo</span>
            </Button>
            <button type="button" onClick={logout} aria-label="Salir" className="hidden size-9 place-items-center rounded-xl border border-border text-muted-foreground hover:text-foreground xl:grid"><LogOut className="size-4" /></button>
          </div>
        </header>

        <div className="scroll-slim min-w-0 flex-1 overflow-y-auto px-3 py-3 lg:px-5 lg:py-4">
          <div className="mx-auto flex min-w-0 max-w-[1400px] flex-col gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">Detección automática</p>
              <h1 className="truncate text-[20px] font-semibold tracking-tight lg:text-[24px]">Alertas</h1>
              <p className="truncate text-[12px] text-muted-foreground">Incidencias priorizadas por riesgo y acción requerida.</p>
            </div>

            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Kpi label="Críticas" value={counts.critica} icon={ShieldAlert} tone="danger" />
              <Kpi label="Altas" value={counts.alta} icon={AlertTriangle} tone="warning" />
              <Kpi label="Medias" value={counts.media} icon={Clock} />
              <Kpi label="Resueltas" value={counts.resueltas} icon={ShieldCheck} tone="primary" />
            </div>

            <div className="scroll-slim flex min-w-0 items-center gap-1.5 overflow-x-auto pb-0.5">
              <span className="flex shrink-0 items-center gap-1.5 pr-1 text-[11.5px] text-muted-foreground"><Filter className="size-3.5" /> Severidad</span>
              {(["critica", "alta", "media"] as Severity[]).map((severity) => <button key={severity} type="button" aria-pressed={severityFilter.has(severity)} onClick={() => toggleSeverity(severity)} className={cn("h-7 shrink-0 rounded-full border px-2.5 text-[11.5px] font-medium transition-colors", severityFilter.has(severity) ? severityTone[severity] : "border-border bg-surface-2/60 text-muted-foreground hover:border-border-strong hover:text-foreground")}>{severityLabel[severity]}</button>)}
              {severityFilter.size > 0 && <button type="button" onClick={() => setSeverityFilter(new Set())} className="ml-1 flex h-7 shrink-0 items-center gap-1 rounded-full px-2 text-[11.5px] text-muted-foreground hover:text-foreground"><X className="size-3" /> Limpiar</button>}
            </div>

            {actionError && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">{actionError}</div>}
            {alertQuery.isLoading ? <LoadingAlerts /> : filtered.length === 0 ? <EmptyAlerts /> : (
              <ul className="flex flex-col gap-2 pb-6">
                {filtered.map((alert) => <AlertRow key={alert.id} alert={alert} message={messageById.get(alert.message_id)} canManage={canManage} resolving={resolve.isPending} onResolve={() => resolve.mutate(alert.id)} onExecute={() => navigate(`/correos?message=${encodeURIComponent(alert.message_id)}`)} />)}
              </ul>
            )}
            {alertQuery.isError && <button type="button" onClick={() => alertQuery.refetch()} className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-[12px] text-destructive">No se pudieron cargar las alertas. Reintentar</button>}
            {alertQuery.hasNextPage && <div className="flex justify-center pb-6"><button type="button" disabled={alertQuery.isFetchingNextPage} onClick={() => alertQuery.fetchNextPage()} className="h-8 rounded-lg border border-border bg-surface-2 px-3 text-[11.5px] text-foreground hover:border-border-strong disabled:opacity-50">{alertQuery.isFetchingNextPage ? "Cargando…" : "Cargar más"}</button></div>}
          </div>
        </div>
      </div>
    </main>
  );
}

function AlertRow({ alert, message, canManage, resolving, onResolve, onExecute }: { alert: Alert; message?: Message; canManage: boolean; resolving: boolean; onResolve: () => void; onExecute: () => void }) {
  const severity = severityOf(alert);
  const provider: Provider | undefined = message ? (message.provider === "gmail" ? "gmail" : providerForEmail(message.account_email)) : undefined;
  return (
    <li className="group grid grid-cols-[auto_minmax(0,1fr)] items-start gap-3 rounded-[18px] border border-border bg-surface/60 p-3 transition-colors hover:border-border-strong hover:bg-surface-2/60 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
      <span className={cn("grid size-9 shrink-0 place-items-center rounded-xl border", severityTone[severity])}>{severity === "critica" ? <ShieldAlert className="size-4" /> : severity === "alta" ? <AlertTriangle className="size-4" /> : <Clock className="size-4" />}</span>
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className={cn("rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", severityTone[severity])}>{severityLabel[severity]}</span>
          <span className="rounded-full border border-border bg-surface-3/50 px-1.5 py-0.5 text-[10px] text-muted-foreground">Mensaje</span>
          {provider && <span className="flex items-center gap-1 text-[10.5px] text-muted-foreground"><ProviderIcon provider={provider} className="size-3.5" />{provider === "gmail" ? "Gmail" : provider === "hotmail" ? "Hotmail" : provider === "live" ? "Live" : "Outlook"}</span>}
        </div>
        <p className="mt-1 truncate text-[13px] font-medium text-foreground">{alert.title}</p>
        <p className="truncate text-[11.5px] text-muted-foreground">{alert.detail || "Revisa el mensaje relacionado para obtener más información."}</p>
        <p className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1 text-primary"><Sparkles className="size-3" /> Revisar mensaje</span>
          {message?.account_email && <span className="truncate">· {message.account_email}</span>}
          <span className="flex items-center gap-1"><Clock className="size-3" /> {new Date(alert.created_at).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })}</span>
        </p>
      </div>
      <div className="col-span-2 flex items-center gap-1.5 sm:col-auto sm:shrink-0">
        <button type="button" onClick={onExecute} className="flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface-3/50 px-2.5 text-[11.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><RefreshCw className="size-3" /> Ejecutar</button>
        <button type="button" onClick={onResolve} disabled={!canManage || resolving} className="flex h-8 items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-2.5 text-[11.5px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"><CheckCircle2 className="size-3" /> Resolver</button>
      </div>
    </li>
  );
}

function providerForEmail(email: string): Provider {
  const domain = email.split("@")[1]?.toLowerCase() ?? "";
  if (domain.includes("hotmail")) return "hotmail";
  if (domain.includes("live")) return "live";
  return "outlook";
}

function EmptyAlerts() {
  return <div className="grid place-items-center rounded-[18px] border border-border bg-surface/50 px-6 py-16 text-center shadow-[0_20px_60px_-40px_rgb(0_0_0/0.9)]"><span className="grid size-12 place-items-center rounded-2xl bg-primary/12 text-primary ring-1 ring-primary/25"><ShieldCheck className="size-6" /></span><p className="mt-3 text-[15px] font-semibold">Todo en orden</p><p className="mt-1 max-w-sm text-[12px] text-muted-foreground">No hay alertas abiertas con los filtros actuales. Seguimos monitoreando la sincronización y el riesgo de cada cuenta.</p></div>;
}

function LoadingAlerts() {
  return <div className="flex flex-col gap-2">{[0, 1, 2].map((item) => <div key={item} className="h-[92px] animate-pulse rounded-[18px] border border-border bg-surface/60" />)}</div>;
}

function Kpi({ label, value, icon: Icon, tone }: { label: string; value: number; icon: typeof Bell; tone?: "danger" | "warning" | "primary" }) {
  return <div className="flex min-w-0 items-center gap-2.5 rounded-[18px] border border-border bg-surface/60 px-3 py-2.5"><span className={cn("grid size-8 shrink-0 place-items-center rounded-xl border border-border bg-surface-3/50 text-muted-foreground", tone === "danger" && "border-destructive/30 bg-destructive/10 text-destructive", tone === "warning" && "border-warning/30 bg-warning/10 text-warning", tone === "primary" && "border-primary/30 bg-primary/10 text-primary")}><Icon className="size-4" /></span><span className="min-w-0"><span className="block text-[18px] font-semibold leading-none tracking-tight">{value.toLocaleString("es")}</span><span className="block truncate text-[11px] text-muted-foreground">{label}</span></span></div>;
}
