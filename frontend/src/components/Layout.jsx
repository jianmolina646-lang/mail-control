import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, setToken } from "../lib/api";

const links = [
  { to: "/", label: "Bandeja", icon: "📥", end: true },
  { to: "/alertas", label: "Alertas críticas", icon: "🚨" },
  { to: "/cuentas", label: "Cuentas", icon: "🗃️" },
  { to: "/seguridad", label: "Seguridad", icon: "🔐" },
];

export default function Layout() {
  const nav = useNavigate();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const load = () => api.stats().then(setStats).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const logout = () => {
    setToken("");
    nav("/login");
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="md:w-64 bg-panel border-b md:border-b-0 md:border-r border-edge flex md:flex-col">
        <div className="p-4 md:p-5 border-edge md:border-b flex-1 md:flex-none">
          <div className="flex items-center gap-2">
            <span className="text-gold text-2xl">👑</span>
            <div>
              <div className="font-bold text-white leading-tight">Mail Control</div>
              <div className="text-[10px] tracking-widest text-gold">TEAM JHELIZ</div>
            </div>
          </div>
        </div>
        <nav className="flex md:flex-col p-2 md:p-3 gap-1 flex-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? "bg-accent/15 text-white border border-accent/40"
                    : "text-zinc-400 hover:bg-edge/60 hover:text-white"
                }`
              }
            >
              <span>{l.icon}</span>
              <span className="hidden sm:inline">{l.label}</span>
              {l.to === "/alertas" && stats?.alerts_open > 0 && (
                <span className="ml-auto bg-accent text-white text-xs px-1.5 rounded-full">
                  {stats.alerts_open}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={logout}
          className="m-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-edge/60 hover:text-white text-left"
        >
          ⎋ Salir
        </button>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-edge border-b border-edge text-center">
            <Stat label="Cuentas" value={stats.accounts_total} />
            <Stat label="OK" value={stats.accounts_ok} tone="text-emerald-400" />
            <Stat label="Con error" value={stats.accounts_error} tone="text-amber-400" />
            <Stat label="Alertas" value={stats.alerts_open} tone="text-accent" />
          </div>
        )}
        <div className="flex-1 min-h-0">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function Stat({ label, value, tone = "text-white" }) {
  return (
    <div className="bg-panel py-2.5">
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );
}
