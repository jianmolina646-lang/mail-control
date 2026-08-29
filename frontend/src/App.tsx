/*
THESIS: Mail Control is an incident desk, not a gallery of KPI cards.
OWN-WORLD: graphite planes, one operational green, hairline borders, compact rows.
STORY: authenticate, see what needs attention, inspect mail, resolve or reconnect.
FIRST VIEWPORT: stable rail, command header, dense summary, trend and alert queue.
FORM: command-center split view, assigned structure 7, seed 4a29bf2b.
*/
import { FormEvent, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  Check,
  ChevronRight,
  CircleAlert,
  Inbox,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  CreditCard,
  X,
  type LucideIcon,
} from "lucide-react";
import { MailInbox } from "./MailInbox";
import { AccountManager } from "./AccountManager";
import { AlertManager } from "./AlertManager";
import { SettingsManager } from "./SettingsManager";
import { TeamManager } from "./TeamManager";
import { PlanManager } from "./PlanManager";
import { SummaryManager } from "./SummaryManager";
import { LoginManager } from "./LoginManager";
import { AnalysisManager } from "./AnalysisManager";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  clearSession,
  currentUser,
  hasSession,
  recordSessionActivity,
  saveSession,
  sessionExpired,
  subscribeSession,
} from "./lib/api";
import type { Account, Alert, Message, Page, PlanUsage, Summary, TokenPair, WorkspaceUser } from "./lib/types";

const nav = [
  { to: "/", label: "Resumen", icon: LayoutDashboard },
  { to: "/correos", label: "Correos", icon: Inbox },
  { to: "/analisis", label: "Análisis IA", icon: Sparkles },
  { to: "/cuentas", label: "Cuentas", icon: Mail },
  { to: "/alertas", label: "Alertas", icon: Bell },
  { to: "/configuracion", label: "Configuración", icon: Settings },
  { to: "/equipo", label: "Equipo", icon: Users },
  { to: "/plan", label: "Plan y consumo", icon: CreditCard },
];

export function LegacyLogin() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const login = useMutation({
    mutationFn: (body: { tenant_slug: string; email: string; password: string }) =>
      api<TokenPair>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }, false),
    onSuccess: (tokens) => {
      saveSession(tokens);
      navigate("/");
    },
    onError: (reason: Error) => setError(reason.message),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    clearSession();
    const data = new FormData(event.currentTarget);
    login.mutate({
      tenant_slug: String(data.get("tenant")).trim().toLowerCase(),
      email: String(data.get("email")).trim().toLowerCase(),
      password: String(data.get("password")),
    });
  }
  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="brand-mark"><Mail size={22} aria-hidden /></div>
        <p className="brand-name">Mail Control</p>
        <h1>La operación de correo, bajo control.</h1>
        <p>Supervisa cuentas, detecta incidencias y actúa antes de que un problema afecte a tus clientes.</p>
        <div className="login-proof">
          <ShieldCheck size={18} aria-hidden />
          <span>OAuth seguro · Datos aislados · Auditoría por distribuidor</span>
        </div>
      </section>
      <section className="login-panel" aria-labelledby="login-title">
        <div>
          <p className="section-kicker">Acceso al workspace</p>
          <h2 id="login-title">Iniciar sesión</h2>
          <p className="muted">Usa las credenciales de tu distribuidor.</p>
        </div>
        <form onSubmit={submit}>
          <label>Workspace<input name="tenant" placeholder="mi-distribuidor" required /></label>
          <label>Correo<input name="email" type="email" autoComplete="email" required /></label>
          <label>Contraseña<input name="password" type="password" autoComplete="current-password" required /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button primary" disabled={login.isPending}>
            {login.isPending ? "Verificando…" : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}

