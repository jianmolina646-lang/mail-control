import { useEffect, useState } from "react";
import DOMPurify from "dompurify";
import { ArrowLeft, Calendar, Mail, ShieldAlert, UserRound } from "lucide-react";
import { api } from "../lib/api";

export default function MessageView({ id, onClose }) {
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("html");

  useEffect(() => {
    setMsg(null); setErr(""); setTab("html");
    if (id) api.message(id).then(setMsg).catch((e) => setErr(e.message));
  }, [id]);

  if (!id) return (
    <div className="flex h-full flex-col items-center justify-center p-8 text-center">
      <Mail className="mb-4 text-slate-400" size={26} />
      <h3 className="font-semibold text-slate-800 dark:text-white">Selecciona un correo</h3>
      <p className="mt-1 max-w-xs text-sm text-slate-500">El contenido completo del mensaje aparecerá aquí.</p>
    </div>
  );

  if (!msg && !err) return <ReadingSkeleton />;

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-200/80 p-5 dark:border-white/10">
        <div className="flex items-start gap-3">
          <button onClick={onClose} className="btn-secondary shrink-0 px-2.5" aria-label="Volver a la bandeja" title="Volver a la bandeja"><ArrowLeft size={18} /></button>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-bold leading-6 text-slate-950 dark:text-white">{msg?.subject || "Sin asunto"}</h2>
            {msg && <div className="mt-4 flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100 font-bold text-brand-600 dark:bg-brand-950 dark:text-brand-200">{initials(msg.from_name || msg.from_addr)}</span>
              <div className="min-w-0 flex-1 text-xs">
                <strong className="block truncate text-sm text-slate-800 dark:text-slate-100">{msg.from_name || msg.from_addr}</strong>
                <span className="block truncate text-slate-500">&lt;{msg.from_addr}&gt; para {msg.to_addr}</span>
              </div>
              <time className="hidden items-center gap-1.5 text-xs text-slate-400 lg:flex"><Calendar size={14} />{new Date(msg.received_at).toLocaleString()}</time>
            </div>}
          </div>
        </div>
      </header>
      {msg && !msg.sender_trusted && (
        <div className="m-4 flex gap-3 rounded-md border border-orange-200 bg-orange-50 p-4 text-orange-800 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-200">
          <ShieldAlert className="mt-0.5 shrink-0" size={20} />
          <div><strong className="block text-sm">Posible suplantación de identidad</strong><p className="mt-1 text-xs leading-5">{msg.security_warning} No abras enlaces ni compartas contraseñas o códigos desde este mensaje.</p></div>
        </div>
      )}
      {err && <div role="alert" className="m-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">{err}</div>}
      {msg && <>
        <div className="flex items-center border-b border-slate-100 px-5 py-2 dark:border-slate-800">
          <div className="flex gap-1">
            {msg.body_html && <Tab active={tab === "html"} onClick={() => setTab("html")}>Vista original</Tab>}
            <Tab active={tab === "text"} onClick={() => setTab("text")}>Texto</Tab>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-slate-50/70 p-2 dark:bg-slate-950/30 md:p-4">
          {tab === "html" && msg.body_html
            ? <iframe
                className="mail-message-frame"
                title={`Correo: ${msg.subject || "Sin asunto"}`}
                sandbox="allow-popups allow-popups-to-escape-sandbox"
                srcDoc={emailDocument(msg.body_html)}
              />
            : <pre className="mx-auto min-h-full max-w-4xl whitespace-pre-wrap border border-slate-200 bg-slate-50 p-5 font-sans text-sm leading-6 text-slate-700 dark:border-slate-800 dark:bg-slate-950/50 dark:text-slate-300">{msg.body_text || "(sin contenido de texto)"}</pre>}
        </div>
      </>}
    </div>
  );
}

function Tab({ active, children, ...props }) { return <button {...props} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${active ? "bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-200" : "text-slate-400 hover:text-slate-700 dark:hover:text-white"}`}>{children}</button>; }
function ReadingSkeleton() { return <div className="space-y-5 p-6"><div className="skeleton h-6 w-3/4" /><div className="flex gap-3"><div className="skeleton h-10 w-10" /><div className="flex-1 space-y-2"><div className="skeleton h-3 w-1/3" /><div className="skeleton h-3 w-1/2" /></div></div><div className="space-y-3 pt-6">{[1,2,3,4,5].map((i) => <div key={i} className={`skeleton h-3 ${i % 2 ? "w-full" : "w-4/5"}`} />)}</div></div>; }
function initials(value = "") { return value.split(/[\s@]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || <UserRound size={17} />; }

function emailDocument(html) {
  const clean = DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  });
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root { color-scheme: light; }
      * { box-sizing: border-box; }
      html, body { width: 100%; max-width: 100%; min-height: 100%; margin: 0; overflow-x: auto; }
      body { padding: clamp(12px, 3vw, 28px); background: #fff; color: #111827; font-family: Arial, Helvetica, sans-serif; }
      img, video { max-width: 100% !important; height: auto !important; }
      table { max-width: 100% !important; }
      body > table { width: 100% !important; }
      td, th { max-width: 100%; overflow-wrap: anywhere; }
      pre { max-width: 100%; white-space: pre-wrap; overflow-wrap: anywhere; }
      a { overflow-wrap: anywhere; }
      @media (max-width: 640px) {
        body { padding: 12px; }
        table[width] { width: 100% !important; }
        td[width], th[width] { width: auto !important; }
      }
    </style>
  </head>
  <body>${clean}</body>
</html>`;
}
