import { useCallback, useEffect, useRef, useState } from "react";
import { FixedSizeList as List } from "react-window";
import { AlertTriangle, Inbox as InboxIcon, Mail, RefreshCw, Search, UsersRound } from "lucide-react";
import { useOutletContext } from "react-router-dom";
import MessageView from "../components/MessageView";
import { api } from "../lib/api";

const PAGE_SIZE = 100;
const ROW_HEIGHT = 82;

export default function Inbox() {
  const { stats } = useOutletContext();
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const loadingRef = useRef(false);
  const requestRef = useRef(0);

  const load = useCallback(async (nextPage, query, replace = false) => {
    if (loadingRef.current && !replace) return;
    const requestId = ++requestRef.current;
    loadingRef.current = true;
    setLoading(true);
    setError("");
    try {
      const data = await api.messages({ page: nextPage, page_size: PAGE_SIZE, account_id: selectedAccount || undefined, q: query ?? q });
      if (requestId !== requestRef.current) return;
      setTotal(data.total);
      setItems((previous) => replace ? data.items : [...previous, ...data.items]);
      setPage(nextPage);
    } catch (err) {
      if (requestId === requestRef.current) setError(err.message);
    } finally {
      if (requestId === requestRef.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
  }, [q, selectedAccount]);

  const reset = useCallback((query = q) => {
    requestRef.current += 1;
    loadingRef.current = false;
    setItems([]);
    setPage(1);
    load(1, query, true);
  }, [load, q]);

  useEffect(() => { api.accounts().then(setAccounts).catch((err) => setError(err.message)); }, []);
  useEffect(() => { setSelected(null); reset(""); }, [selectedAccount]); // eslint-disable-line react-hooks/exhaustive-deps

  const syncSelected = async () => {
    setSyncing(true);
    setError("");
    try {
      const targets = selectedAccount ? accounts.filter((a) => String(a.id) === selectedAccount) : accounts.filter((a) => a.is_enabled);
      await Promise.all(targets.map((a) => api.syncAccount(a.id)));
      window.setTimeout(() => reset(q), 3000);
    } catch (err) { setError(err.message); } finally { setSyncing(false); }
  };

  const accountLabel = accounts.find((a) => String(a.id) === selectedAccount)?.email || "Todas las cuentas";

  const Row = ({ index, style }) => {
    const message = items[index];
    if (!message) return null;
    const active = selected === message.id;
    return (
      <button type="button" style={style} onClick={() => setSelected(message.id)}
        className={`group w-full border-b border-slate-100 px-4 text-left dark:border-white/5 ${active ? "bg-brand-50 dark:bg-brand-500/10" : "hover:bg-slate-50 dark:hover:bg-white/[.03]"}`}>
        <div className="flex h-full items-center gap-3">
          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${message.is_alert ? "bg-rose-100 text-rose-600 dark:bg-rose-500/15" : "bg-slate-100 text-slate-500 dark:bg-white/5"}`}>
            {message.is_alert ? <AlertTriangle size={18} /> : initials(message.from_name || message.from_addr)}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2"><strong className="truncate text-sm text-slate-800 dark:text-slate-100">{message.from_name || message.from_addr}</strong><time className="ml-auto shrink-0 text-[11px] text-slate-400">{formatMessageDate(message.received_at)}</time></span>
            <span className="mt-1 block truncate text-xs font-medium text-slate-600 dark:text-slate-300">{message.subject || "(sin asunto)"}</span>
            <span className="mt-0.5 block truncate text-xs text-slate-400">{message.snippet}</span>
          </span>
        </div>
      </button>
    );
  };

  return (
    <div className="flex min-h-full flex-col p-3 md:p-6">
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Summary icon={Mail} label="Correos almacenados" value={total} tone="brand" />
        <Summary icon={UsersRound} label="Cuentas vinculadas" value={stats?.accounts_total ?? accounts.length} tone="sky" />
        <Summary icon={InboxIcon} label="Cuentas activas" value={stats?.accounts_ok ?? "—"} tone="emerald" />
        <Summary icon={AlertTriangle} label="Alertas abiertas" value={stats?.alerts_open ?? "—"} tone="rose" />
      </div>
      <div className="card flex min-h-[620px] flex-1 overflow-hidden">
        <aside className="hidden w-60 shrink-0 border-r border-slate-200/80 bg-slate-50/60 dark:border-white/10 dark:bg-slate-950/30 xl:block">
          <div className="p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Cuentas</p></div>
          <AccountButton active={selectedAccount === ""} label="Todas las cuentas" detail={`${accounts.length} vinculadas`} onClick={() => setSelectedAccount("")} />
          {accounts.map((a) => <AccountButton key={a.id} active={selectedAccount === String(a.id)} label={a.email} detail={`${a.provider} · ${statusLabel(a.last_status)}`} onClick={() => setSelectedAccount(String(a.id))} />)}
        </aside>
        <section className="flex min-w-0 w-full flex-col border-r border-slate-200/80 dark:border-white/10 md:w-[400px] lg:w-[470px]">
          <div className="space-y-3 border-b border-slate-200/80 p-4 dark:border-white/10">
            <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)} className="input xl:hidden">
              <option value="">Todas las cuentas</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.email}</option>)}
            </select>
            <div className="flex gap-2">
              <label className="relative min-w-0 flex-1"><Search className="absolute left-3 top-2.5 text-slate-400" size={17} /><input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && reset(q)} placeholder="Buscar correos…" className="input pl-10" /></label>
              <button onClick={syncSelected} disabled={syncing} className="btn-secondary px-3" title={`Sincronizar ${accountLabel}`}><RefreshCw size={18} className={syncing ? "animate-spin" : ""} /></button>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-500"><strong className="max-w-[70%] truncate text-slate-700 dark:text-slate-300">{accountLabel}</strong><span>{total} correos</span></div>
          </div>
          {error && <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600 dark:border-rose-500/20 dark:bg-rose-500/10">{error}</div>}
          <div className="min-h-0 flex-1">
            {loading && items.length === 0 ? <MessageSkeleton /> : items.length === 0 ? <EmptyInbox /> :
              <AutoList itemCount={items.length} Row={Row} onScroll={({ scrollOffset }) => {
                if (scrollOffset + 600 >= items.length * ROW_HEIGHT - 400 && items.length < total && !loadingRef.current) load(page + 1);
              }} />}
          </div>
        </section>
        <section className={`absolute inset-0 z-20 min-w-0 flex-1 bg-white dark:bg-slate-900 md:static md:z-auto ${selected ? "block" : "hidden md:block"}`}><MessageView id={selected} onClose={() => setSelected(null)} /></section>
      </div>
    </div>
  );
}

function Summary({ icon: Icon, label, value, tone }) {
  const colors = { brand: "bg-brand-100 text-brand-600 dark:bg-brand-500/15", sky: "bg-sky-100 text-sky-600 dark:bg-sky-500/15", emerald: "bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15", rose: "bg-rose-100 text-rose-600 dark:bg-rose-500/15" };
  return <div className="card flex items-center gap-3 p-4"><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${colors[tone]}`}><Icon size={19} /></span><span><strong className="block text-xl text-slate-950 dark:text-white">{value}</strong><small className="text-slate-500">{label}</small></span></div>;
}
function AccountButton({ active, label, detail, onClick }) {
  return <button onClick={onClick} className={`mx-2 mb-1 w-[calc(100%-1rem)] rounded-xl px-3 py-2.5 text-left ${active ? "bg-white text-brand-700 shadow-sm dark:bg-white/10 dark:text-brand-100" : "text-slate-600 hover:bg-white dark:text-slate-400 dark:hover:bg-white/5"}`}><span className="block truncate text-sm font-semibold">{label}</span><span className="mt-0.5 block truncate text-[11px] text-slate-400">{detail}</span></button>;
}
function MessageSkeleton() { return <div className="space-y-5 p-4">{[1,2,3,4,5].map((i) => <div key={i} className="flex gap-3"><div className="skeleton h-10 w-10 shrink-0" /><div className="flex-1 space-y-2"><div className="skeleton h-3 w-2/5" /><div className="skeleton h-3 w-4/5" /><div className="skeleton h-2.5 w-full" /></div></div>)}</div>; }
function EmptyInbox() { return <div className="flex h-full flex-col items-center justify-center p-8 text-center"><span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10"><InboxIcon size={25} /></span><strong className="text-slate-800 dark:text-white">Bandeja vacía</strong><p className="mt-1 max-w-xs text-xs text-slate-500">Sincroniza la cuenta o cambia los filtros para encontrar mensajes.</p></div>; }
function AutoList({ itemCount, onScroll, Row }) {
  const ref = useRef(null); const [height, setHeight] = useState(600);
  useEffect(() => { const update = () => ref.current && setHeight(ref.current.clientHeight); update(); const observer = new ResizeObserver(update); if (ref.current) observer.observe(ref.current); return () => observer.disconnect(); }, []);
  return <div ref={ref} className="h-full"><List height={height} itemCount={itemCount} itemSize={ROW_HEIGHT} width="100%" onScroll={onScroll}>{Row}</List></div>;
}
function initials(value = "") { return value.split(/[\s@]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "M"; }
function formatMessageDate(value) { const date = new Date(value); const today = new Date(); return date.toDateString() === today.toDateString() ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString([], { day: "2-digit", month: "short" }); }
function statusLabel(status) { return status === "ok" ? "Conectada" : status === "error" ? "Error" : "Pendiente"; }
