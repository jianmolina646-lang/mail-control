import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowLeft, Bot, CheckCircle2, ChevronDown, Clock3,
  Cpu, CreditCard, Gauge, Inbox, Layers3, LogOut, PanelLeft, Search, ShieldCheck,
  Sparkles, WandSparkles, X, Zap,
} from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession } from "@/lib/api";
import type { Analysis, Page, Risk } from "@/lib/types";
import { cn } from "@/lib/utils";

const risks: { value: Risk | ""; label: string }[] = [
  { value: "", label: "Todos" },
  { value: "critical", label: "Críticos" },
  { value: "high", label: "Altos" },
  { value: "medium", label: "Medios" },
  { value: "low", label: "Bajos" },
];

const paymentAlertTypes = new Set(["payment_rejected", "payment_method_expired", "renewal_due"]);

export function AnalysisManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const messageId = params.get("message_id");
  const [rawSearch, setRawSearch] = useState("");
  const [search, setSearch] = useState("");
  const [risk, setRisk] = useState<Risk | "">("");

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(rawSearch.trim()), 220);
    return () => window.clearTimeout(timer);
  }, [rawSearch]);

  const paymentQuery = useQuery({
    queryKey: ["analyses", "payment-attention"],
    queryFn: () => api<Page<Analysis>>("/v1/analysis/incidents/active?limit=100"),
  });
  const paymentAnalyses = useMemo(() => (paymentQuery.data?.items ?? []).filter(
    (analysis) => analysis.alert_types.some((type) => paymentAlertTypes.has(type)),
  ), [paymentQuery.data]);
  const analyses = useMemo(() => paymentAnalyses.filter((analysis) => {
    if (messageId && analysis.message_id !== messageId) return false;
    if (risk && analysis.risk_level !== risk) return false;
    if (search.length < 2) return true;
    const searchable = [analysis.sender, analysis.subject, analysis.service, analysis.platform, analysis.category, analysis.account_email].filter(Boolean).join(" ").toLowerCase();
    return searchable.includes(search.toLowerCase());
  }), [messageId, paymentAnalyses, risk, search]);
  const paymentAttention = useMemo(() => {
    const grouped = new Map<string, Analysis>();
    for (const analysis of paymentAnalyses) {
      const platform = analysis.platform || analysis.service || analysis.category;
      const key = `${analysis.account_email.toLowerCase()}::${platform.toLowerCase()}`;
      if (!grouped.has(key)) grouped.set(key, analysis);
    }
    return [...grouped.values()];
  }, [paymentAnalyses]);
  const critical = analyses.filter((item) => item.risk_level === "critical").length;
  const actionable = analyses.filter((item) => item.action_required).length;
  const categories = new Set(analyses.map((item) => item.category)).size;

  function logout() {
    clearSession();
    queryClient.clear();
    navigate("/login", { replace: true });
  }
  function clearMessageFilter() {
    const next = new URLSearchParams(params);
    next.delete("message_id");
    setParams(next, { replace: true });
  }

  return <main className="sleek-mail fixed inset-0 z-[70] flex h-[100dvh] w-full overflow-hidden bg-background">
    <AppSidebar className="hidden lg:flex" />
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="grid h-20 shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 border-b border-border bg-card/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-2">
          <Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 lg:hidden" aria-label="Menú"><PanelLeft className="size-4" /></Button></SheetTrigger><SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0"><SheetTitle className="sr-only">Navegación</SheetTitle><AppSidebar className="flex w-full border-r-0" /></SheetContent></Sheet>
          <span className="hidden size-10 place-items-center rounded-2xl bg-primary/12 text-primary ring-1 ring-primary/20 sm:grid"><WandSparkles className="size-5" /></span>
          <div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">Inteligencia operativa</p><h1 className="truncate text-xl font-extrabold tracking-tight text-foreground">Análisis IA</h1></div>
        </div>
        <div />
        <div className="flex items-center gap-2"><span className="hidden items-center gap-2 rounded-full border border-primary/20 bg-primary/[0.06] px-3 py-1.5 text-[11px] font-semibold text-primary md:flex"><span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-40" /><span className="relative inline-flex size-2 rounded-full bg-primary" /></span>OpenAI operativo</span><Button variant="ghost" size="sm" onClick={() => navigate("/correos")} className="hidden gap-1.5 sm:flex"><ArrowLeft className="size-4" />Correos</Button><Button variant="ghost" size="icon" onClick={logout} aria-label="Cerrar sesión"><LogOut className="size-4" /></Button></div>
      </header>

      <div className="scroll-slim min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_75%_0%,color-mix(in_oklab,var(--primary)_9%,transparent),transparent_34%)]">
        <div className="mx-auto w-full max-w-[1500px] space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <section className="relative overflow-hidden rounded-3xl border border-border bg-card px-5 py-6 shadow-sm sm:px-7 lg:px-8">
            <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-primary/10 blur-3xl" />
            <div className="relative flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
              <div className="max-w-2xl"><div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-primary"><Cpu className="size-3.5" />Centro de decisiones</div><h2 className="mt-2 text-2xl font-extrabold tracking-[-0.035em] text-foreground sm:text-3xl">Cada correo convertido en una acción clara.</h2><p className="mt-2 max-w-xl text-[13px] leading-6 text-muted-foreground">Revisa clasificaciones, riesgos y recomendaciones producidas por el modelo sin mezclar el análisis con tu bandeja.</p></div>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface-2/80 px-4 py-3"><span className="grid size-9 place-items-center rounded-xl bg-primary/12 text-primary"><Activity className="size-4" /></span><div><p className="text-[10px] uppercase tracking-wide text-muted-foreground">Procesamiento</p><p className="text-[12.5px] font-semibold text-foreground">Resultados actualizados</p></div></div>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Stat icon={Sparkles} label="Análisis visibles" value={analyses.length} detail="Resultados cargados" />
            <Stat icon={AlertTriangle} label="Riesgo crítico" value={critical} detail="Requieren prioridad" tone="danger" />
            <Stat icon={Zap} label="Con acción" value={actionable} detail="Recomendación disponible" tone="primary" />
            <Stat icon={Layers3} label="Categorías" value={categories} detail="Tipos detectados" tone="violet" />
          </section>

          <PaymentAttention analyses={paymentAttention} loading={paymentQuery.isLoading} />

          <section className="rounded-3xl border border-border bg-card p-3 shadow-sm sm:p-4">
            {messageId && <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-primary/20 bg-primary/[0.06] px-3 py-2.5 text-[12px] font-medium text-primary"><span className="flex items-center gap-2"><span className="grid size-7 place-items-center rounded-lg bg-primary/10"><Inbox className="size-3.5" /></span>Mostrando el análisis del correo seleccionado</span><button type="button" onClick={clearMessageFilter} className="grid size-7 place-items-center rounded-lg transition-colors hover:bg-primary/10" aria-label="Mostrar todos los análisis"><X className="size-3.5" /></button></div>}
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><input value={rawSearch} onChange={(event) => setRawSearch(event.target.value)} placeholder="Buscar por remitente, asunto, servicio o categoría" className="h-11 w-full rounded-xl border border-border bg-surface-2/70 pl-10 pr-3 text-[13px] outline-none transition-all duration-200 hover:border-border-strong focus:-translate-y-px focus:border-primary/40 focus:bg-card focus:ring-4 focus:ring-primary/10" /></div>
              <div className="scroll-slim flex gap-1.5 overflow-x-auto rounded-xl bg-surface-2/70 p-1">{risks.map((option) => <button key={option.label} type="button" onClick={() => setRisk(option.value)} className={cn("h-9 shrink-0 rounded-lg px-3 text-[12px] transition-all duration-200", risk === option.value ? "bg-card font-semibold text-foreground shadow-sm ring-1 ring-border" : "text-muted-foreground hover:bg-card/60 hover:text-foreground")}>{option.label}</button>)}</div>
            </div>
          </section>

          {paymentQuery.isLoading ? <AnalysisSkeleton /> : paymentQuery.isError ? <div className="rounded-3xl border border-destructive/30 bg-destructive/5 p-10 text-center"><AlertTriangle className="mx-auto size-8 text-destructive" /><p className="mt-3 text-sm font-semibold text-destructive">No se pudieron cargar los análisis</p><p className="mt-1 text-[12px] text-muted-foreground">Comprueba la conexión y vuelve a intentarlo.</p><Button variant="outline" size="sm" onClick={() => paymentQuery.refetch()} className="mt-4">Reintentar</Button></div> : analyses.length ? <div className="grid gap-4 xl:grid-cols-2">{analyses.map((analysis, index) => <AnalysisCard key={analysis.id} analysis={analysis} index={index} />)}</div> : <div className="rounded-3xl border border-dashed border-border bg-card/60 p-14 text-center"><span className="mx-auto grid size-14 place-items-center rounded-2xl bg-surface-2 text-muted-foreground"><Bot className="size-6" /></span><p className="mt-4 text-sm font-semibold">No hay problemas de pago para estos filtros</p><p className="mt-1 text-[12px] text-muted-foreground">Los inicios de sesión y eventos de seguridad no se muestran en esta sección.</p></div>}
        </div>
      </div>
    </div>
  </main>;
}

