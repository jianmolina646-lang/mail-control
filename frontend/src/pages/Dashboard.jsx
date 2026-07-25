import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, Inbox, RefreshCw, UsersRound } from "lucide-react";
import { api } from "../lib/api";
import { EmptyState, LoadingBlock, Notice, PageHeader, StatusBadge } from "../components/ui";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = () => {
    setError("");
    Promise.all([
      api.stats(), api.accounts(), api.alerts({ page: 1, page_size: 5 }),
      api.messages({ page: 1, page_size: 6 }), api.subscriptionStats(),
    ]).then(([stats, accounts, alerts, messages, subscriptions]) => setData({ stats, accounts, alerts: alerts.items, messages: messages.items, subscriptions })).catch((err) => setError(err.message));
  };
  useEffect(load, []);

  return <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
    <PageHeader title="Resumen operativo" description="Estado actual de tus cuentas, suscripciones y mensajes que requieren atención." actions={<button onClick={load} className="btn-secondary"><RefreshCw size={16} /> Actualizar</button>} />
    {error && <Notice tone="error">{error}</Notice>}
    {!data ? <div className="panel"><LoadingBlock rows={5} /></div> : <>
      <section aria-label="Indicadores principales" className="grid border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2 lg:grid-cols-4">
        <Indicator label="Cuentas conectadas" value={data.stats.accounts_total} detail={`${data.stats.accounts_ok} sincronizando correctamente`} />
        <Indicator label="Mensajes almacenados" value={data.stats.messages_total} detail="Disponibles en la bandeja" />
        <Indicator label="Alertas abiertas" value={data.stats.alerts_open} detail={data.stats.alerts_open ? "Requieren revisión" : "Sin incidencias críticas"} critical={data.stats.alerts_open > 0} />
        <Indicator label="Suscripciones con problema" value={data.subscriptions.warning + data.subscriptions.payment_failed + data.subscriptions.suspended} detail={`${data.subscriptions.active} activas confirmadas`} critical={data.subscriptions.payment_failed + data.subscriptions.suspended > 0} />
      </section>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(300px,.6fr)]">
        <section className="panel">
          <SectionTitle title="Necesita atención" link="/alertas" linkLabel="Ver alertas" />
          {data.alerts.length === 0 ? <EmptyState icon={CheckCircle2} title="No hay alertas abiertas" description="Las cuentas están sincronizando sin incidencias críticas detectadas." /> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.alerts.map((alert) => <Link key={alert.id} to="/alertas" className="flex items-start gap-3 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"><AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" /><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><strong className="truncate text-sm text-slate-900 dark:text-white">{alert.service}</strong><StatusBadge status={alert.severity}>{alert.severity === "critical" ? "Crítica" : "Advertencia"}</StatusBadge></div><p className="mt-1 truncate text-sm text-slate-600 dark:text-slate-300">{alert.message.subject}</p><span className="mt-1 block text-xs text-slate-400">{new Date(alert.created_at).toLocaleString()}</span></div><ArrowRight size={16} className="mt-1 text-slate-400" /></Link>)}</div>}
        </section>
        <section className="panel">
          <SectionTitle title="Estado de cuentas" link="/cuentas" linkLabel="Gestionar" />
          {data.accounts.length === 0 ? <EmptyState icon={UsersRound} title="No hay cuentas conectadas" description="Conecta una cuenta para comenzar a sincronizar mensajes." action={<Link to="/cuentas" className="btn-primary">Conectar cuenta</Link>} /> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.accounts.slice(0, 6).map((account) => <div key={account.id} className="flex items-center gap-3 px-4 py-3"><span className={`h-2 w-2 rounded-full ${account.last_status === "ok" ? "bg-emerald-500" : account.last_status === "error" ? "bg-rose-500" : "bg-slate-300"}`} /><div className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">{account.email}</span><span className="text-xs text-slate-400">{account.provider}</span></div><StatusBadge status={account.last_status}>{account.last_status === "ok" ? "Conectada" : account.last_status === "error" ? "Error" : "Pendiente"}</StatusBadge></div>)}</div>}
        </section>
      </div>
      <section className="panel">
        <SectionTitle title="Actividad reciente" link="/bandeja" linkLabel="Abrir bandeja" />
        {data.messages.length === 0 ? <EmptyState icon={Inbox} title="Todavía no hay mensajes" description="La actividad aparecerá cuando termine la primera sincronización de tus cuentas." /> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.messages.map((message) => <Link key={message.id} to="/bandeja" className="grid gap-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 sm:grid-cols-[180px_minmax(0,1fr)_auto] sm:items-center"><span className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{message.from_name || message.from_addr}</span><span className="truncate text-sm text-slate-600 dark:text-slate-300">{message.subject || "(sin asunto)"}</span><time className="text-xs text-slate-400">{new Date(message.received_at).toLocaleDateString()}</time></Link>)}</div>}
      </section>
    </>}
  </div>;
}

function Indicator({ label, value, detail, critical }) {
  return <div className="border-b border-slate-200 p-4 last:border-b-0 dark:border-slate-800 sm:border-b-0 sm:border-r sm:last:border-r-0"><span className="text-xs font-medium text-slate-500">{label}</span><div className={`mt-1 text-2xl font-semibold tabular-nums ${critical ? "text-rose-700 dark:text-rose-400" : "text-slate-950 dark:text-white"}`}>{value}</div><p className="mt-1 text-xs text-slate-400">{detail}</p></div>;
}
function SectionTitle({ title, link, linkLabel }) {
  return <div className="flex items-center border-b border-slate-200 px-4 py-3 dark:border-slate-800"><h2 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h2><Link to={link} className="ml-auto text-xs font-medium text-brand-600 hover:text-brand-700">{linkLabel}</Link></div>;
}