function Shell() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const isAdmin = ["owner", "admin"].includes(currentUser()?.role ?? "");
  const visibleNav = isAdmin ? nav : nav.filter((item) => !["/equipo", "/plan"].includes(item.to));
  const title = visibleNav.find((item) => item.to === location.pathname)?.label ?? "Mail Control";
  function logout() {
    clearSession();
    queryClient.clear();
    navigate("/login", { replace: true });
  }
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
  }
  if (location.pathname === "/correos") return <MailInbox />;
  if (location.pathname === "/analisis") return <AnalysisManager />;
  if (location.pathname === "/cuentas") return <AccountManager />;
  if (location.pathname === "/alertas") return <AlertManager />;
  if (location.pathname === "/configuracion") return <SettingsManager />;
  if (location.pathname === "/equipo") return isAdmin ? <TeamManager /> : <Navigate to="/" replace />;
  if (location.pathname === "/plan") return isAdmin ? <PlanManager /> : <Navigate to="/" replace />;
  if (location.pathname === "/") return <SummaryManager />;
  return (
    <div className="app-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="sidebar-brand">
          <div className="brand-mark"><Mail size={19} /></div>
          <div><strong>Mail Control</strong><span>Enterprise</span></div>
          <button className="icon-button close-nav" onClick={() => setOpen(false)} aria-label="Cerrar menú"><X /></button>
        </div>
        <nav aria-label="Navegación principal">
          {visibleNav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}>
              <Icon size={18} aria-hidden /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" /> Sistema operativo
          <small>Sincronización y análisis activos</small>
        </div>
      </aside>
      {open && <button className="scrim" onClick={() => setOpen(false)} aria-label="Cerrar menú" />}
      <div className="work-area">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setOpen(true)} aria-label="Abrir menú"><Menu /></button>
          <div><span>Workspace</span><strong>{title}</strong></div>
          <div className="top-actions">
            <button className="icon-button" onClick={toggleTheme} aria-label="Cambiar tema">
              {theme === "dark" ? <Sun /> : <Moon />}
            </button>
            <button className="icon-button notification-button" aria-label="Notificaciones"><Bell /><i /></button>
            <button className="logout-button" onClick={logout}><LogOut size={17} /> <span>Salir</span></button>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/correos" element={currentUser() ? <MailInbox /> : <Messages />} />
          <Route path="/analisis" element={<AnalysisManager />} />
          <Route path="/cuentas" element={<Accounts />} />
          <Route path="/alertas" element={<Alerts />} />
          <Route path="/configuracion" element={<SettingsPage />} />
          <Route path="/equipo" element={isAdmin ? <TeamPage /> : <Navigate to="/" replace />} />
          <Route path="/plan" element={isAdmin ? <PlanPage /> : <Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

function PageHeading({ kicker, title, description, action }: { kicker: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-heading"><div><p className="section-kicker">{kicker}</p><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}

function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api<Summary>("/v1/dashboard/summary") });
  const alerts = useQuery({ queryKey: ["alerts", "dashboard"], queryFn: () => api<Page<Alert>>("/v1/alerts?limit=5") });
  if (summary.isLoading) return <Loading />;
  if (summary.isError || !summary.data) return <ErrorState retry={() => summary.refetch()} />;
  const data = summary.data;
  return (
    <main className="page">
      <PageHeading kicker="Centro de operaciones" title="Resumen" description="Estado actual de tus buzones, análisis y alertas." />
      <section className="metric-strip" aria-label="Métricas principales">
        <Metric label="Cuentas conectadas" value={data.connected_accounts} />
        <Metric label="Mensajes" value={data.total_messages} />
        <Metric label="Analizados" value={`${data.analysis_coverage_percent}%`} />
        <Metric label="Alertas abiertas" value={data.open_alerts} danger={data.critical_alerts > 0} />
      </section>
      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-heading"><div><p className="section-kicker">Últimos 14 días</p><h2>Flujo de actividad</h2></div><span>{data.messages_last_24h} hoy</span></div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.trend}>
                <CartesianGrid vertical={false} stroke="var(--line)" />
                <XAxis dataKey="day" tickFormatter={(v) => new Date(`${v}T00:00:00`).toLocaleDateString("es", { weekday: "short" })} />
                <YAxis width={28} />
                <Tooltip />
                <Area type="monotone" dataKey="messages" stroke="var(--accent)" fill="var(--accent-soft)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel alert-panel">
          <div className="panel-heading"><div><p className="section-kicker">Atención requerida</p><h2>Alertas recientes</h2></div><NavLink to="/alertas">Ver todas</NavLink></div>
          <AlertList alerts={alerts.data?.items ?? []} compact />
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: string | number; danger?: boolean }) {
  return <div className={danger ? "metric danger" : "metric"}><span>{label}</span><strong>{value}</strong></div>;
}

