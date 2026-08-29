import { NavLink } from "react-router-dom";
import { Bell, CreditCard, LayoutGrid, Mail, Settings, UserRoundCog, Users, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems: { label: string; icon: LucideIcon; to: string; tone: string }[] = [
  { label: "Resumen", icon: LayoutGrid, to: "/", tone: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
  { label: "Correos", icon: Mail, to: "/correos", tone: "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400" },
  { label: "Cuentas", icon: Users, to: "/cuentas", tone: "bg-cyan-500/12 text-cyan-600 dark:text-cyan-400" },
  { label: "Alertas", icon: Bell, to: "/alertas", tone: "bg-red-500/12 text-red-600 dark:text-red-400" },
  { label: "Configuración", icon: Settings, to: "/configuracion", tone: "bg-slate-500/12 text-slate-600 dark:text-slate-400" },
  { label: "Equipo", icon: UserRoundCog, to: "/equipo", tone: "bg-violet-500/12 text-violet-600 dark:text-violet-400" },
  { label: "Plan y consumo", icon: CreditCard, to: "/plan", tone: "bg-blue-500/12 text-blue-600 dark:text-blue-400" },
];

export function AppSidebar({ className, compact = false }: { className?: string; compact?: boolean }) {
  return <aside className={cn("flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar", compact ? "w-20" : "w-56", className)}>
    <div className={cn("flex items-center py-5", compact ? "justify-center px-2" : "gap-3 px-4")}><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25"><Mail className="size-[18px]" /></span>{!compact && <span className="min-w-0"><span className="block truncate text-sm font-semibold text-sidebar-foreground">Mail Control</span><span className="block text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Enterprise</span></span>}</div>
    <nav className={cn("flex-1 space-y-1 pt-2", compact ? "px-2" : "px-3")}>{navItems.map((item) => <NavLink key={item.to} to={item.to} end={item.to === "/"} title={compact ? item.label : undefined} aria-label={item.label} className={({ isActive }) => cn("flex w-full items-center rounded-xl py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60", compact ? "justify-center px-1" : "gap-2.5 px-2.5", isActive ? "bg-primary/12 font-semibold text-primary ring-1 ring-primary/25" : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground")}><span className={cn("grid size-8 shrink-0 place-items-center rounded-lg", item.tone)}><item.icon className="size-4" strokeWidth={2} /></span>{!compact && <span className="truncate">{item.label}</span>}</NavLink>)}</nav>
    <div className={cn("mb-4 mt-6", compact ? "mx-auto" : "mx-3 rounded-xl border border-sidebar-border bg-surface/60 px-3 py-3")} title="Sincronización y análisis activos"><p className="flex items-center gap-2 text-xs font-medium text-foreground"><span className="size-2 shrink-0 rounded-full bg-primary shadow-[0_0_0_3px_var(--primary-soft)]" />{!compact && "Sistema operativo"}</p>{!compact && <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">Sincronización y análisis activos</p>}</div>
  </aside>;
}
