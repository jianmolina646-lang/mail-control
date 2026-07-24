import { useCallback, useEffect, useRef, useState } from "react";
import { FixedSizeList as List } from "react-window";
import MessageView from "../components/MessageView";
import { api } from "../lib/api";

const PAGE_SIZE = 100;
const ROW_HEIGHT = 72;

export default function Inbox() {
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

  const load = useCallback(
    async (nextPage, query, replace = false) => {
      if (loadingRef.current && !replace) return;
      const requestId = ++requestRef.current;
      loadingRef.current = true;
      setLoading(true);
      setError("");

      try {
        const data = await api.messages({
          page: nextPage,
          page_size: PAGE_SIZE,
          account_id: selectedAccount || undefined,
          q: query ?? q,
        });
        if (requestId !== requestRef.current) return;
        setTotal(data.total);
        setItems((previous) =>
          replace ? data.items : [...previous, ...data.items],
        );
        setPage(nextPage);
      } catch (err) {
        if (requestId === requestRef.current) setError(err.message);
      } finally {
        if (requestId === requestRef.current) {
          loadingRef.current = false;
          setLoading(false);
        }
      }
    },
    [q, selectedAccount],
  );

  const reset = useCallback(
    (query = q) => {
      requestRef.current += 1;
      loadingRef.current = false;
      setItems([]);
      setPage(1);
      load(1, query, true);
    },
    [load, q],
  );

  useEffect(() => {
    api.accounts().then(setAccounts).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setSelected(null);
    reset("");
  }, [selectedAccount]); // eslint-disable-line react-hooks/exhaustive-deps

  const syncSelected = async () => {
    setSyncing(true);
    setError("");
    try {
      const targets = selectedAccount
        ? accounts.filter((account) => String(account.id) === selectedAccount)
        : accounts.filter((account) => account.is_enabled);
      await Promise.all(targets.map((account) => api.syncAccount(account.id)));
      window.setTimeout(() => reset(q), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const onScroll = ({ scrollOffset }) => {
    const visibleEnd = scrollOffset + 600;
    const loadedHeight = items.length * ROW_HEIGHT;
    if (
      visibleEnd >= loadedHeight - 400 &&
      items.length < total &&
      !loadingRef.current
    ) {
      load(page + 1);
    }
  };

  const Row = ({ index, style }) => {
    const message = items[index];
    if (!message) return null;
    const active = selected === message.id;
    return (
      <button
        type="button"
        style={style}
        onClick={() => setSelected(message.id)}
        className={`w-full px-4 text-left border-b border-edge/60 transition ${
          active ? "bg-accent/15" : "hover:bg-edge/40"
        }`}
      >
        <div className="flex items-center gap-3">
          {message.is_alert && <span title="Alerta crítica">🚨</span>}
          <span className="w-32 shrink-0 truncate text-sm font-semibold text-white">
            {message.from_name || message.from_addr}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-zinc-300">
            {message.subject || "(sin asunto)"}
            <span className="font-normal text-zinc-500">
              {" "}— {message.snippet}
            </span>
          </span>
          <time className="shrink-0 text-[11px] text-zinc-500">
            {formatMessageDate(message.received_at)}
          </time>
        </div>
      </button>
    );
  };

  const accountLabel =
    accounts.find((account) => String(account.id) === selectedAccount)?.email ||
    "Todas las cuentas";

  return (
    <div className="flex h-full min-h-0">
      <AccountSidebar
        accounts={accounts}
        selectedAccount={selectedAccount}
        onSelect={setSelectedAccount}
      />

      <section className="flex w-full min-w-0 flex-col border-r border-edge md:w-[420px] lg:w-[520px]">
        <div className="space-y-2 border-b border-edge p-3">
          <select
            value={selectedAccount}
            onChange={(event) => setSelectedAccount(event.target.value)}
            className="w-full rounded-lg border border-edge bg-surface px-3 py-2 text-sm lg:hidden"
          >
            <option value="">Todas las cuentas</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.email}
              </option>
            ))}
          </select>

          <div className="flex gap-2">
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && reset(q)}
              placeholder="Buscar remitente o asunto…"
              className="min-w-0 flex-1 rounded-lg border border-edge bg-surface px-3 py-2 text-sm focus:border-accent focus:outline-none"
            />
            <button
              type="button"
              onClick={() => reset(q)}
              className="rounded-lg bg-edge px-3 text-sm hover:bg-edge/70"
              title="Buscar"
            >
              🔍
            </button>
            <button
              type="button"
              onClick={syncSelected}
              disabled={syncing}
              className="rounded-lg bg-edge px-3 text-sm hover:bg-edge/70 disabled:opacity-60"
              title={`Sincronizar ${accountLabel}`}
            >
              {syncing ? "⟳" : "↻"}
            </button>
          </div>
        </div>

        <div className="border-b border-edge/60 px-4 py-2 text-xs text-zinc-500">
          <span className="font-medium text-zinc-300">{accountLabel}</span>
          {" · "}{total} correos
          {loading && " · cargando…"}
        </div>

        {error && (
          <div className="border-b border-red-900/40 bg-red-950/30 px-4 py-2 text-xs text-red-300">
            {error}
          </div>
        )}

        <div className="min-h-0 flex-1">
          {items.length === 0 && !loading ? (
            <div className="p-8 text-center text-sm text-zinc-500">
              No hay correos para esta cuenta.
            </div>
          ) : (
            <AutoList itemCount={items.length} onScroll={onScroll} Row={Row} />
          )}
        </div>
      </section>

      <section
        className={`absolute inset-0 min-w-0 flex-1 bg-surface md:static md:block ${
          selected ? "block" : "hidden"
        }`}
      >
        <MessageView id={selected} onClose={() => setSelected(null)} />
      </section>
    </div>
  );
}

