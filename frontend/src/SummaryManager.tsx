import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Bell,
  Inbox,
  LogOut,
  Mail,
  PanelLeft,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession, currentUser } from "@/lib/api";
import type { Alert, Page, Summary } from "@/lib/types";

export function SummaryManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = currentUser();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api<Summary>("/v1/dashboard/summary") });
  const alerts = useQuery({ queryKey: ["alerts", "dashboard"], queryFn: () => api<Page<Alert>>("/v1/alerts?limit=6") });

  function logout() {
    clearSession();
    queryClient.clear();
    navigate("/login", { replace: true });
  }

  return (
    <main className="sleek-mail clear-summary fixed inset-0 z-[70] flex h-[100dvh] min-w-0 overflow-hidden bg-background text-foreground">
      <AppSidebar className="hidden lg:flex" />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="grid h-20 shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 border-b border-border bg-card px-4 lg:px-10">
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
            <span className="min-w-0">
              <span className="block text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Workspace</span>
              <span className="block truncate text-xl font-bold tracking-tight">Resumen</span>
            </span>
          </div>
          <div />
          <div className="flex items-center gap-4">
            <div className="hidden flex-col text-right sm:flex"><span className="text-sm font-semibold">{user?.display_name || "Admin Mail"}</span><span className="text-xs text-muted-foreground">{user?.email || "—"}</span></div>
            <button type="button" onClick={() => navigate("/alertas")} aria-label="Alertas" className="grid size-10 place-items-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:bg-secondary">
              <Bell className="size-5" />
            </button>
            <button type="button" onClick={logout} className="flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-semibold transition-colors hover:bg-secondary">
              <LogOut className="size-4" /><span className="hidden sm:inline">Salir</span>
            </button>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-y-auto p-6 lg:p-10">
          {summary.isLoading ? <SummarySkeleton /> : summary.isError || !summary.data ? <SummaryError retry={() => summary.refetch()} /> : <SummaryContent data={summary.data} alerts={alerts.data?.items ?? []} alertsLoading={alerts.isLoading} />}
        </div>
      </div>
    </main>
  );
}

