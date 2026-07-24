import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, Ban, CheckCircle2, ChevronRight, Clock3, CreditCard,
  History, RefreshCw, ShieldX, X,
} from "lucide-react";
import MessageView from "../components/MessageView";
import { api } from "../lib/api";

const STATUS = {
  active: { label: "Activa", icon: CheckCircle2, badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" },
  warning: { label: "Actualizar", icon: AlertTriangle, badge: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300" },
  payment_failed: { label: "Pago rechazado", icon: CreditCard, badge: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" },
  suspended: { label: "Suspendida", icon: ShieldX, badge: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300" },
  cancelled: { label: "Cancelada", icon: Ban, badge: "bg-slate-200 text-slate-700 dark:bg-white/10 dark:text-slate-300" },
};

export default function Subscriptions() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState(null);
  const [messageId, setMessageId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (accountId) params.account_id = accountId;
      if (status) params.status = status;
      const [subscriptions, summary, linked] = await Promise.all([
        api.subscriptions(params), api.subscriptionStats(), api.accounts(),
      ]);
      setItems(subscriptions); setStats(summary); setAccounts(linked);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [accountId, status]); // eslint-disable-line react-hooks/exhaustive-deps

  const services = useMemo(() => new Set(items.map((item) => item.service)).size, [items]);

  const rebuild = async () => {
    setRebuilding(true); setNotice("");
    try {
      await api.rebuildSubscriptions();
      setNotice("Reclasificación iniciada. Los estados aparecerán en unos momentos.");
      window.setTimeout(load, 5000);
    } catch (error) { setNotice(error.message); }
    finally { setRebuilding(false); }
  };

  const openHistory = async (id) => {
    setSelected(await api.subscription(id));
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 md:p-7">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metric label="Servicios detectados" value={services} icon={CreditCard} tone="brand" />
        <Metric label="Activas" value={stats?.active ?? "—"} icon={CheckCircle2} tone="emerald" />
        <Metric label="Actualizar pago" value={stats?.warning ?? "—"} icon={AlertTriangle} tone="amber" />
        <Metric label="Pagos rechazados" value={stats?.payment_failed ?? "—"} icon={CreditCard} tone="rose" />
        <Metric label="Suspendidas" value={stats?.suspended ?? "—"} icon={ShieldX} tone="red" />
      </div>

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-200/80 p-4 dark:border-white/10 lg:flex-row lg:items-center">
          <div className="mr-auto"><h2 className="font-bold text-slate-900 dark:text-white">Monitor de suscripciones</h2><p className="text-xs text-slate-500">Último estado detectado para cada cuenta y servicio.</p></div>
          <select className="input lg:w-64" value={accountId} onChange={(e) => setAccountId(e.target.value)}><option value="">Todas las cuentas</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.email}</option>)}</select>
          <select className="input lg:w-48" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Todos los estados</option>{Object.entries(STATUS).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select>
          <button onClick={rebuild} disabled={rebuilding} className="btn-secondary"><RefreshCw size={16} className={rebuilding ? "animate-spin" : ""} /> Reclasificar</button>
        </div>
        {notice && <div className="border-b border-brand-100 bg-brand-50 px-4 py-2 text-xs text-brand-700 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-brand-100">{notice}</div>}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left">
            <thead className="bg-slate-50/80 text-[10px] uppercase tracking-wider text-slate-400 dark:bg-slate-950/30"><tr><th className="px-5 py-3">Cuenta</th><th className="px-5 py-3">Servicio</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Motivo</th><th className="px-5 py-3">Última detección</th><th className="px-5 py-3" /></tr></thead>
            <tbody className="divide-y divide-slate-100 dark:divide-white/5">
              {loading ? <TableSkeleton /> : items.length === 0 ? <tr><td colSpan="6" className="px-5 py-16 text-center"><CreditCard className="mx-auto mb-3 text-slate-300" size={30} /><strong className="block text-slate-700 dark:text-white">Aún no hay estados detectados</strong><span className="text-xs text-slate-500">Pulsa “Reclasificar” para analizar los correos existentes.</span></td></tr> :
              items.map((item) => {
                const info = STATUS[item.status] || STATUS.cancelled; const Icon = info.icon;
                return <tr key={item.id} className="hover:bg-slate-50/70 dark:hover:bg-white/[.03]"><td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300">{item.account_email}</td><td className="px-5 py-4 font-semibold text-slate-900 dark:text-white">{item.service}</td><td className="px-5 py-4"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${info.badge}`}><Icon size={13} />{info.label}</span></td><td className="px-5 py-4 text-sm text-slate-500">{item.reason || "Sin novedad"}</td><td className="px-5 py-4 text-xs text-slate-500">{new Date(item.updated_at).toLocaleString()}</td><td className="px-5 py-4"><button onClick={() => openHistory(item.id)} className="btn-secondary px-2.5" title="Ver historial"><History size={16} /></button></td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </section>
      {selected && <HistoryPanel item={selected} onClose={() => setSelected(null)} onMessage={setMessageId} />}
      {messageId && <div className="fixed inset-0 z-[60] bg-slate-950/50 p-3 backdrop-blur-sm md:p-8"><div className="mx-auto h-full max-w-5xl overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-slate-900"><MessageView id={messageId} onClose={() => setMessageId(null)} /></div></div>}
    </div>
  );
}

function Metric({ label, value, icon: Icon, tone }) {
  const colors = { brand: "bg-brand-100 text-brand-600 dark:bg-brand-500/15", emerald: "bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15", amber: "bg-amber-100 text-amber-600 dark:bg-amber-500/15", rose: "bg-rose-100 text-rose-600 dark:bg-rose-500/15", red: "bg-red-100 text-red-600 dark:bg-red-500/15" };
  return <div className="card flex items-center gap-3 p-4"><span className={`flex h-10 w-10 items-center justify-center rounded-xl ${colors[tone]}`}><Icon size={19} /></span><span><strong className="block text-xl text-slate-950 dark:text-white">{value}</strong><small className="text-slate-500">{label}</small></span></div>;
}

function HistoryPanel({ item, onClose, onMessage }) {
  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40 backdrop-blur-sm" onMouseDown={onClose}><aside onMouseDown={(e) => e.stopPropagation()} className="h-full w-full max-w-lg animate-fade-in overflow-y-auto bg-white p-6 shadow-2xl dark:bg-slate-900"><div className="flex items-start"><div><p className="text-sm font-semibold text-brand-600">{item.service}</p><h2 className="text-xl font-bold text-slate-950 dark:text-white">{item.account_email}</h2></div><button onClick={onClose} className="btn-secondary ml-auto px-2.5"><X size={18} /></button></div><div className="mt-8"><h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-slate-800 dark:text-white"><History size={17} /> Historial de estados</h3><div className="space-y-1">{item.events.map((event, index) => { const info = STATUS[event.status] || STATUS.cancelled; const Icon = info.icon; return <div key={event.id} className="relative flex gap-3 pb-6"><div className={`z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${info.badge}`}><Icon size={15} /></div>{index < item.events.length - 1 && <div className="absolute left-[17px] top-9 h-full w-px bg-slate-200 dark:bg-white/10" />}<div className="min-w-0 flex-1"><strong className="text-sm text-slate-800 dark:text-white">{info.label}</strong><p className="text-xs text-slate-500">{event.reason}</p><time className="mt-1 flex items-center gap-1 text-[11px] text-slate-400"><Clock3 size={12} />{new Date(event.detected_at).toLocaleString()}</time>{event.message_id && <button onClick={() => onMessage(event.message_id)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-600">Abrir correo <ChevronRight size={13} /></button>}</div></div>; })}</div></div></aside></div>;
}

function TableSkeleton() { return <>{[1,2,3,4].map((row) => <tr key={row}>{[1,2,3,4,5,6].map((cell) => <td key={cell} className="px-5 py-5"><div className="skeleton h-3 w-full" /></td>)}</tr>)}</>; }
