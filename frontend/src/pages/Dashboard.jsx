import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowRight, CheckCircle2, CreditCard,
  Inbox, MailCheck, RefreshCw, UsersRound,
} from "lucide-react";
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
    ])
      .then(([stats, accounts, alerts, messages, subscriptions]) => {
        setData({ stats, accounts, alerts: alerts.items, messages: messages.items, subscriptions });
      })
      .catch((err) => setError(err.message));
  };
  useEffect(load, []);

  const subscriptionRisk = data
    ? data.subscriptions.warning + data.subscriptions.payment_failed + data.subscriptions.suspended
    : 0;

  return <div className="dashboard-page mx-auto max-w-[1500px] space-y-6 p-4 md:p-7">
    <PageHeader
      eyebrow="Centro operativo"
      title="Resumen de actividad"
      description="Una lectura clara del correo, las cuentas conectadas y las suscripciones que necesitan seguimiento."
      actions={<button onClick={load} className="btn-secondary"><RefreshCw size={16} /> Actualizar datos</button>}
    />
    {error && <Notice tone="error">{error}</Notice>}
    {!data ? <div className="panel"><LoadingBlock rows={5} /></div> : <>
      <section aria-label="Indicadores principales" className="metric-grid">
        <Indicator icon={UsersRound} label="Cuentas conectadas" value={data.stats.accounts_total} detail={`${data.stats.accounts_ok} sincronizando correctamente`} />
        <Indicator icon={MailCheck} label="Mensajes procesados" value={data.stats.messages_total} detail="Disponibles en la bandeja" />
        <Indicator icon={AlertTriangle} label="Alertas abiertas" value={data.stats.alerts_open} detail={data.stats.alerts_open ? "Requieren revisión" : "Operación sin incidencias"} critical={data.stats.alerts_open > 0} />
        <Indicator icon={CreditCard} label="Suscripciones en riesgo" value={subscriptionRisk} detail={`${data.subscriptions.active} activas confirmadas`} critical={data.subscriptions.payment_failed + data.subscriptions.suspended > 0} />
      </section>

      <div className="dashboard-main-grid">
        <section className="panel dashboard-attention">
          <SectionTitle icon={Activity} title="Necesita atención" subtitle="Prioridades detectadas en tus correos" link="/alertas" linkLabel="Ver alertas" />
          {data.alerts.length === 0
            ? <EmptyState icon={CheckCircle2} title="No hay alertas abiertas" description="Las cuentas están sincronizando sin incidencias críticas detectadas." />
            : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.alerts.map((alert) =>
              <Link key={alert.id} to="/alertas" className="activity-row">
                <span className="activity-row-icon is-warning"><AlertTriangle size={17} /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><strong className="truncate text-sm text-slate-900 dark:text-white">{alert.service}</strong><StatusBadge status={alert.severity}>{alert.severity === "critical" ? "Crítica" : "Advertencia"}</StatusBadge></div>
                  <p className="mt-1 truncate text-sm text-slate-600 dark:text-slate-300">{alert.message.subject}</p>
                  <span className="mt-1 block text-xs text-slate-400">{new Date(alert.created_at).toLocaleString()}</span>
                </div><ArrowRight size={16} className="mt-1 text-slate-500" />
              </Link>)}</div>}
        </section>

        <section className="panel">
          <SectionTitle icon={UsersRound} title="Estado de cuentas" subtitle="Salud de sincronización" link="/cuentas" linkLabel="Gestionar" />
          {data.accounts.length === 0
            ? <EmptyState icon={UsersRound} title="No hay cuentas conectadas" description="Conecta una cuenta para comenzar a sincronizar mensajes." action={<Link to="/cuentas" className="btn-primary">Conectar cuenta</Link>} />
            : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.accounts.slice(0, 6).map((account) =>
              <div key={account.id} className="account-health-row">
                <span className={`account-provider ${account.last_status === "ok" ? "is-ok" : account.last_status === "error" ? "is-error" : ""}`}>{account.email?.[0]?.toUpperCase()}</span>
                <div className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">{account.email}</span><span className="text-xs capitalize text-slate-500">{account.provider}</span></div>
                <StatusBadge status={account.last_status}>{account.last_status === "ok" ? "Conectada" : account.last_status === "error" ? "Error" : "Pendiente"}</StatusBadge>
              </div>)}</div>}
        </section>
      </div>

      <section className="panel dashboard-activity">
        <SectionTitle icon={Inbox} title="Actividad reciente" subtitle="Últimos mensajes recibidos" link="/bandeja" linkLabel="Abrir bandeja" />
        {data.messages.length === 0
          ? <EmptyState icon={Inbox} title="Todavía no hay mensajes" description="La actividad aparecerá cuando termine la primera sincronización de tus cuentas." />
          : <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.messages.map((message) =>
            <Link key={message.id} to="/bandeja" className="message-activity-row">
              <span className="message-avatar">{(message.from_name || message.from_addr || "M")[0].toUpperCase()}</span>
              <span className="min-w-0"><strong>{message.from_name || message.from_addr}</strong><small>{message.subject || "(sin asunto)"}</small></span>
              <time>{new Date(message.received_at).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</time>
              <ArrowRight size={15} />
            </Link>)}</div>}
      </section>
    </>}
  </div>;
}

function Indicator({ icon: Icon, label, value, detail, critical }) {
  return <article className={`metric-card ${critical ? "is-critical" : ""}`}>
    <div className="metric-card-head"><span className="metric-icon"><Icon size={16} /></span><span className="metric-label">{label}</span><span className="metric-kicker">{critical ? "Atención" : "En línea"}</span></div>
    <div className="metric-card-body"><strong>{value}</strong></div>
    <p>{detail}</p>
  </article>;
}

function SectionTitle({ icon: Icon, title, subtitle, link, linkLabel }) {
  return <div className="section-title"><span className="section-title-icon"><Icon size={16} /></span><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><Link to={link}>{linkLabel}<ArrowRight size={13} /></Link></div>;
}
