import { useEffect, useState } from "react";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import MessageView from "../components/MessageView";

export default function Alerts() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); api.alerts({ page: 1, page_size: 200 }).then((data) => setItems(data.items)).finally(() => setLoading(false)); };
  useEffect(load, []);
  const resolve = async (id, event) => { event.stopPropagation(); await api.resolveAlert(id); setItems((current) => current.filter((alert) => alert.id !== id)); };

  return (
    <div className="flex min-h-full p-3 md:p-6">
      <div className="card flex min-h-[680px] w-full overflow-hidden">
        <section className="flex w-full flex-col border-r border-slate-200/80 dark:border-white/10 md:w-[420px]">
          <div className="border-b border-slate-200/80 p-5 dark:border-white/10">
            <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-500/15"><ShieldAlert size={20} /></span><div><h2 className="font-bold text-slate-900 dark:text-white">Atención requerida</h2><p className="text-xs text-slate-500">{items.length} alertas abiertas</p></div></div>
          </div>
          <div className="flex-1 overflow-auto">
            {loading ? <div className="space-y-4 p-4">{[1,2,3,4].map((i) => <div key={i} className="space-y-2"><div className="skeleton h-4 w-1/3" /><div className="skeleton h-4 w-4/5" /><div className="skeleton h-3 w-1/2" /></div>)}</div> :
            items.length === 0 ? <div className="flex h-full flex-col items-center justify-center p-8 text-center"><span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15"><CheckCircle2 size={26} /></span><strong className="text-slate-800 dark:text-white">Todo está en orden</strong><p className="mt-1 text-sm text-slate-500">No tienes alertas críticas abiertas.</p></div> :
            items.map((alert) => <button key={alert.id} onClick={() => setSelected(alert.message.id)} className={`w-full border-b border-slate-100 p-4 text-left dark:border-white/5 ${selected === alert.message.id ? "bg-brand-50 dark:bg-brand-500/10" : "hover:bg-slate-50 dark:hover:bg-white/[.03]"}`}>
              <div className="mb-2 flex items-center gap-2"><span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-600 dark:bg-rose-500/15">{alert.service}</span><span className="text-[10px] font-semibold uppercase text-amber-500">{alert.keyword}</span><time className="ml-auto text-[11px] text-slate-400">{new Date(alert.created_at).toLocaleDateString()}</time></div>
              <strong className="block truncate text-sm text-slate-800 dark:text-white">{alert.message.subject}</strong><span className="block truncate text-xs text-slate-500">{alert.message.from_addr}</span>
              <span onClick={(event) => resolve(alert.id, event)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 hover:text-emerald-700"><CheckCircle2 size={14} /> Marcar resuelta</span>
            </button>)}
          </div>
        </section>
        <section className={`absolute inset-0 z-20 flex-1 bg-white dark:bg-slate-900 md:static md:z-auto ${selected ? "block" : "hidden md:block"}`}><MessageView id={selected} onClose={() => setSelected(null)} /></section>
      </div>
    </div>
  );
}
