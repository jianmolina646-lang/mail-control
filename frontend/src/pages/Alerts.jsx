import { useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import MessageView from "../components/MessageView";
import { EmptyState, LoadingBlock, Notice, PageHeader, StatusBadge } from "../components/ui";

export default function Alerts() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = () => {
    setLoading(true); setError("");
    api.alerts({ page: 1, page_size: 200 }).then((data) => setItems(data.items)).catch((err) => setError(err.message)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const resolve = async (id, event) => {
    event.stopPropagation(); setError(""); setSuccess("");
    try {
      await api.resolveAlert(id);
      setItems((current) => current.filter((alert) => alert.id !== id));
      setSuccess("La alerta se marcó como resuelta.");
    } catch (err) { setError(err.message); }
  };

  return <div className="flex min-h-full flex-col gap-5 p-4 md:p-7">
    <PageHeader title="Alertas" description="Incidencias de pago, suspensión o autenticación que requieren revisión." actions={<button onClick={load} className="btn-secondary"><RefreshCw size={16} /> Actualizar</button>} />
    {error && <Notice tone="error">{error}</Notice>}
    {success && <Notice tone="success">{success}</Notice>}
    <div className="panel flex min-h-[640px] flex-1 overflow-hidden">
      <section className="flex w-full flex-col border-r border-slate-200 dark:border-slate-800 md:w-[420px]">
        <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800"><h2 className="text-sm font-semibold text-slate-900 dark:text-white">Abiertas ({items.length})</h2></div>
        <div className="flex-1 overflow-auto">
          {loading ? <LoadingBlock /> : !items.length ? <EmptyState icon={CheckCircle2} title="No hay alertas abiertas" description="No se detectaron pagos rechazados, suspensiones ni cuentas que requieran atención." /> : items.map((alert) => <button key={alert.id} onClick={() => setSelected(alert.message.id)} className={`w-full border-b border-slate-100 p-4 text-left dark:border-slate-800 ${selected === alert.message.id ? "bg-brand-50 dark:bg-brand-950/30" : "hover:bg-slate-50 dark:hover:bg-slate-800/50"}`}>
            <span className="mb-2 flex items-center gap-2"><StatusBadge status={alert.severity}>{alert.severity === "critical" ? "Crítica" : "Advertencia"}</StatusBadge><span className="text-xs font-medium text-slate-600 dark:text-slate-300">{alert.service}</span><time className="ml-auto text-[11px] text-slate-400">{new Date(alert.created_at).toLocaleDateString()}</time></span>
            <strong className="block truncate text-sm font-medium text-slate-900 dark:text-white">{alert.message.subject}</strong>
            <span className="mt-1 block truncate text-xs text-slate-500">{alert.keyword} · {alert.message.from_addr}</span>
            <span onClick={(event) => resolve(alert.id, event)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700"><CheckCircle2 size={14} /> Marcar como resuelta</span>
          </button>)}
        </div>
      </section>
      <section className={`absolute inset-0 z-20 flex-1 bg-white dark:bg-slate-900 md:static md:z-auto ${selected ? "block" : "hidden md:block"}`}><MessageView id={selected} onClose={() => setSelected(null)} /></section>
    </div>
  </div>;
}
