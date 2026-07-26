import { useMemo, useState } from "react";
import { Check, Circle } from "lucide-react";
import { api } from "../lib/api";
import { InlineLoading, Notice, PageHeader } from "../components/ui";

export default function Security() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);

  const checks = useMemo(() => [
    { ok: next.length >= 8, label: "Al menos 8 caracteres" },
    { ok: /[A-Z]/.test(next), label: "Una letra mayúscula" },
    { ok: /[a-z]/.test(next), label: "Una letra minúscula" },
    { ok: /[0-9]/.test(next), label: "Un número" },
    { ok: next !== "" && next !== current, label: "Distinta a la contraseña actual" },
    { ok: confirmation !== "" && confirmation === next, label: "Ambas contraseñas coinciden" },
  ], [current, next, confirmation]);
  const valid = current.length > 0 && checks.every((check) => check.ok);

  const submit = async (event) => {
    event.preventDefault();
    if (!valid) return;
    setSaving(true); setMessage(null);
    try {
      await api.changePassword(current, next);
      setCurrent(""); setNext(""); setConfirmation("");
      setMessage({ tone: "success", text: "La contraseña se actualizó correctamente." });
    } catch (error) { setMessage({ tone: "error", text: error.message }); } finally { setSaving(false); }
  };

  return <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-7">
    <PageHeader eyebrow="Administración" title="Configuración" description="Seguridad y preferencias de acceso al panel." />
    {message && <Notice tone={message.tone}>{message.text}</Notice>}
    <div className="grid gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
      <nav aria-label="Secciones de configuración" className="text-sm"><span className="block border-l-2 border-brand-600 bg-white px-3 py-2 font-medium text-brand-700 dark:bg-slate-900 dark:text-brand-200">Contraseña</span></nav>
      <form onSubmit={submit} className="panel p-5 md:p-6">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Cambiar contraseña</h2>
        <p className="mt-1 text-sm text-slate-500">Esta contraseña protege el acceso administrativo a Mail Control.</p>
        <div className="mt-6 max-w-md space-y-4">
          <Field label="Contraseña actual"><input className="input" type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} /></Field>
          <Field label="Nueva contraseña"><input className="input" type="password" autoComplete="new-password" required value={next} onChange={(event) => setNext(event.target.value)} /></Field>
          <Field label="Confirmar nueva contraseña"><input className="input" type="password" autoComplete="new-password" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></Field>
          <ul className="grid gap-1.5 pt-1 sm:grid-cols-2">{checks.map((check) => <li key={check.label} className={`flex items-center gap-2 text-xs ${check.ok ? "text-emerald-700 dark:text-emerald-300" : "text-slate-500"}`}>{check.ok ? <Check size={14} /> : <Circle size={12} />}{check.label}</li>)}</ul>
          <button disabled={!valid || saving} className="btn-primary">{saving ? <InlineLoading label="Guardando" /> : "Guardar nueva contraseña"}</button>
        </div>
      </form>
    </div>
  </div>;
}

function Field({ label, children }) { return <label className="block"><span className="label">{label}</span>{children}</label>; }
