import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  CreditCard,
  Inbox,
  LogOut,
  Moon,
  PanelLeft,
  Sparkles,
  Sun,
  Users,
  Zap,
} from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession } from "@/lib/api";
import type { PlanUsage } from "@/lib/types";
import { cn } from "@/lib/utils";

type Quota = {
  id: string;
  icon: typeof Users;
  label: string;
  used: number;
  limit: number;
  hint: string;
};

const fmt = (value: number) => value.toLocaleString("es");

function readableStatus(value: string) {
  const names: Record<string, string> = {
    active: "Activo",
    trialing: "Trialing",
    trial: "Prueba",
    past_due: "Pago pendiente",
    canceled: "Cancelado",
    cancelled: "Cancelado",
  };
  return names[value.toLowerCase()] ?? value;
}

function readableDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("es");
}

export function PlanManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );
  const query = useQuery({
    queryKey: ["plan-usage"],
    queryFn: () => api<PlanUsage>("/v1/saas/usage"),
  });

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
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
                <button
                  type="button"
                  aria-label="Abrir navegación"
                  className="grid size-9 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground lg:hidden"
                >
                  <PanelLeft className="size-4" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0">
                <SheetTitle className="sr-only">Navegación</SheetTitle>
                <AppSidebar className="w-full border-r-0" />
              </SheetContent>
            </Sheet>
            <span className="min-w-0">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Workspace
              </span>
              <span className="block truncate text-[13px] font-semibold">Plan y consumo</span>
            </span>
          </div>

          <div />

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Tema"
              className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <button
              type="button"
              onClick={() => navigate("/alertas")}
              aria-label="Alertas"
              className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              <Bell className="size-4" />
            </button>
            <button
              type="button"
              onClick={logout}
              className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              <LogOut className="size-4" />
              <span className="hidden sm:inline">Salir</span>
            </button>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-y-auto px-4 py-6 lg:px-8 lg:py-8">
          {query.isLoading ? (
            <PlanSkeleton />
          ) : query.isError || !query.data ? (
            <PlanError retry={() => query.refetch()} />
          ) : (
            <PlanContent data={query.data} />
          )}
        </div>
      </div>
    </main>
  );
}

function PlanContent({ data }: { data: PlanUsage }) {
  const status = readableStatus(data.status);
  const renews = readableDate(data.period_end);
  const quotas: Quota[] = [
    { id: "cuentas", icon: Inbox, label: "Cuentas", used: data.accounts, limit: data.accounts_limit, hint: "Buzones conectados" },
    { id: "usuarios", icon: Users, label: "Usuarios", used: data.users, limit: data.users_limit, hint: "Miembros del workspace" },
    { id: "mensajes", icon: Zap, label: "Mensajes este mes", used: data.messages_this_month, limit: data.messages_limit, hint: "Procesados en el periodo" },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-surface/70 p-6 shadow-section lg:p-8">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-full bg-primary/12 blur-3xl" />
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-primary">Suscripción SaaS</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight lg:text-4xl">Plan y consumo</h1>
        <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-muted-foreground">Límites operativos del periodo actual.</p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Chip icon={CreditCard} label={`Plan ${data.plan_name}`} />
          <Chip icon={Sparkles} label={status} />
          <Chip icon={CalendarClock} label={`Renueva el ${renews}`} />
        </div>
      </section>

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
        <article className="relative overflow-hidden rounded-2xl border border-border bg-surface/60 p-5 shadow-card transition-all hover:border-border-strong hover:bg-surface hover:shadow-card-hover">
          <div aria-hidden className="pointer-events-none absolute -left-16 -bottom-16 size-44 rounded-full bg-primary/10 blur-3xl" />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/12 px-2.5 py-1 text-[11px] font-semibold text-primary ring-1 ring-primary/25">
            <span className="size-1.5 rounded-full bg-primary" />
            {status}
          </span>
          <h2 className="mt-4 text-[28px] font-semibold tracking-tight">{data.plan_name}</h2>
          <p className="mt-1 text-[12.5px] text-muted-foreground">Renueva el {renews}</p>
          <div className="mt-5 grid size-11 place-items-center rounded-xl bg-primary/12 text-primary ring-1 ring-primary/25">
            <CreditCard className="size-[19px]" />
          </div>
        </article>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {quotas.map((quota) => <QuotaCard key={quota.id} quota={quota} />)}
        </div>
      </div>

      <p className="mt-6 text-[11.5px] text-muted-foreground">El consumo se reinicia al inicio de cada periodo de facturación.</p>
    </div>
  );
}

function QuotaCard({ quota }: { quota: Quota }) {
  const pct = quota.limit > 0 ? Math.min(100, (quota.used / quota.limit) * 100) : 0;
  const rounded = Math.round(pct);
  const tone = pct >= 90 ? "danger" : pct >= 70 ? "warning" : "ok";
  return (
    <article className="flex flex-col rounded-2xl border border-border bg-surface/60 p-4 shadow-card transition-all hover:border-border-strong hover:bg-surface hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted-foreground ring-1 ring-border"><quota.icon className="size-4" /></span>
        <span className="text-right text-[13px] font-semibold tabular-nums">{fmt(quota.used)} <span className="text-muted-foreground">/ {fmt(quota.limit)}</span></span>
      </div>
      <p className="mt-3 truncate text-[13px] font-medium">{quota.label}</p>
      <p className="mt-0.5 truncate text-[11.5px] text-muted-foreground">{quota.hint}</p>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
        <div
          className={cn("h-full rounded-full transition-all", tone === "danger" ? "bg-destructive" : tone === "warning" ? "bg-warning" : "bg-primary")}
          style={{ width: `${Math.max(pct, pct > 0 ? 3 : 0)}%` }}
        />
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">{rounded}% utilizado</p>
    </article>
  );
}

function Chip({ icon: Icon, label }: { icon: typeof Users; label: string }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2/80 px-3 py-1.5 text-[11.5px] text-muted-foreground"><Icon className="size-3.5 text-primary" />{label}</span>;
}

function PlanSkeleton() {
  return <div className="mx-auto w-full max-w-5xl animate-pulse"><div className="h-56 rounded-3xl border border-border bg-surface/70" /><div className="mt-6 grid gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-44 rounded-2xl border border-border bg-surface/60" />)}</div></div>;
}

function PlanError({ retry }: { retry: () => void }) {
  return <div className="mx-auto flex min-h-72 w-full max-w-5xl flex-col items-center justify-center rounded-3xl border border-destructive/30 bg-destructive/10 px-6 text-center"><CreditCard className="size-8 text-destructive" /><h1 className="mt-4 text-xl font-semibold">No pudimos cargar el plan</h1><p className="mt-2 text-[13px] text-muted-foreground">Comprueba la conexión e inténtalo nuevamente.</p><button type="button" onClick={retry} className="mt-5 h-9 rounded-xl border border-border bg-surface-2 px-4 text-[12.5px] font-semibold hover:border-border-strong">Reintentar</button></div>;
}
