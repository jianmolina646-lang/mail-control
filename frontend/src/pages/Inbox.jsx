import { useCallback, useEffect, useRef, useState } from "react";
import { FixedSizeList as List } from "react-window";
import { AlertTriangle, Inbox as InboxIcon, RefreshCw, Search, ShieldAlert } from "lucide-react";
import MessageView from "../components/MessageView";
import { EmptyState, PageHeader } from "../components/ui";
import { api } from "../lib/api";

const PAGE_SIZE = 100;
const ROW_HEIGHT = 78;

export default function Inbox() {
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const loadingRef = useRef(false);
  const requestRef = useRef(0);

  const load = useCallback(async (nextPage, search, replace = false) => {
    if (loadingRef.current && !replace) return;
    const requestId = ++requestRef.current;
    loadingRef.current = true; setLoading(true); setError("");
    try {
      const data = await api.messages({ page: nextPage, page_size: PAGE_SIZE, account_id: accountId || undefined, q: search ?? query });
      if (requestId !== requestRef.current) return;
      setItems((previous) => replace ? data.items : [...previous, ...data.items]);
      setTotal(data.total); setPage(nextPage);
    } catch (err) {
      if (requestId === requestRef.current) setError(err.message);
    } finally {
      if (requestId === requestRef.current) { loadingRef.current = false; setLoading(false); }
    }
  }, [accountId, query]);

  const reset = useCallback((search = query) => {
    requestRef.current += 1; loadingRef.current = false; setItems([]); setPage(1); load(1, search, true);
  }, [load, query]);

  useEffect(() => { api.accounts().then(setAccounts).catch((err) => setError(err.message)); }, []);
  useEffect(() => { setSelected(null); reset(""); }, [accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  const sync = async () => {
    setSyncing(true); setError("");
    try {
      const targets = accountId ? accounts.filter((item) => String(item.id) === accountId) : accounts.filter((item) => item.is_enabled);
      await Promise.all(targets.map((item) => api.syncAccount(item.id)));
      window.setTimeout(() => reset(query), 3000);
    } catch (err) { setError(err.message); } finally { setSyncing(false); }
  };

  const activeLabel = accounts.find((item) => String(item.id) === accountId)?.email || "Todas las cuentas";
  const Row = ({ index, style }) => {
    const message = items[index];
    if (!message) return null;
    const isActive = selected === message.id;
    return <button style={style} onClick={() => setSelected(message.id)} className={`w-full border-b border-slate-100 px-4 text-left dark:border-slate-800 ${isActive ? "bg-brand-50 dark:bg-brand-950/30" : "hover:bg-slate-50 dark:hover:bg-slate-800/50"}`}>
      <span className="flex h-full items-center gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${!message.sender_trusted ? "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300" : message.is_alert ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{!message.sender_trusted ? <ShieldAlert size={16} /> : message.is_alert ? <AlertTriangle size={16} /> : initials(message.from_name || message.from_addr)}</span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2"><strong className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{message.from_name || message.from_addr}</strong><time className="ml-auto shrink-0 text-[11px] text-slate-400">{formatDate(message.received_at)}</time></span>
          <span className="mt-1 flex min-w-0 items-center gap-2"><span className="truncate text-xs text-slate-600 dark:text-slate-300">{message.subject || "(sin asunto)"}</span>{!message.sender_trusted && <span className="shrink-0 text-[10px] font-semibold text-orange-700 dark:text-orange-300">Remitente no verificado</span>}</span>
          <span className="mt-0.5 block truncate text-xs text-slate-400">{message.snippet}</span>
        </span>
      </span>
    </button>;
  };

  return <div className="inbox-page flex min-h-full flex-col gap-5 p-4 md:p-7">
    <PageHeader eyebrow="Centro de comunicaciones" title="Bandeja de entrada" description="Mensajes sincronizados de todas tus cuentas conectadas." />
    <div className="panel flex min-h-[640px] flex-1 overflow-hidden">
      <aside className={`hidden w-60 shrink-0 border-r border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40 ${selected ? "2xl:block" : "xl:block"}`}>
        <p className="px-4 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Cuentas conectadas</p>
        <AccountOption active={!accountId} label="Todas las cuentas" detail={`${accounts.length} conectadas`} onClick={() => setAccountId("")} />
        {accounts.map((account) => <AccountOption key={account.id} active={accountId === String(account.id)} label={account.email} detail={`${account.provider} · ${account.last_status === "ok" ? "Conectada" : account.last_status === "error" ? "Con error" : "Pendiente"}`} onClick={() => setAccountId(String(account.id))} />)}
      </aside>
      <section className={`flex w-full min-w-0 flex-col border-r border-slate-200 dark:border-slate-800 ${selected ? "md:w-[340px] lg:w-[380px]" : "md:w-[400px] lg:w-[460px]"}`}>
        <div className="space-y-3 border-b border-slate-200 p-4 dark:border-slate-800">
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)} className="input xl:hidden"><option value="">Todas las cuentas</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.email}</option>)}</select>
          <div className="flex gap-2"><label className="relative min-w-0 flex-1"><span className="sr-only">Buscar correos</span><Search className="absolute left-3 top-3 text-slate-400" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && reset(query)} className="input pl-9" placeholder="Buscar por remitente o asunto" /></label><button onClick={sync} disabled={syncing || !accounts.length} className="btn-secondary px-3" aria-label={`Sincronizar ${activeLabel}`}><RefreshCw size={16} className={syncing ? "animate-spin" : ""} /></button></div>
          <div className="flex justify-between text-xs text-slate-500"><strong className="max-w-[70%] truncate font-medium text-slate-700 dark:text-slate-300">{activeLabel}</strong><span>{total} mensajes</span></div>
        </div>
        {error && <div role="alert" className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">{error}</div>}
        <div className="min-h-0 flex-1">{loading && !items.length ? <MessageSkeleton /> : !items.length ? <EmptyState icon={InboxIcon} title="Tu bandeja está vacía" description={accounts.length ? "No hay mensajes para esta cuenta o búsqueda. Actualiza para comprobar si llegaron correos nuevos." : "Conecta una cuenta de correo antes de sincronizar mensajes."} action={accounts.length ? <button onClick={sync} className="btn-secondary"><RefreshCw size={16} /> Actualizar bandeja</button> : null} /> : <AutoList itemCount={items.length} Row={Row} onScroll={({ scrollOffset }) => { if (scrollOffset + 600 >= items.length * ROW_HEIGHT - 400 && items.length < total && !loadingRef.current) load(page + 1); }} />}</div>
      </section>
      <section className={`absolute inset-0 z-20 min-w-0 flex-1 bg-white dark:bg-slate-900 md:static md:z-auto ${selected ? "block" : "hidden md:block"}`}><MessageView id={selected} onClose={() => setSelected(null)} /></section>
    </div>
  </div>;
}