function Stat({ icon: Icon, label, value, detail, tone = "neutral" }: { icon: typeof Sparkles; label: string; value: number; detail: string; tone?: "neutral" | "primary" | "danger" | "violet" }) {
  return <article className="group relative overflow-hidden rounded-3xl border border-border bg-card p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md"><div aria-hidden className={cn("pointer-events-none absolute -right-8 -top-8 size-24 rounded-full blur-2xl transition-transform duration-300 group-hover:scale-125", tone === "danger" ? "bg-destructive/10" : tone === "violet" ? "bg-chart-5/10" : "bg-primary/10")} /><div className="relative flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-extrabold leading-none tracking-tight tabular-nums text-foreground">{value.toLocaleString("es-PE")}</p><p className="mt-2 text-[11px] text-muted-foreground">{detail}</p></div><span className={cn("grid size-10 shrink-0 place-items-center rounded-2xl ring-1", tone === "danger" ? "bg-destructive/10 text-destructive ring-destructive/15" : tone === "violet" ? "bg-chart-5/10 text-chart-5 ring-chart-5/15" : "bg-primary/10 text-primary ring-primary/15")}><Icon className="size-4.5" /></span></div></article>;
}

function PaymentAttention({ analyses, loading }: { analyses: Analysis[]; loading: boolean }) {
  return <section className="overflow-hidden rounded-3xl border border-warning/20 bg-card shadow-sm">
    <div className="flex flex-col justify-between gap-3 border-b border-border bg-gradient-to-r from-warning/[0.08] to-transparent px-5 py-4 sm:flex-row sm:items-center sm:px-6">
      <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-2xl bg-warning/12 text-warning ring-1 ring-warning/20"><CreditCard className="size-4.5" /></span><div><h2 className="text-[14px] font-bold text-foreground">Pagos por actualizar</h2><p className="text-[11px] text-muted-foreground">Cuentas agrupadas por correo y plataforma</p></div></div>
      {!loading && <span className="w-fit rounded-full bg-warning/10 px-3 py-1 text-[10px] font-bold text-warning">{analyses.length} {analyses.length === 1 ? "cuenta pendiente" : "cuentas pendientes"}</span>}
    </div>
    {loading ? <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-2xl bg-surface-2" />)}</div> : analyses.length ? <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-3">{analyses.map((analysis) => <PaymentItem key={`${analysis.account_email}-${analysis.platform || analysis.service || analysis.category}`} analysis={analysis} />)}</div> : <div className="flex flex-col items-center px-5 py-9 text-center"><span className="grid size-11 place-items-center rounded-2xl bg-primary/10 text-primary"><CheckCircle2 className="size-5" /></span><p className="mt-3 text-[13px] font-semibold text-foreground">No hay pagos que requieran actualización</p><p className="mt-1 text-[11px] text-muted-foreground">GPT no detectó rechazos, tarjetas vencidas ni renovaciones pendientes.</p></div>}
  </section>;
}

