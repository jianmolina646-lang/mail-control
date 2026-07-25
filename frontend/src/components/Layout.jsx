import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, ChevronLeft, ChevronRight, CreditCard, Inbox, LayoutDashboard,
  LogOut, Mail, Menu, Moon, Settings, ShieldAlert, Sun, UsersRound, X,
} from "lucide-react";
import { api } from "../lib/api";

const groups = [
  { label: "Workspace", items: [
    { to: "/", label: "Resumen", icon: LayoutDashboard, end: true },
    { to: "/bandeja", label: "Bandeja de entrada", icon: Inbox },
    { to: "/suscripciones", label: "Suscripciones", icon: CreditCard },
  ]},
  { label: "Gestión", items: [
    { to: "/cuentas", label: "Cuentas", icon: UsersRound },
    { to: "/alertas", label: "Alertas", icon: ShieldAlert, alerts: true },
    { to: "/seguridad", label: "Configuración", icon: Settings },
  ]},
];

const pageTitles = {
  "/": "Resumen",
  "/bandeja": "Bandeja de entrada",
  "/suscripciones": "Suscripciones",
  "/cuentas": "Cuentas",
  "/alertas": "Alertas",
  "/plantillas": "Plantillas",
  "/seguridad": "Configuración",
};

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [user, setUser] = useState(null);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    api.me().then(setUser).catch(() => {});
    const load = () => api.stats().then(setStats).catch(() => {});
    load(); const timer = setInterval(load, 30000); return () => clearInterval(timer);
  }, []);
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const toggleCollapsed = () => setCollapsed((value) => {
    localStorage.setItem("sidebar-collapsed", String(!value)); return !value;
  });
  const logout = async () => { try { await api.logout(); } finally { navigate("/login"); } };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {mobileOpen && <button aria-label="Cerrar navegación" className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" onClick={() => setMobileOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-slate-200 bg-slate-950 text-slate-300 transition-[width,transform] duration-200 lg:static ${collapsed ? "lg:w-[72px]" : "lg:w-60"} ${mobileOpen ? "w-64 translate-x-0" : "w-64 -translate-x-full lg:translate-x-0"}`}>
        <div className="flex h-16 items-center border-b border-white/10 px-4">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand-600 text-white"><Mail size={17} /></span>
          {(!collapsed || mobileOpen) && <div className="ml-3 min-w-0"><strong className="block truncate text-sm text-white">Mail Control</strong><span className="block text-[10px] uppercase tracking-wider text-slate-500">Operaciones de correo</span></div>}
          <button aria-label="Cerrar navegación" onClick={() => setMobileOpen(false)} className="ml-auto rounded p-1 text-slate-400 hover:bg-white/10 lg:hidden"><X size={18} /></button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-4">
          {groups.map((group) => <div key={group.label} className="mb-5">
            {(!collapsed || mobileOpen) && <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[.12em] text-slate-600">{group.label}</p>}
            <div className="space-y-0.5">{group.items.map(({ to, label, icon: Icon, end, alerts }) => <NavLink key={to} to={to} end={end} title={collapsed ? label : undefined} className={({ isActive }) => `flex h-10 items-center gap-3 rounded-md px-2.5 text-sm ${isActive ? "bg-white/10 font-medium text-white" : "text-slate-400 hover:bg-white/[.06] hover:text-slate-100"}`}><Icon size={18} className="shrink-0" />{(!collapsed || mobileOpen) && <span className="truncate">{label}</span>}{alerts && stats?.alerts_open > 0 && <span className="ml-auto min-w-5 rounded-full bg-rose-500 px-1.5 text-center text-[10px] font-semibold text-white">{stats.alerts_open}</span>}</NavLink>)}</div>
          </div>)}
        </nav>
        <div className="border-t border-white/10 p-2">
          <div className={`mb-1 flex items-center gap-2 px-2 py-2 ${collapsed ? "justify-center" : ""}`}>
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-200">{user?.email?.[0]?.toUpperCase() || "A"}</span>
            {!collapsed && <div className="min-w-0 flex-1"><span className="block truncate text-xs font-medium text-slate-200">{user?.email || "Administrador"}</span><span className="text-[10px] text-slate-500">Administrador</span></div>}
          </div>
          <button onClick={logout} className={`flex h-9 w-full items-center gap-3 rounded-md px-2.5 text-sm text-slate-400 hover:bg-white/[.06] hover:text-white ${collapsed ? "justify-center" : ""}`}><LogOut size={17} />{!collapsed && "Cerrar sesión"}</button>
          <button onClick={toggleCollapsed} aria-label={collapsed ? "Expandir navegación" : "Contraer navegación"} className="mt-1 hidden h-8 w-full items-center justify-center rounded-md text-slate-500 hover:bg-white/[.06] hover:text-slate-300 lg:flex">{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900 md:px-6">
          <button aria-label="Abrir navegación" onClick={() => setMobileOpen(true)} className="btn-quiet mr-2 px-2 lg:hidden"><Menu size={19} /></button>
          <span className="text-sm font-medium text-slate-900 dark:text-white lg:hidden">{pageTitles[location.pathname] || "Mail Control"}</span>
          <div className="ml-auto flex items-center gap-1">
            <NavLink to="/alertas" aria-label="Ver alertas" className="btn-quiet relative px-2.5"><Bell size={18} />{stats?.alerts_open > 0 && <span className="absolute right-2 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500" />}</NavLink>
            <button aria-label={dark ? "Usar tema claro" : "Usar tema oscuro"} onClick={() => setDark(!dark)} className="btn-quiet px-2.5">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto"><Outlet context={{ stats, user }} /></main>
      </div>
    </div>
  );
}
