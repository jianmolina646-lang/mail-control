import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, Ban, CheckCircle2, ChevronRight, Clock3, CreditCard,
  History, MoreHorizontal, RefreshCw, Search, ShieldX, SlidersHorizontal, X,
} from "lucide-react";
import MessageView from "../components/MessageView";
import { api } from "../lib/api";
import { EmptyState, Notice } from "../components/ui";

const STATUS = {
  active: { label: "Activa", icon: CheckCircle2, color: "#22c55e", className: "is-active" },
  warning: { label: "Por renovar", icon: AlertTriangle, color: "#f59e0b", className: "is-warning" },
  payment_failed: { label: "Pago rechazado", icon: CreditCard, color: "#ef4444", className: "is-danger" },
  suspended: { label: "Suspendida", icon: ShieldX, color: "#6366f1", className: "is-suspended" },
  cancelled: { label: "Cancelada", icon: Ban, color: "#64748b", className: "is-neutral" },
};

export default function Subscriptions() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [messageId, setMessageId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const params = {};
      if (accountId) params.account_id = accountId;
      if (status) params.status = status;
      const [subscriptions, summary, linked] = await Promise.all([
        api.subscriptions(params), api.subscriptionStats(), api.accounts(),
      ]);
      setItems(subscriptions); setStats(summary); setAccounts(linked);
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [accountId, status]); // eslint-disable-line react-hooks/exhaustive-deps

  const serviceCounts = useMemo(() => {
    const counts = new Map();
    items.forEach((item) => counts.set(item.service, (counts.get(item.service) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [items]);
  const services = serviceCounts.length;
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) => `${item.service} ${item.account_email} ${item.reason || ""}`.toLowerCase().includes(normalized));
  }, [items, query]);
  const totalStates = Math.max(1, (stats?.active || 0) + (stats?.warning || 0) + (stats?.payment_failed || 0) + (stats?.suspended || 0));

  const rebuild = async () => {
    setRebuilding(true); setNotice("");
    try {
      await api.rebuildSubscriptions();
      setNotice("Reclasificación iniciada. Los estados aparecerán en unos momentos.");
      window.setTimeout(load, 5000);
    } catch (err) { setNotice(err.message); } finally { setRebuilding(false); }
  };
  const openHistory = async (id) => setSelected(await api.subscription(id));

  const metrics = [
    { label: "Servicios detectados", value: services, icon: CreditCard, tone: "violet", detail: `${items.length} estados registrados` },
    { label: "Servicios activos", value: stats?.active ?? "—", icon: CheckCircle2, tone: "green", detail: `${Math.round(((stats?.active || 0) / totalStates) * 100)}% del total` },
    { label: "Por renovar", value: stats?.warning ?? "—", icon: AlertTriangle, tone: "amber", detail: "Requieren atención" },
    { label: "Pago rechazado", value: stats?.payment_failed ?? "—", icon: CreditCard, tone: "red", detail: "Incidencias detectadas" },
    { label: "Suspendidas", value: stats?.suspended ?? "—", icon: ShieldX, tone: "blue", detail: "Sin servicio activo" },
  ];

  return (
    <div className="subscriptions-page">
      <header className="subscriptions-hero">
        <div>
          <span>SUPERVISIÓN COMERCIAL</span>
          <h1>Gestión de suscripciones</h1>
          <p>Administra y supervisa todos los servicios detectados en tus cuentas de correo.</p>
        </div>
        <button onClick={rebuild} disabled={rebuilding} className="subscriptions-primary">
          <RefreshCw size={15} className={rebuilding ? "animate-spin" : ""} />
          {rebuilding ? "Reclasificando…" : "Reclasificar correos"}
        </button>
      </header>

      {error && <Notice tone="error">{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}

      <section className="subscription-metrics">
        {metrics.map((metric) => <Metric key={metric.label} {...metric} />)}
      </section>

      <div className="subscriptions-layout">
        <section className="subscriptions-main">
          <div className="subscription-filters">
            <label className="subscription-search">
              <Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar por servicio, cuenta o motivo…" />
            </label>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">Todas las cuentas</option>
              {accounts.map((account) => <option key={account.id} value={account.id}>{account.email}</option>)}
            </select>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Todos los estados</option>
              {Object.entries(STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
            </select>
            <span className="subscription-filter-count"><SlidersHorizontal size={14} />{filtered.length}</span>
          </div>

          <div className="subscription-table-card">
            <div className="subscription-table-title"><div><strong>Servicios y suscripciones ({filtered.length})</strong><span>Último estado detectado por cuenta y servicio.</span></div></div>
            <div className="subscription-table-wrap">
              <table>
                <thead><tr><th>Servicio</th><th>Cuenta</th><th>Estado</th><th>Motivo</th><th>Última actividad</th><th>Acciones</th></tr></thead>
                <tbody>
                  {loading ? <TableSkeleton /> : filtered.length === 0 ? (
                    <tr><td colSpan="6"><EmptyState icon={CreditCard} title="No hay estados detectados" description="Reclasifica los correos para construir el estado de cada suscripción." /></td></tr>
                  ) : filtered.map((item) => {
                    const info = STATUS[item.status] || STATUS.cancelled;
                    return (
                      <tr key={item.id}>
                        <td><div className="subscription-service"><ServiceMark name={item.service} /><strong>{item.service}</strong></div></td>
                        <td><span className="subscription-email">{item.account_email}</span></td>
                        <td><StatusPill info={info} /></td>
                        <td><span className="subscription-reason">{item.reason || "Sin novedad"}</span></td>
                        <td><time>{new Date(item.updated_at).toLocaleString()}</time></td>
                        <td><button onClick={() => openHistory(item.id)} className="subscription-more" title="Ver historial"><MoreHorizontal size={16} /></button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <aside className="subscriptions-summary">
          <SummaryDonut stats={stats} total={totalStates} />
          <div className="summary-card">
            <h3>Servicios más detectados</h3>
            <div className="summary-services">
              {serviceCounts.slice(0, 5).map(([name, count], index) => (
                <div key={name}><span><ServiceMark name={name} />{name}</span><b>{count}</b><i><em style={{ width: `${(count / Math.max(1, serviceCounts[0]?.[1])) * 100}%` }} /></i></div>
              ))}
              {!serviceCounts.length && <p>Sin servicios detectados todavía.</p>}
            </div>
          </div>
          <div className="summary-card">
            <h3>Acciones rápidas</h3>
            <button onClick={rebuild} disabled={rebuilding}><RefreshCw size={14} />Sincronizar estados</button>
            <button onClick={() => setStatus("warning")}><AlertTriangle size={14} />Ver por renovar</button>
            <button onClick={() => setStatus("suspended")}><ShieldX size={14} />Ver suspendidas</button>
          </div>
        </aside>
      </div>

      {selected && <HistoryPanel item={selected} onClose={() => setSelected(null)} onMessage={setMessageId} />}
      {messageId && <div className="fixed inset-0 z-[60] bg-slate-950/50 p-3 md:p-8"><div className="mx-auto h-full max-w-5xl overflow-hidden border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900"><MessageView id={messageId} onClose={() => setMessageId(null)} /></div></div>}
    </div>
  );
}

function Metric({ label, value, icon: Icon, tone, detail }) {
  const bars = [28, 44, 34, 58, 43, 67, 53, 74, 61, 81];
  return <article className={`subscription-metric tone-${tone}`}><div><span><Icon size={15} /></span><small>{label}</small></div><strong>{value}</strong><p>{detail}</p><div className="subscription-spark">{bars.map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div></article>;
}

function ServiceMark({ name }) {
  return <span className="subscription-service-mark">{(name || "?").slice(0, 1).toUpperCase()}</span>;
}

function StatusPill({ info }) {
  const Icon = info.icon;
  return <span className={`subscription-status ${info.className}`}><Icon size={11} />{info.label}</span>;
}

function SummaryDonut({ stats, total }) {
  const active = Math.round(((stats?.active || 0) / total) * 100);
  const warning = Math.round(((stats?.warning || 0) / total) * 100);
  const failed = Math.round(((stats?.payment_failed || 0) / total) * 100);
  const suspended = Math.max(0, 100 - active - warning - failed);
  const gradient = `conic-gradient(#22c55e 0 ${active}%, #f59e0b ${active}% ${active + warning}%, #ef4444 ${active + warning}% ${active + warning + failed}%, #6366f1 ${active + warning + failed}% ${active + warning + failed + suspended}%)`;
  return <div className="summary-card"><h3>Resumen de suscripciones</h3><div className="summary-donut"><div style={{ background: gradient }}><span><b>{total === 1 && !stats ? "—" : total}</b><small>Total</small></span></div><ul>{[["Activas", stats?.active || 0, "#22c55e"],["Por renovar", stats?.warning || 0, "#f59e0b"],["Rechazadas", stats?.payment_failed || 0, "#ef4444"],["Suspendidas", stats?.suspended || 0, "#6366f1"]].map(([label,value,color])=><li key={label}><i style={{background:color}} />{label}<b>{value}</b></li>)}</ul></div></div>;
}

function HistoryPanel({ item, onClose, onMessage }) {
  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40 backdrop-blur-sm" onMouseDown={onClose}><aside onMouseDown={(e) => e.stopPropagation()} className="h-full w-full max-w-lg animate-fade-in overflow-y-auto bg-white p-6 shadow-2xl dark:bg-slate-900"><div className="flex items-start"><div><p className="text-sm font-semibold text-brand-600">{item.service}</p><h2 className="text-xl font-bold text-slate-950 dark:text-white">{item.account_email}</h2></div><button onClick={onClose} className="btn-secondary ml-auto px-2.5"><X size={18} /></button></div><div className="mt-8"><h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-slate-800 dark:text-white"><History size={17} /> Historial de estados</h3><div className="space-y-1">{item.events.map((event, index) => { const info = STATUS[event.status] || STATUS.cancelled; const Icon = info.icon; return <div key={event.id} className="relative flex gap-3 pb-6"><div className={`z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full subscription-status ${info.className}`}><Icon size={15} /></div>{index < item.events.length - 1 && <div className="absolute left-[17px] top-9 h-full w-px bg-slate-200 dark:bg-white/10" />}<div className="min-w-0 flex-1"><strong className="text-sm text-slate-800 dark:text-white">{info.label}</strong><p className="text-xs text-slate-500">{event.reason}</p><time className="mt-1 flex items-center gap-1 text-[11px] text-slate-400"><Clock3 size={12} />{new Date(event.detected_at).toLocaleString()}</time>{event.message_id && <button onClick={() => onMessage(event.message_id)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-600">Abrir correo <ChevronRight size={13} /></button>}</div></div>; })}</div></div></aside></div>;
}

function TableSkeleton() {
  return <>{[1,2,3,4,5].map((row) => <tr key={row}>{[1,2,3,4,5,6].map((cell) => <td key={cell}><div className="skeleton h-3 w-full" /></td>)}</tr>)}</>;
}