function Messages() {
  const [search, setSearch] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["messages", search],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => api<Page<Message>>(`/v1/mail/messages?limit=50${search.trim().length >= 2 ? `&search=${encodeURIComponent(search.trim())}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
  const messages = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <main className="page">
      <PageHeading kicker="Bandeja unificada" title="Correos" description="Todos tus proveedores, una sola vista operativa." />
      <div className="search-field"><Search size={18} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar remitente, asunto o contenido…" aria-label="Buscar correos" /></div>
      <section className="data-list">
        <div className="list-header"><span>Mensaje</span><span>Cuenta</span><span>Clasificación</span><span>Recibido</span></div>
        {query.isLoading ? <Loading /> : messages.length ? <>{messages.map((message) => <MessageRow key={message.id} message={message} />)}{query.hasNextPage && <div className="load-more"><button className="button" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>{query.isFetchingNextPage ? "Cargando…" : "Cargar más"}</button></div>}</> : <Empty icon={Inbox} title="No hay correos para mostrar" detail="Conecta una cuenta o cambia los filtros de búsqueda." />}
      </section>
    </main>
  );
}

function MessageRow({ message }: { message: Message }) {
  return <article className="message-row"><div className="message-main"><span className={`provider-icon ${message.provider}`}>{message.provider === "gmail" ? "G" : "M"}</span><div><strong>{message.subject || "Sin asunto"}</strong><span>{message.sender || "Remitente desconocido"}</span><p>{message.snippet}</p></div></div><span className="account-cell">{message.account_email}</span><div className="classification">{message.category && <span className="badge">{message.category}</span>}{message.risk_level && message.risk_level !== "low" && <span className={`risk ${message.risk_level}`}>{message.risk_level}</span>}</div><time>{message.received_at ? new Date(message.received_at).toLocaleString("es", { dateStyle: "short", timeStyle: "short" }) : "—"}</time></article>;
}

function Accounts() {
  const canManage = currentUser()?.role !== "viewer";
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/v1/mail/accounts") });
  async function connect(provider: "gmail" | "microsoft") {
    const result = await api<{ authorization_url: string }>(`/v1/providers/${provider}/authorize`, { method: "POST" });
    window.location.assign(result.authorization_url);
  }
  async function sync(account: Account) {
    await api(`/v1/providers/${account.provider}/${account.id}/sync`, { method: "POST" });
    await client.invalidateQueries({ queryKey: ["accounts"] });
  }
  return (
    <main className="page">
      <PageHeading kicker="Proveedores" title="Cuentas conectadas" description="Controla sincronización, estado y volumen por buzón." action={canManage ? <div className="heading-actions"><button className="button" onClick={() => connect("gmail")}><Plus size={17} /> Gmail</button><button className="button primary" onClick={() => connect("microsoft")}><Plus size={17} /> Microsoft</button></div> : undefined} />
      <section className="accounts-grid">
        {query.isLoading ? <Loading /> : query.data?.length ? query.data.map((account) => <article className="account-card" key={account.id}><div className="account-top"><span className={`provider-icon ${account.provider}`}>{account.provider === "gmail" ? "G" : "M"}</span><span className={`status ${account.status}`}>{account.status}</span></div><div><h2>{account.email}</h2><p>{account.provider === "gmail" ? "Google Gmail" : "Microsoft Outlook / Hotmail / Live"}</p></div><dl><div><dt>Mensajes</dt><dd>{account.message_count}</dd></div><div><dt>Alertas</dt><dd>{account.alert_count}</dd></div></dl><footer><span>{account.last_synced_at ? `Actualizada ${new Date(account.last_synced_at).toLocaleString("es")}` : "Pendiente de sincronización"}</span>{canManage && <button className="icon-button" onClick={() => sync(account)} aria-label={`Sincronizar ${account.email}`}><RefreshCw /></button>}</footer></article>) : <Empty icon={Mail} title="Aún no hay cuentas conectadas" detail="Conecta Gmail o Microsoft para iniciar la primera sincronización." />}
      </section>
    </main>
  );
}