function AccountSidebar({ accounts, selectedAccount, onSelect }) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-edge bg-panel lg:flex">
      <div className="border-b border-edge px-4 py-4">
        <div className="font-semibold text-white">Cuentas vinculadas</div>
        <div className="mt-0.5 text-xs text-zinc-500">
          Selecciona una bandeja
        </div>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        <AccountButton
          active={selectedAccount === ""}
          label="Todas las cuentas"
          detail={`${accounts.length} vinculadas`}
          onClick={() => onSelect("")}
        />
        {accounts.map((account) => (
          <AccountButton
            key={account.id}
            active={selectedAccount === String(account.id)}
            label={account.email}
            detail={`${account.provider} · ${statusLabel(account.last_status)}`}
            onClick={() => onSelect(String(account.id))}
          />
        ))}
      </div>
    </aside>
  );
}

function AccountButton({ active, label, detail, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full border-r-2 px-4 py-3 text-left transition ${
        active
          ? "border-accent bg-accent/15"
          : "border-transparent hover:bg-edge/40"
      }`}
    >
      <div className="truncate text-sm font-medium text-white">{label}</div>
      <div className="mt-0.5 truncate text-xs text-zinc-500">{detail}</div>
    </button>
  );
}

function AutoList({ itemCount, onScroll, Row }) {
  const containerRef = useRef(null);
  const [height, setHeight] = useState(600);

  useEffect(() => {
    const update = () => {
      if (containerRef.current) setHeight(containerRef.current.clientHeight);
    };
    update();
    const observer = new ResizeObserver(update);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="h-full">
      <List
        height={height}
        itemCount={itemCount}
        itemSize={ROW_HEIGHT}
        width="100%"
        onScroll={onScroll}
      >
        {Row}
      </List>
    </div>
  );
}

function formatMessageDate(value) {
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { day: "2-digit", month: "short" });
}

function statusLabel(status) {
  if (status === "ok") return "OK";
  if (status === "error") return "Error";
  return "Pendiente";
}
