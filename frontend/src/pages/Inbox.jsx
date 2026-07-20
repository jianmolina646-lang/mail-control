import { useCallback, useEffect, useRef, useState } from "react";
import { FixedSizeList as List } from "react-window";
import { api } from "../lib/api";
import MessageView from "../components/MessageView";

const PAGE_SIZE = 50;
const ROW_HEIGHT = 76;

export default function Inbox() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const loadingRef = useRef(false);

  const reset = useCallback((query) => {
    setItems([]);
    setPage(1);
    load(1, query, true);
  }, []);

  const load = useCallback(async (p, query, replace = false) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const data = await api.messages({
        page: p,
        page_size: PAGE_SIZE,
        q: query ?? q,
      });
      setTotal(data.total);
      setItems((prev) => (replace ? data.items : [...prev, ...data.items]));
      setPage(p);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    load(1, "", true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onScroll = ({ scrollOffset }) => {
    const visibleEnd = scrollOffset + 600;
    const loadedHeight = items.length * ROW_HEIGHT;
    if (visibleEnd >= loadedHeight - 400 && items.length < total && !loadingRef.current) {
      load(page + 1);
    }
  };

  const Row = ({ index, style }) => {
    const m = items[index];
    if (!m) return null;
    const active = selected === m.id;
    return (
      <div
        style={style}
        onClick={() => setSelected(m.id)}
        className={`px-4 flex flex-col justify-center border-b border-edge/60 cursor-pointer ${
          active ? "bg-accent/10" : "hover:bg-edge/40"
        }`}
      >
        <div className="flex items-center gap-2">
          {m.is_alert && <span title="Alerta">🚨</span>}
          <span className="text-sm font-medium text-white truncate flex-1">
            {m.from_name || m.from_addr}
          </span>
          <span className="text-[11px] text-zinc-500 flex-shrink-0">
            {new Date(m.received_at).toLocaleDateString()}
          </span>
        </div>
        <div className="text-sm text-zinc-300 truncate">{m.subject || "(sin asunto)"}</div>
        <div className="text-xs text-zinc-500 truncate">{m.snippet}</div>
      </div>
    );
  };

  return (
    <div className="flex h-full">
      <div className="w-full md:w-[380px] lg:w-[420px] border-r border-edge flex flex-col">
        <div className="p-3 border-b border-edge flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && reset(q)}
            placeholder="Buscar remitente o asunto…"
            className="flex-1 bg-surface border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => reset(q)}
            className="px-3 rounded-lg bg-edge hover:bg-edge/70 text-sm"
          >
            🔍
          </button>
        </div>
        <div className="px-4 py-1.5 text-xs text-zinc-500 border-b border-edge/60">
          {total} correos {loading && "· cargando…"}
        </div>
        <div className="flex-1 min-h-0">
          {items.length === 0 && !loading ? (
            <div className="p-6 text-center text-sm text-zinc-500">Sin correos todavía.</div>
          ) : (
            <AutoList
              itemCount={items.length}
              onScroll={onScroll}
              Row={Row}
            />
          )}
        </div>
      </div>
      <div className={`flex-1 min-w-0 ${selected ? "block" : "hidden md:block"} absolute md:static inset-0 bg-surface md:bg-transparent`}>
        <MessageView id={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}

function AutoList({ itemCount, onScroll, Row }) {
  const ref = useRef(null);
  const [height, setHeight] = useState(600);
  useEffect(() => {
    const update = () => {
      if (ref.current) setHeight(ref.current.clientHeight);
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return (
    <div ref={ref} className="h-full">
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