function PaymentItem({ analysis }: { analysis: Analysis }) {
  const platform = analysis.platform || analysis.service || analysis.category;
  const reason = analysis.alert_types.includes("payment_rejected") ? "Pago rechazado" : analysis.alert_types.includes("payment_method_expired") ? "Método de pago vencido" : "Renovación pendiente";
  return <article className="rounded-2xl border border-border bg-surface-2/55 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-warning/30 hover:bg-card hover:shadow-sm">
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-[13px] font-bold text-foreground">{platform}</p><p className="mt-0.5 truncate text-[10.5px] text-muted-foreground" title={analysis.account_email}>{analysis.account_email}</p></div><RiskBadge risk={analysis.risk_level} /></div>
    <div className="mt-3 flex items-center gap-2 text-[11px] font-semibold text-warning"><AlertTriangle className="size-3.5" />{reason}</div>
    <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-foreground/75">{analysis.action_required || "Revisar y actualizar la información de pago."}</p>
  </article>;
}

function AnalysisCard({ analysis, index }: { analysis: Analysis; index: number }) {
  return <article style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }} className={cn("group relative animate-in overflow-hidden rounded-3xl border bg-card p-5 fill-mode-backwards duration-500 fade-in slide-in-from-bottom-3 transition-all hover:-translate-y-0.5 hover:shadow-md", riskBorder(analysis.risk_level))}>
    <div aria-hidden className={cn("absolute inset-y-0 left-0 w-1", riskBar(analysis.risk_level))} />
    <div className="flex items-start justify-between gap-3 pl-1"><div className="min-w-0"><div className="flex flex-wrap items-center gap-1.5"><span className="rounded-full bg-primary/10 px-2.5 py-1 text-[9.5px] font-bold uppercase tracking-wide text-primary">{analysis.category}</span><RiskBadge risk={analysis.risk_level} />{analysis.action_required && <span className="flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-1 text-[9.5px] font-semibold text-warning"><Zap className="size-3" />Acción</span>}</div><h2 className="mt-3 line-clamp-2 text-[15px] font-bold leading-5 tracking-tight text-foreground">{analysis.subject || "Sin asunto"}</h2><p className="mt-1 truncate text-[11.5px] text-muted-foreground">{analysis.sender || "Remitente desconocido"}</p><p className="mt-0.5 truncate text-[10.5px] text-muted-foreground/80">{analysis.account_email}</p></div><div className="flex shrink-0 flex-col items-end gap-2"><span className="grid size-10 place-items-center rounded-2xl bg-surface-2 text-primary ring-1 ring-border transition-transform duration-200 group-hover:scale-105"><Gauge className="size-4.5" /></span><time className="flex items-center gap-1 text-[10px] text-muted-foreground"><Clock3 className="size-3" />{new Date(analysis.created_at).toLocaleDateString("es-PE", { day: "2-digit", month: "short" })}</time></div></div>
    <div className="mt-4 grid grid-cols-2 gap-2 pl-1 text-[11.5px] sm:grid-cols-4"><Detail icon={Sparkles} label="Servicio" value={analysis.service || analysis.platform || "—"} /><Detail icon={Layers3} label="Tipo" value={analysis.email_type} /><Detail icon={Activity} label="Prioridad" value={analysis.priority} /><Detail icon={Inbox} label="País" value={analysis.country || "—"} /></div>
    {analysis.action_required ? <div className="mt-4 rounded-2xl border border-warning/20 bg-gradient-to-br from-warning/[0.08] to-transparent p-3.5"><div className="flex items-center gap-1.5 text-[9.5px] font-bold uppercase tracking-[0.14em] text-warning"><CheckCircle2 className="size-3.5" />Acción recomendada</div><p className="mt-1.5 text-[12.5px] leading-5 text-foreground/85">{analysis.action_required}</p></div> : <div className="mt-4 flex items-center gap-2 rounded-xl bg-primary/[0.05] px-3 py-2 text-[11px] text-primary"><ShieldCheck className="size-3.5" />No requiere una acción registrada.</div>}
    <details className="group/details mt-4 border-t border-border pt-3"><summary className="flex cursor-pointer list-none items-center justify-between rounded-lg px-1 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"><span className="flex items-center gap-1.5"><Cpu className="size-3.5" />Detalles técnicos</span><ChevronDown className="size-3.5 transition-transform group-open/details:rotate-180" /></summary><div className="mt-2 grid gap-2 rounded-xl bg-surface-2/60 p-3 text-[10.5px] text-muted-foreground sm:grid-cols-2"><p>Modelo: <span className="font-medium text-foreground/80">{analysis.model}</span></p><p>Prompt: <span className="font-medium text-foreground/80">{analysis.prompt_version}</span></p><p>Idioma: <span className="font-medium text-foreground/80">{analysis.language}</span></p><p>Importe: <span className="font-medium text-foreground/80">{analysis.amount ? `${analysis.amount} ${analysis.currency ?? ""}`.trim() : "—"}</span></p></div></details>
  </article>;
}