function SummaryContent({ data, alerts, alertsLoading }: { data: Summary; alerts: Alert[]; alertsLoading: boolean }) {
  const kpis = [
    { id: "accounts", label: "Cuentas conectadas", value: String(data.connected_accounts), icon: Inbox },
    { id: "messages", label: "Mensajes", value: String(data.total_messages), icon: Mail },
    { id: "analysis", label: "Analizados", value: `${data.analysis_coverage_percent}%`, icon: Sparkles },
    { id: "alerts", label: "Alertas abiertas", value: String(data.open_alerts), icon: AlertTriangle },
  ];
  const series = data.trend.map((point) => ({ iso: point.day, day: new Date(`${point.day}T00:00:00`).toLocaleDateString("es", { weekday: "short" }).replace(".", ""), value: point.messages }));
  const periodTotal = series.reduce((total, point) => total + point.value, 0);
  const periodPeak = series.reduce((peak, point) => Math.max(peak, point.value), 0);

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <section className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4" aria-label="Métricas principales">
        {kpis.map((kpi, index) => (
          <article key={kpi.id} style={{ animationDelay: `${index * 70}ms` }} className={`summary-kpi summary-kpi--${kpi.id} group relative animate-in overflow-hidden rounded-3xl border border-border bg-secondary/60 p-6 fill-mode-backwards duration-500 fade-in slide-in-from-bottom-3 transition-all hover:-translate-y-1 hover:shadow-sm`}>
            <i className="summary-kpi__beam" aria-hidden />
            <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 size-28 rounded-full bg-primary/10 blur-2xl transition-all duration-500 group-hover:scale-125 group-hover:bg-primary/20" />
            <div className="flex items-start justify-between gap-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{kpi.label}</p>
              <span className="grid size-9 shrink-0 place-items-center rounded-2xl bg-card text-primary transition-transform duration-300 group-hover:scale-110"><kpi.icon className="size-4" /></span>
            </div>
            <p className="mt-3 text-3xl font-bold leading-none tracking-tight tabular-nums">{kpi.value}</p>
          </article>
        ))}
      </section>

      <div className="mt-8 grid items-start gap-8 xl:grid-cols-3">
        <section style={{ animationDelay: "280ms" }} className="summary-chart-card animate-in rounded-3xl border border-border bg-secondary/60 p-6 fill-mode-backwards duration-700 fade-in slide-in-from-bottom-4 lg:p-8 xl:col-span-2">
          <i className="summary-chart-card__orb" aria-hidden />
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-primary">Últimos 14 días</p><h2 className="mt-1 flex items-center gap-2 text-lg font-semibold tracking-tight"><Activity className="size-4 text-primary" />Flujo de actividad</h2></div>
            <span className="shrink-0 rounded-full border border-border bg-surface-2/80 px-2.5 py-1 text-[11px] text-muted-foreground">{data.messages_last_24h} hoy</span>
          </div>
          <div className="summary-chart-stats" aria-label="Resumen del periodo">
            <span><small>Actividad total</small><b>{periodTotal.toLocaleString("es")}</b></span>
            <span><small>Pico diario</small><b>{periodPeak.toLocaleString("es")}</b></span>
            <span><small>Últimas 24 h</small><b>{data.messages_last_24h.toLocaleString("es")}</b></span>
          </div>
          <div className="summary-chart mt-6 h-64 w-full">
            <i className="summary-chart__scanner" aria-hidden />
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                <defs>
                  <linearGradient id="summaryFlowFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#00c98a" stopOpacity={0.42} /><stop offset="55%" stopColor="#42dfb0" stopOpacity={0.14} /><stop offset="100%" stopColor="#8ff0d2" stopOpacity={0} /></linearGradient>
                  <linearGradient id="summaryFlowStroke" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#0ea5e9" /><stop offset="48%" stopColor="#00c98a" /><stop offset="100%" stopColor="#8b5cf6" /></linearGradient>
                  <filter id="summaryFlowGlow" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                </defs>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                <YAxis tickLine={false} axisLine={false} width={34} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} allowDecimals={false} />
                <Tooltip cursor={{ stroke: "var(--border-strong)" }} contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, color: "var(--foreground)" }} labelFormatter={(_, payload) => payload?.[0]?.payload?.iso ?? ""} formatter={(value: number) => [value, "Mensajes"]} />
                <Area type="monotone" dataKey="value" stroke="url(#summaryFlowStroke)" strokeWidth={3} fill="url(#summaryFlowFill)" dot={{ r: 3, fill: "#fff", stroke: "#00bd82", strokeWidth: 2 }} activeDot={{ r: 6, fill: "#fff", stroke: "#8b5cf6", strokeWidth: 3 }} isAnimationActive animationBegin={180} animationDuration={1800} animationEasing="ease-out" style={{ filter: "url(#summaryFlowGlow)" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section style={{ animationDelay: "380ms" }} className="summary-alert-card animate-in rounded-3xl border border-border bg-secondary/60 p-6 fill-mode-backwards duration-700 fade-in slide-in-from-bottom-4 lg:p-8">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-primary">Atención requerida</p><h2 className="mt-1 text-lg font-semibold tracking-tight">Alertas recientes</h2></div>
            <NavLink to="/alertas" className="shrink-0 rounded-full border border-border bg-surface-2/80 px-2.5 py-1 text-[11px] text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-border-strong hover:text-foreground">Ver todas</NavLink>
          </div>
          <div className="mt-4 space-y-2">
            {alertsLoading ? <AlertSkeleton /> : alerts.length === 0 ? (
              <div className="animate-in rounded-xl border border-border bg-surface-2/40 px-4 py-8 text-center duration-700 fade-in zoom-in-95"><span className="mx-auto grid size-10 place-items-center rounded-xl bg-primary/12 text-primary ring-1 ring-primary/25"><ShieldCheck className="size-5" /></span><p className="mt-3 text-[13px] font-medium">Todo en orden</p><p className="mt-1 text-[11.5px] text-muted-foreground">No hay alertas abiertas en este momento.</p></div>
            ) : alerts.map((alert, index) => (
              <article key={alert.id} style={{ animationDelay: `${450 + index * 60}ms` }} className="summary-alert-item animate-in rounded-2xl border border-border bg-card p-4 fill-mode-backwards duration-500 fade-in slide-in-from-right-3 transition-colors hover:border-primary/40">
                <div className="flex items-center gap-2"><AlertTriangle className="size-3.5 shrink-0 text-warning" /><p className="min-w-0 flex-1 truncate text-[12.5px] font-medium">{alert.title}</p><span className="shrink-0 rounded-full bg-warning/12 px-2 py-0.5 text-[10px] font-semibold text-warning">{riskLabel(alert.risk_level)}</span></div>
                <p className="mt-1 truncate text-[11.5px] text-muted-foreground">{alert.detail || "Revisa el mensaje relacionado para obtener más información."}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function riskLabel(risk: Alert["risk_level"]) {
  return { low: "Bajo", medium: "Medio", high: "Alto", critical: "Crítico" }[risk];
}

function SummarySkeleton() {
  return <div className="mx-auto w-full max-w-6xl animate-pulse"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-28 rounded-2xl border border-border bg-surface/60" />)}</div><div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,340px)]"><div className="h-[370px] rounded-2xl border border-border bg-surface/60" /><div className="h-[370px] rounded-2xl border border-border bg-surface/60" /></div></div>;
}

function AlertSkeleton() {
  return <>{[0, 1, 2].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl border border-border bg-surface-2/40" />)}</>;
}

function SummaryError({ retry }: { retry: () => void }) {
  return <div className="mx-auto flex min-h-72 w-full max-w-6xl flex-col items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10 px-6 text-center"><Activity className="size-8 text-destructive" /><h1 className="mt-4 text-xl font-semibold">No pudimos cargar el resumen</h1><p className="mt-2 text-[13px] text-muted-foreground">Comprueba la conexión e inténtalo nuevamente.</p><button type="button" onClick={retry} className="mt-5 h-9 rounded-xl border border-border bg-surface-2 px-4 text-[12.5px] font-semibold hover:border-border-strong">Reintentar</button></div>;
}
