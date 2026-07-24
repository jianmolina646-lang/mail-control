import { useEffect, useState } from "react";
import DOMPurify from "dompurify";
import { api } from "../lib/api";

export default function MessageView({ id, onClose }) {
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("html");

  useEffect(() => {
    setMsg(null);
    setErr("");
    setTab("html");
    if (id) api.message(id).then(setMsg).catch((e) => setErr(e.message));
  }, [id]);

  if (!id) {
    return (
      <div className="hidden md:flex flex-col items-center justify-center h-full text-zinc-600">
        <div className="text-5xl mb-3">✉️</div>
        <p className="text-sm">Elegí un correo para verlo acá</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-edge flex items-start gap-3">
        <button
          onClick={onClose}
          className="md:hidden text-zinc-400 hover:text-white text-xl leading-none"
        >
          ←
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-white break-words">
            {msg?.subject || (err ? "" : "Cargando…")}
          </h2>
          {msg && (
            <div className="text-xs text-zinc-400 mt-1">
              <div>
                <span className="text-zinc-500">De:</span> {msg.from_name} &lt;{msg.from_addr}&gt;
              </div>
              <div>
                <span className="text-zinc-500">Para:</span> {msg.to_addr}
              </div>
              <div>{new Date(msg.received_at).toLocaleString()}</div>
            </div>
          )}
        </div>
      </div>

      {err && <div className="p-4 text-red-400 text-sm">{err}</div>}

      {msg && (
        <>
          <div className="flex gap-1 px-4 pt-3 text-xs">
            {msg.body_html && (
              <TabBtn active={tab === "html"} onClick={() => setTab("html")}>
                HTML
              </TabBtn>
            )}
            <TabBtn active={tab === "text"} onClick={() => setTab("text")}>
              Texto
            </TabBtn>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {tab === "html" && msg.body_html ? (
              <div
                className="mail-html-body bg-white text-black rounded-lg p-4 text-sm"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(msg.body_html, {
                    USE_PROFILES: { html: true },
                  }),
                }}
              />
            ) : (
              <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-sans">
                {msg.body_text || "(sin contenido de texto)"}
              </pre>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function TabBtn({ active, children, ...rest }) {
  return (
    <button
      {...rest}
      className={`px-3 py-1.5 rounded-t-lg ${
        active ? "bg-panel text-white border border-edge border-b-panel" : "text-zinc-500"
      }`}
    >
      {children}
    </button>
  );
}
