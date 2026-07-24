import { useEffect, useState } from "react";
import DOMPurify from "dompurify";
import { ArrowLeft, Calendar, Mail, MoreHorizontal, Reply, UserRound } from "lucide-react";
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
      <span className="mb-5 flex h-16 w-16 items-center justify-center rounded-3xl bg-brand-50 text-brand-600 dark:bg-brand-500/10"><Mail size={28} /></span>
      <h3 className="font-semibold text-slate-800 dark:text-white">Selecciona un correo</h3>
      <p className="mt-1 max-w-xs text-sm text-slate-500">El contenido completo del mensaje aparecerá aquí.</p>
    </div>
  );

  if (!msg && !err) return <ReadingSkeleton />;

  return (
    <div className="flex h-full flex-col animate-fade-in">
      <header className="border-b border-slate-200/80 p-5 dark:border-white/10">
        <div className="flex items-start gap-3">
          <button onClick={onClose} className="btn-secondary px-2.5 md:hidden"><ArrowLeft size={18} /></button>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-bold leading-6 text-slate-950 dark:text-white">{msg?.subject || "Sin asunto"}</h2>
            {msg && <div className="mt-4 flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-100 font-bold text-brand-600 dark:bg-brand-500/15">{initials(msg.from_name || msg.from_addr)}</span>
              <div className="min-w-0 flex-1 text-xs">
                <strong className="block truncate text-sm text-slate-800 dark:text-slate-100">{msg.from_name || msg.from_addr}</strong>
                <span className="block truncate text-slate-500">&lt;{msg.from_addr}&gt; para {msg.to_addr}</span>
              </div>
              <time className="hidden items-center gap-1.5 text-xs text-slate-400 lg:flex"><Calendar size={14} />{new Date(msg.received_at).toLocaleString()}</time>
            </div>}
          </div>
          <button className="btn-secondary px-2.5"><MoreHorizontal size={18} /></button>
        </div>
      </header>
      {err && <div className="m-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-600 dark:bg-rose-500/10">{err}</div>}
      {msg && <>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-2 dark:border-white/5">
          <div className="flex gap-1">
            {msg.body_html && <Tab active={tab === "html"} onClick={() => setTab("html")}>Vista original</Tab>}
            <Tab active={tab === "text"} onClick={() => setTab("text")}>Texto</Tab>
          </div>
          <button className="btn-secondary py-1.5"><Reply size={15} /> Responder</button>
        </div>
        <div className="flex-1 overflow-auto p-4 md:p-6">
          {tab === "html" && msg.body_html ? <div className="mail-html-body mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-5 text-sm text-black shadow-sm" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(msg.body_html, { USE_PROFILES: { html: true } }) }} /> : <pre className="mx-auto max-w-4xl whitespace-pre-wrap rounded-2xl bg-slate-50 p-5 font-sans text-sm leading-6 text-slate-700 dark:bg-slate-950/50 dark:text-slate-300">{msg.body_text || "(sin contenido de texto)"}</pre>}
        </div>
      </>}
    </div>
  );
}

function Tab({ active, children, ...props }) { return <button {...props} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${active ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "text-slate-400 hover:text-slate-700 dark:hover:text-white"}`}>{children}</button>; }
function ReadingSkeleton() { return <div className="space-y-5 p-6"><div className="skeleton h-6 w-3/4" /><div className="flex gap-3"><div className="skeleton h-10 w-10" /><div className="flex-1 space-y-2"><div className="skeleton h-3 w-1/3" /><div className="skeleton h-3 w-1/2" /></div></div><div className="space-y-3 pt-6">{[1,2,3,4,5].map((i) => <div key={i} className={`skeleton h-3 ${i % 2 ? "w-full" : "w-4/5"}`} />)}</div></div>; }
function initials(value = "") { return value.split(/[\s@]+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || <UserRound size={17} />; }
