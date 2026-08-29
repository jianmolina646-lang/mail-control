import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Bell, Clock, Database, LogOut, Moon, PanelLeft, ShieldCheck, Sparkles, Sun } from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { clearSession } from "@/lib/api";
import { cn } from "@/lib/utils";

type Pref = {
  id: string;
  icon: typeof ShieldCheck;
  title: string;
  description: string;
  detail: string;
  state: "activo" | "proximamente";
};

const prefs: Pref[] = [
  {
    id: "sesion",
    icon: ShieldCheck,
    title: "Seguridad de la sesión",
    description: "Los accesos usan tokens cortos y renovación segura.",
    detail: "Tokens de 15 min · rotación automática",
    state: "activo",
  },
  {
    id: "analisis",
    icon: Sparkles,
    title: "Análisis automático",
    description: "Los mensajes nuevos se clasifican una sola vez mediante OpenAI.",
    detail: "Clasificación única por mensaje",
    state: "activo",
  },
  {
    id: "retencion",
    icon: Database,
    title: "Retención y privacidad",
    description: "La configuración de políticas estará disponible para administradores.",
    detail: "Requiere rol de administrador",
    state: "proximamente",
  },
];

export function SettingsManager() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [theme, setTheme] = useState<"dark" | "light">(() => document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const [enabled, setEnabled] = useState<Record<string, boolean>>({ sesion: true, analisis: true });

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
                <button type="button" aria-label="Abrir navegación" className="grid size-9 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground lg:hidden"><PanelLeft className="size-4" /></button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0">
                <SheetTitle className="sr-only">Navegación</SheetTitle>
                <AppSidebar className="w-full border-r-0" />
              </SheetContent>
            </Sheet>
            <span className="min-w-0">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workspace</span>
              <span className="block truncate text-[13px] font-semibold">Configuración</span>
            </span>
          </div>
          <div />
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={toggleTheme} aria-label="Tema" className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground">{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</button>
            <button type="button" onClick={() => navigate("/alertas")} aria-label="Alertas" className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><Bell className="size-4" /></button>
            <button type="button" onClick={logout} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><LogOut className="size-4" /><span className="hidden sm:inline">Salir</span></button>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-y-auto px-4 py-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-4xl">
            <section className="relative overflow-hidden rounded-3xl border border-border bg-surface/70 p-6 shadow-section lg:p-8">
              <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-full bg-primary/12 blur-3xl" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-primary">Preferencias</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight lg:text-4xl">Configuración</h1>
              <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-muted-foreground">Seguridad, proveedores y comportamiento del workspace.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Stat icon={ShieldCheck} label="Sesión protegida" />
                <Stat icon={Sparkles} label="IA activa" />
                <Stat icon={Clock} label="Actualizado hoy" />
              </div>
            </section>

            <div className="mt-6 space-y-3">
              {prefs.map((pref) => {
                const isSoon = pref.state === "proximamente";
                const on = enabled[pref.id] ?? false;
                return (
                  <article key={pref.id} className="group flex flex-col gap-4 rounded-2xl border border-border bg-surface/60 p-4 shadow-card transition-all hover:border-border-strong hover:bg-surface hover:shadow-card-hover sm:flex-row sm:items-center sm:p-5">
                    <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl ring-1 transition-colors", isSoon ? "bg-surface-2 text-muted-foreground ring-border" : "bg-primary/12 text-primary ring-primary/25")}><pref.icon className="size-[19px]" /></span>
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate text-[14.5px] font-semibold tracking-tight">{pref.title}</h2>
                      <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{pref.description}</p>
                      <p className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 text-[11px] text-muted-foreground">{pref.detail}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 sm:justify-end">
                      {isSoon ? <span className="rounded-xl border border-border bg-surface-2 px-3 py-1.5 text-[11.5px] font-medium text-muted-foreground">Próximamente</span> : <><span className={cn("hidden rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 sm:inline-flex", on ? "bg-primary/12 text-primary ring-primary/25" : "bg-surface-2 text-muted-foreground ring-border")}>{on ? "Activo" : "Inactivo"}</span><button type="button" role="switch" aria-checked={on} aria-label={`${pref.title}: ${on ? "activo" : "inactivo"}`} onClick={() => setEnabled((previous) => ({ ...previous, [pref.id]: !on }))} className={cn("relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50", on ? "bg-primary" : "bg-surface-3")}><span className={cn("absolute top-0.5 size-5 rounded-full bg-background transition-transform", on ? "translate-x-[22px]" : "translate-x-0.5")} /></button></>}
                    </div>
                  </article>
                );
              })}
            </div>
            <p className="mt-6 text-[11.5px] text-muted-foreground">Los cambios se aplican al workspace actual. Las políticas de retención las gestiona un administrador.</p>
          </div>
        </div>
      </div>
    </main>
  );
}

function Stat({ icon: Icon, label }: { icon: typeof ShieldCheck; label: string }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2/80 px-3 py-1.5 text-[11.5px] text-muted-foreground"><Icon className="size-3.5 text-primary" />{label}</span>;
}