function AccountOption({ active, label, detail, onClick }) { return <button onClick={onClick} className={`mx-2 mb-0.5 w-[calc(100%-1rem)] rounded-md border-l-2 px-3 py-2.5 text-left ${active ? "border-brand-600 bg-white text-brand-700 dark:bg-slate-900 dark:text-brand-200" : "border-transparent text-slate-600 hover:bg-white dark:text-slate-400 dark:hover:bg-slate-900"}`}><span className="block truncate text-sm font-medium">{label}</span><span className="mt-0.5 block truncate text-[11px] text-slate-400">{detail}</span></button>; }
function MessageSkeleton() { return <div className="space-y-5 p-4">{[1,2,3,4,5].map((item) => <div key={item} className="flex gap-3"><div className="skeleton h-9 w-9 rounded-full" /><div className="flex-1 space-y-2"><div className="skeleton h-3 w-2/5" /><div className="skeleton h-3 w-4/5" /></div></div>)}</div>; }
function AutoList({ itemCount, onScroll, Row }) { const ref = useRef(null); const [height, setHeight] = useState(600); useEffect(() => { const update = () => ref.current && setHeight(ref.current.clientHeight); update(); const observer = new ResizeObserver(update); if (ref.current) observer.observe(ref.current); return () => observer.disconnect(); }, []); return <div ref={ref} className="h-full"><List height={height} itemCount={itemCount} itemSize={ROW_HEIGHT} width="100%" onScroll={onScroll}>{Row}</List></div>; }
function initials(value = "") { return value.split(/[\s@]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "M"; }
function formatDate(value) { const date = new Date(value); const today = new Date(); return date.toDateString() === today.toDateString() ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString([], { day: "2-digit", month: "short" }); }