function Alerts() {
  const canManage = currentUser()?.role !== "viewer";
  const client = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: ["alerts"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => api<Page<Alert>>(`/v1/alerts?limit=50${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
  const alerts = query.data?.pages.flatMap((page) => page.items) ?? [];
  const resolve = useMutation({
    mutationFn: (id: string) => api(`/v1/alerts/${id}/resolve`, { method: "PATCH" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["alerts"] }),
  });
  return <main className="page"><PageHeading kicker="Detección automática" title="Alertas" description="Incidencias priorizadas por riesgo y acción requerida." /><section className="panel"><AlertList alerts={alerts} onResolve={canManage ? (id) => resolve.mutate(id) : undefined} />{query.hasNextPage && <div className="load-more"><button className="button" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>{query.isFetchingNextPage ? "Cargando…" : "Cargar más"}</button></div>}{!query.isLoading && !alerts.length && <Empty icon={ShieldCheck} title="Todo en orden" detail="No hay alertas abiertas en este momento." />}</section></main>;
}

function AlertList({ alerts, compact = false, onResolve }: { alerts: Alert[]; compact?: boolean; onResolve?: (id: string) => void }) {
  return <div className={compact ? "alert-list compact" : "alert-list"}>{alerts.map((alert) => <article key={alert.id} className="alert-row"><span className={`alert-symbol ${alert.risk_level}`}>{alert.risk_level === "critical" ? <CircleAlert /> : <AlertTriangle />}</span><div><strong>{alert.title}</strong><p>{alert.detail || "Revisa el mensaje relacionado para obtener más información."}</p><time>{new Date(alert.created_at).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" })}</time></div>{onResolve ? <button className="button quiet" onClick={() => onResolve(alert.id)}><Check size={16} /> Resolver</button> : <ChevronRight size={18} />}</article>)}</div>;
}

function SettingsPage() {
  return <main className="page"><PageHeading kicker="Preferencias" title="Configuración" description="Seguridad, proveedores y comportamiento del workspace." /><section className="settings-list"><div><h2>Seguridad de la sesión</h2><p>Los accesos usan tokens cortos y renovación segura.</p><span className="badge success">Activo</span></div><div><h2>Análisis automático</h2><p>Los mensajes nuevos se clasifican una sola vez mediante OpenAI.</p><span className="badge success">Activo</span></div><div><h2>Retención y privacidad</h2><p>La configuración de políticas estará disponible para administradores.</p><button className="button" disabled>Próximamente</button></div></section></main>;
}

function TeamPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["workspace-users"], queryFn: () => api<WorkspaceUser[]>("/v1/saas/users") });
  const create = useMutation({
    mutationFn: (body: object) => api<WorkspaceUser>("/v1/saas/users", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["workspace-users"] }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    create.mutate(Object.fromEntries(data));
    if (!create.isError) form.reset();
  }
  return <main className="page"><PageHeading kicker="Administración" title="Equipo" description="Usuarios y permisos aislados dentro de este workspace." /><div className="team-grid"><section className="panel"><div className="panel-heading"><h2>Usuarios</h2><span>{query.data?.length ?? 0}</span></div>{query.data?.map((user) => <div className="user-row" key={user.id}><span className="provider-icon">{user.display_name.slice(0, 1)}</span><div><strong>{user.display_name}</strong><p>{user.email}</p></div><span className="badge">{user.role}</span><span className={user.is_active ? "badge success" : "badge"}>{user.is_active ? "Activo" : "Inactivo"}</span></div>)}</section><form className="panel compact-form" onSubmit={submit}><div className="panel-heading"><h2>Agregar usuario</h2></div><label>Nombre<input name="display_name" required /></label><label>Correo<input name="email" type="email" required /></label><label>Contraseña temporal<input name="password" type="password" minLength={12} required /></label><label>Rol<select name="role" defaultValue="viewer"><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="admin">Admin</option></select></label>{create.error && <p className="form-error">{create.error.message}</p>}<button className="button primary" disabled={create.isPending}>Guardar usuario</button></form></div></main>;
}

function PlanPage() {
  const query = useQuery({ queryKey: ["plan-usage"], queryFn: () => api<PlanUsage>("/v1/saas/usage") });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <ErrorState retry={() => query.refetch()} />;
  const data = query.data;
  return <main className="page"><PageHeading kicker="Suscripción SaaS" title="Plan y consumo" description="Límites operativos del periodo actual." /><section className="plan-card panel"><div><span className="badge success">{data.status}</span><h2>{data.plan_name}</h2><p>Renueva el {new Date(data.period_end).toLocaleDateString("es")}</p></div><Usage label="Cuentas" value={data.accounts} limit={data.accounts_limit} /><Usage label="Usuarios" value={data.users} limit={data.users_limit} /><Usage label="Mensajes este mes" value={data.messages_this_month} limit={data.messages_limit} /></section></main>;
}

function Usage({ label, value, limit }: { label: string; value: number; limit: number }) {
  const percent = Math.min(100, Math.round((value / Math.max(limit, 1)) * 100));
  return <div className="usage"><div><span>{label}</span><strong>{value.toLocaleString()} / {limit.toLocaleString()}</strong></div><progress value={percent} max="100" /><small>{percent}% utilizado</small></div>;
}

function Loading() { return <div className="loading" role="status"><span /><p>Cargando datos…</p></div>; }
function ErrorState({ retry }: { retry: () => void }) { return <div className="empty-state"><CircleAlert /><h2>No pudimos cargar esta vista</h2><p>Comprueba la conexión e inténtalo nuevamente.</p><button className="button" onClick={retry}>Reintentar</button></div>; }
function Empty({ icon: Icon, title, detail }: { icon: LucideIcon; title: string; detail: string }) { return <div className="empty-state"><Icon /><h2>{title}</h2><p>{detail}</p></div>; }

export default function App() {
  const authenticated = useSyncExternalStore(subscribeSession, hasSession, () => false);
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!authenticated) return;
    const expireIfNeeded = () => {
      if (!sessionExpired()) return false;
      clearSession();
      queryClient.clear();
      return true;
    };
    const recordActivity = () => {
      if (!expireIfNeeded()) recordSessionActivity();
    };
    if (expireIfNeeded()) return;
    const interval = window.setInterval(expireIfNeeded, 15_000);
    const events: (keyof WindowEventMap)[] = ["pointerdown", "keydown", "touchstart", "focus"];
    events.forEach((event) => window.addEventListener(event, recordActivity, { passive: true }));
    return () => {
      window.clearInterval(interval);
      events.forEach((event) => window.removeEventListener(event, recordActivity));
    };
  }, [authenticated, queryClient]);
  return <Routes><Route path="/login" element={authenticated ? <Navigate to="/" replace /> : <LoginManager />} /><Route path="/*" element={authenticated ? <Shell /> : <Navigate to="/login" replace />} /></Routes>;
}
