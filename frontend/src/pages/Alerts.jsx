import { useEffect, useState } from "react";
import { api } from "../lib/api";
import MessageView from "../components/MessageView";

export default function Alerts() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api
      .alerts({ page: 1, page_size: 200 })
      .then((d) => setItems(d.items))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const resolve = async (id, e) => {
    e.stopPropagation();
    await api.resolveAlert(id);
    setItems((prev) => prev.filter((a) => a.id !== id));
  };

  return (
    <div className="flex h-full">
      <div className="w-full md:w-[420px] border-r border-edge flex flex-col">
        <div className="p-4 border-b border-edge">
          <h1 className="font-bold text-white flex items-center gap-2">
            🚨 Alertas críticas
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Problemas de suscripción detectados en las casillas
          </p>
        </div>
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="p-6 text-center text-zinc-500 text-sm">Cargando…</div>
          ) : items.length === 0 ? (
            <div className="p-6 text-center text-emerald-400 text-sm">
              ✓ Sin alertas abiertas. Todo en orden.
            </div>
          ) : (
            items.map((a) => (
              <div
                key={a.id}
                onClick={() => setSelected(a.message.id)}
                className={`p-4 border-b border-edge/60 cursor-pointer ${
                  selected === a.message.id ? "bg-accent/10" : "hover:bg-edge/40"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="bg-accent/20 text-accent text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                    {a.service}
                  </span>
                  <span className="text-[10px] text-amber-400 uppercase tracking-wide">
                    {a.keyword}
                  </span>
                  <span className="ml-auto text-[11px] text-zinc-500">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="text-sm text-white truncate">{a.message.subject}</div>
                <div className="text-xs text-zinc-500 truncate">{a.message.from_addr}</div>
                <button
                  onClick={(e) => resolve(a.id, e)}
                  className="mt-2 text-xs text-emerald-400 hover:text-emerald-300"
                >
                  ✓ Marcar resuelta
                </button>
              </div>
            ))
          )}
        </div>
      </div>
      <div className={`flex-1 min-w-0 ${selected ? "block" : "hidden md:block"}`}>
        <MessageView id={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}
