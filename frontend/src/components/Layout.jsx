import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, ChevronLeft, ChevronRight, Inbox, KeyRound, LayoutGrid, LogOut,
  Mail, Menu, Moon, Plus, Radio, Settings, ShieldAlert, Sun, TicketCheck,
  UsersRound, X,
} from "lucide-react";
import { api } from "../lib/api";

const links = [
  { to: "/", label: "Bandeja de entrada", icon: Inbox, end: true },
  { to: "/alertas", label: "Alertas críticas", icon: ShieldAlert, badge: true },
  { to: "/cuentas", label: "Cuentas", icon: UsersRound },
  { to: "/plantillas", label: "Plantillas de ventas", icon: LayoutGrid },
  { to: "/seguridad", label: "Configuración", icon: Settings },
];

const titles = {
  "/": ["Bandeja de entrada", "Gestiona todos tus correos desde un solo lugar"],
  "/alertas": ["Alertas críticas", "Prioriza incidencias que requieren atención"],
  "/cuentas": ["Cuentas vinculadas", "Administra tus proveedores de correo"],
  "/plantillas": ["Plantillas", "Responde más rápido con contenido reutilizable"],
  "/seguridad": ["Configuración", "Seguridad y preferencias del panel"],
};

export default function Layout() {
  const nav = useNavigate();
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    const load = () => api.stats().then(setStats).catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  const toggleSidebar = () => {
    setCollapsed((value) => {
      localStorage.setItem("sidebar-collapsed", String(!value));
      return !value;
    });
  };

  const logout = async () => {
    try { await api.logout(); } finally { nav("/login"); }
  };

  const [title, subtitle] = titles[location.pathname] || ["Mail Control", "Centro de operaciones"];

  return (
    <div className="app-background flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {mobileOpen && <button aria-label="Cerrar menú" onClick={() => setMobileOpen(false)} className="fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-sm lg:hidden" />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-slate-200/80 bg-white/90 backdrop-blur-xl transition-all duration-300 dark:border-white/10 dark:bg-slate-950/90 lg:static ${collapsed ? "lg:w-[84px]" : "lg:w-64"} ${mobileOpen ? "w-72 translate-x-0" : "w-72 -translate-x-full lg:translate-x-0"}`}>
        <div className="flex h-20 items-center gap-3 px-5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-violet-700 text-white shadow-glow"><Mail size={22} /></div>
          {(!collapsed || mobileOpen) && <div className="min-w-0 animate-fade-in"><div className="font-bold tracking-tight text-slate-950 dark:text-white">Mail Control</div><div className="text-[10px] font-semibold uppercase tracking-[.2em] text-brand-600">Team Jheliz</div></div>}
          <button onClick={() => setMobileOpen(false)} className="ml-auto text-slate-400 lg:hidden"><X size={20} /></button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {!collapsed && <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">Workspace</p>}
          {links.map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink key={to} to={to} end={end} title={collapsed ? label : undefined} className={({ isActive }) => `group flex h-12 items-center gap-3 rounded-xl px-3 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"}`}>
              <Icon size={20} className="shrink-0" />
              {(!collapsed || mobileOpen) && <span className="truncate">{label}</span>}
              {badge && stats?.alerts_open > 0 && <span className="ml-auto rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-bold text-white">{stats.alerts_open}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200/80 p-3 dark:border-white/10">
          <button onClick={logout} title="Cerrar sesión" className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10"><LogOut size={19} />{(!collapsed || mobileOpen) && "Cerrar sesión"}</button>
          <button onClick={toggleSidebar} className="mt-1 hidden h-10 w-full items-center justify-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/5 lg:flex">{collapsed ? <ChevronRight size={18} /> : <><ChevronLeft size={18} /><span className="ml-2 text-xs">Contraer menú</span></>}</button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass z-20 flex h-20 shrink-0 items-center gap-3 border-x-0 border-t-0 px-4 md:px-7">
          <button onClick={() => setMobileOpen(true)} className="btn-secondary px-2.5 lg:hidden"><Menu size={19} /></button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-bold text-slate-950 dark:text-white">{title}</h1>
            <p className="hidden truncate text-xs text-slate-500 sm:block">{subtitle}</p>
          </div>
          <button onClick={() => setDark(!dark)} aria-label="Cambiar tema" className="btn-secondary px-2.5">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          <NavLink to="/alertas" className="btn-secondary relative px-2.5"><Bell size={18} />{stats?.alerts_open > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-white dark:ring-slate-900" />}</NavLink>
          <button onClick={() => setQuickOpen(true)} className="btn-primary"><Plus size={18} /><span className="hidden sm:inline">Acción rápida</span></button>
        </header>
        <main className="min-h-0 flex-1 overflow-auto"><Outlet context={{ stats }} /></main>
      </div>
      {quickOpen && <QuickActions onClose={() => setQuickOpen(false)} />}
    </div>
  );
}

function QuickActions({ onClose }) {
  const actions = [
    { icon: KeyRound, label: "Enviar licencia", detail: "Clave y activación", tone: "bg-violet-100 text-violet-600 dark:bg-violet-500/15" },
    { icon: Radio, label: "Compartir acceso", detail: "Streaming y perfiles", tone: "bg-sky-100 text-sky-600 dark:bg-sky-500/15" },
    { icon: TicketCheck, label: "Crear ticket", detail: "Seguimiento al cliente", tone: "bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15" },
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div onMouseDown={(e) => e.stopPropagation()} className="glass w-full max-w-md animate-slide-up rounded-3xl p-5">
        <div className="mb-5 flex items-center justify-between"><div><h2 className="font-bold text-slate-950 dark:text-white">Acciones rápidas</h2><p className="text-xs text-slate-500">¿Qué deseas enviar?</p></div><button onClick={onClose} className="btn-secondary px-2.5"><X size={18} /></button></div>
        <div className="space-y-2">{actions.map(({ icon: Icon, label, detail, tone }) => <NavLink key={label} to="/plantillas" onClick={onClose} className="flex items-center gap-3 rounded-2xl border border-transparent p-3 hover:border-brand-200 hover:bg-white/70 dark:hover:bg-white/5"><span className={`flex h-11 w-11 items-center justify-center rounded-xl ${tone}`}><Icon size={20} /></span><span><strong className="block text-sm text-slate-800 dark:text-white">{label}</strong><small className="text-slate-500">{detail}</small></span><ChevronRight className="ml-auto text-slate-400" size={18} /></NavLink>)}</div>
      </div>
    </div>
  );
}
