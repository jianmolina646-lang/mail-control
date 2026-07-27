import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Bell, ChevronLeft, ChevronRight, CreditCard, Inbox, LayoutDashboard,
  LogOut, Mail, Menu, Moon, Settings, ShieldAlert, Sun, UsersRound, X,
} from "lucide-react";
import { api } from "../lib/api";

const groups = [
  { label: "Operación", items: [
    { to: "/", label: "Resumen", icon: LayoutDashboard, end: true },
    { to: "/bandeja", label: "Bandeja de entrada", icon: Inbox },
    { to: "/suscripciones", label: "Suscripciones", icon: CreditCard },
  ]},
  { label: "Administración", items: [
    { to: "/cuentas", label: "Cuentas conectadas", icon: UsersRound },
    { to: "/alertas", label: "Alertas", icon: ShieldAlert, alerts: true },
    { to: "/actividad", label: "Actividad", icon: Activity },
    { to: "/seguridad", label: "Configuración", icon: Settings },
  ]},
];

const pageMeta = {
  "/": { title: "Resumen operativo", section: "Workspace" },
  "/bandeja": { title: "Bandeja de entrada", section: "Correo" },
  "/suscripciones": { title: "Suscripciones", section: "Supervisión" },
  "/cuentas": { title: "Cuentas conectadas", section: "Administración" },
  "/alertas": { title: "Alertas críticas", section: "Supervisión" },
  "/plantillas": { title: "Plantillas", section: "Productividad" },
  "/actividad": { title: "Actividad de sincronización", section: "Supervisión" },
  "/seguridad": { title: "Configuración", section: "Administración" },
};

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [user, setUser] = useState(null);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");
  const currentPage = pageMeta[location.pathname] || { title: "Mail Control", section: "Workspace" };

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    api.me().then(setUser).catch(() => {});
    const load = () => api.stats().then(setStats).catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const toggleCollapsed = () => setCollapsed((value) => {
    localStorage.setItem("sidebar-collapsed", String(!value));
    return !value;
  });
  const logout = async () => { try { await api.logout(); } finally { navigate("/login"); } };

  return (
    <div className="app-shell">
      {mobileOpen && <button aria-label="Cerrar navegación" className="app-sidebar-overlay" onClick={() => setMobileOpen(false)} />}
      <aside className={`app-sidebar ${collapsed ? "is-collapsed" : ""} ${mobileOpen ? "is-open" : ""}`}>
        <div className="app-brand">
          <span className="app-brand-mark"><Mail size={17} /></span>
          {(!collapsed || mobileOpen) && <div className="app-brand-copy"><strong>Mail Control</strong><span>Centro operativo</span></div>}
          <button aria-label="Cerrar navegación" onClick={() => setMobileOpen(false)} className="app-icon-button ml-auto lg:hidden"><X size={18} /></button>
        </div>

        <div className={`app-health ${collapsed && !mobileOpen ? "is-compact" : ""}`}>
          <span className="app-health-dot" />
          {(!collapsed || mobileOpen) && <><span>Sistema operativo</span><small>Sincronización activa</small></>}
        </div>

        <nav className="app-navigation" aria-label="Navegación principal">
          {groups.map((group) => (
            <div key={group.label} className="app-nav-group">
              {(!collapsed || mobileOpen) && <p>{group.label}</p>}
              {group.items.map(({ to, label, icon: Icon, end, alerts }) => (
                <NavLink key={to} to={to} end={end} title={collapsed ? label : undefined} className={({ isActive }) => `app-nav-link ${isActive ? "is-active" : ""}`}>
                  <Icon size={17} />
                  {(!collapsed || mobileOpen) && <span>{label}</span>}
                  {alerts && stats?.alerts_open > 0 && <span className="app-alert-count">{stats.alerts_open}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="app-sidebar-footer">
          <div className={`app-user ${collapsed ? "is-compact" : ""}`}>
            <span className="app-user-avatar">{user?.email?.[0]?.toUpperCase() || "A"}</span>
            {!collapsed && <div><strong>{user?.email || "Administrador"}</strong><span>Administrador</span></div>}
          </div>
          <button onClick={logout} className={`app-nav-link app-logout ${collapsed ? "justify-center" : ""}`}>
            <LogOut size={17} />{!collapsed && <span>Cerrar sesión</span>}
          </button>
          <button onClick={toggleCollapsed} aria-label={collapsed ? "Expandir navegación" : "Contraer navegación"} className="app-collapse">
            {collapsed ? <ChevronRight size={17} /> : <><ChevronLeft size={17} /><span>Contraer menú</span></>}
          </button>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="app-topbar">
          <button aria-label="Abrir navegación" onClick={() => setMobileOpen(true)} className="app-icon-button lg:hidden"><Menu size={19} /></button>
          <div className="app-page-context"><span>{currentPage.section}</span><strong>{currentPage.title}</strong></div>
          <div className="app-topbar-actions">
            <span className="app-live-status"><i /> Supervisión activa</span>
            <NavLink to="/alertas" aria-label="Ver alertas" className="app-icon-button app-notification"><Bell size={18} />{stats?.alerts_open > 0 && <span />}</NavLink>
            <span className="app-topbar-divider" />
            <button aria-label={dark ? "Usar tema claro" : "Usar tema oscuro"} onClick={() => setDark(!dark)} className="app-icon-button">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          </div>
        </header>
        <main className="app-content"><Outlet context={{ stats, user }} /></main>
      </div>
    </div>
  );
}