function Detail({ icon: Icon, label, value }: { icon: typeof Sparkles; label: string; value: string }) { return <div className="rounded-xl border border-transparent bg-surface-2/70 px-2.5 py-2.5 transition-colors group-hover:border-border"><p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"><Icon className="size-3" />{label}</p><p className="mt-1 truncate font-semibold text-foreground/85" title={value}>{value}</p></div>; }
function RiskBadge({ risk }: { risk: Risk }) { const label = { critical: "Urgente", high: "Prioritario", medium: "Revisar", low: "Informativo" }[risk]; return <span className={cn("rounded-full px-2.5 py-1 text-[9.5px] font-bold uppercase tracking-wide", risk === "critical" ? "bg-destructive/10 text-destructive" : risk === "high" ? "bg-warning/10 text-warning" : risk === "medium" ? "bg-chart-5/10 text-chart-5" : "bg-primary/10 text-primary")}>{label}</span>; }
function riskBorder(risk: Risk) { return risk === "critical" ? "border-destructive/30 hover:border-destructive/50" : risk === "high" ? "border-warning/25 hover:border-warning/45" : "border-border hover:border-border-strong"; }
function riskBar(risk: Risk) { return risk === "critical" ? "bg-destructive" : risk === "high" ? "bg-warning" : risk === "medium" ? "bg-chart-5" : "bg-primary"; }
function AnalysisSkeleton() { return <div className="grid gap-4 xl:grid-cols-2">{[0, 1, 2, 3].map((item) => <div key={item} className="h-72 animate-pulse rounded-3xl border border-border bg-card"><div className="m-5 h-5 w-1/3 rounded bg-surface-2" /><div className="mx-5 mt-4 h-4 w-2/3 rounded bg-surface-2" /><div className="mx-5 mt-8 grid grid-cols-4 gap-2">{[0, 1, 2, 3].map((cell) => <div key={cell} className="h-14 rounded-xl bg-surface-2" />)}</div><div className="mx-5 mt-4 h-16 rounded-2xl bg-surface-2" /></div>)}</div>; }
