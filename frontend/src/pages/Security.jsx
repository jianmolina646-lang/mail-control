import { useMemo, useState } from "react";
import { api } from "../lib/api";

export default function Security() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState(null);
  const [saving, setSaving] = useState(false);

  const checks = useMemo(
    () => [
      { ok: next.length >= 8, label: "Mínimo 8 caracteres" },
      { ok: /[A-Z]/.test(next), label: "Una mayúscula" },
      { ok: /[a-z]/.test(next), label: "Una minúscula" },
      { ok: /[0-9]/.test(next), label: "Un número" },
      { ok: next !== "" && next !== current, label: "Distinta a la actual" },
      { ok: confirm !== "" && confirm === next, label: "Las contraseñas coinciden" },
    ],
    [current, next, confirm]
  );
  const valid = current.length > 0 && checks.every((c) => c.ok);

  const strength = useMemo(() => {
    let s = 0;
    if (next.length >= 8) s++;
    if (next.length >= 12) s++;
    if (/[A-Z]/.test(next) && /[a-z]/.test(next)) s++;
    if (/[0-9]/.test(next)) s++;
    if (/[^A-Za-z0-9]/.test(next)) s++;
    return s; // 0-5
  }, [next]);

  const submit = async (e) => {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    setMsg(null);
    try {
      await api.changePassword(current, next);
      setMsg({ ok: true, text: "Contraseña actualizada correctamente." });
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto h-full max-w-xl overflow-auto p-4 md:p-8">
      <form onSubmit={submit} className="card space-y-4 p-6">
        <div>
          <p className="text-sm font-semibold text-brand-600">Protección de acceso</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">Seguridad</h2>
          <p className="mt-1 text-sm text-slate-500">Actualiza la contraseña de acceso al panel.</p>
        </div>

        <Field label="Contraseña actual">
          <input type="password" required value={current} autoComplete="current-password"
            onChange={(e) => setCurrent(e.target.value)} className={inp} />
        </Field>

        <Field label="Nueva contraseña">
          <input type="password" required value={next} autoComplete="new-password"
            onChange={(e) => setNext(e.target.value)} className={inp} />
          {next && (
            <div className="mt-2 flex gap-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className={`h-1.5 flex-1 rounded-full ${
                  i <= strength
                    ? strength <= 2 ? "bg-red-500" : strength <= 3 ? "bg-amber-400" : "bg-emerald-500"
                    : "bg-slate-200 dark:bg-slate-800"
                }`} />
              ))}
            </div>
          )}
        </Field>

        <Field label="Confirmar nueva contraseña">
          <input type="password" required value={confirm} autoComplete="new-password"
            onChange={(e) => setConfirm(e.target.value)} className={inp} />
        </Field>

        <ul className="space-y-1">
          {checks.map((c) => (
            <li key={c.label} className={`text-xs flex items-center gap-2 ${
              c.ok ? "text-emerald-500" : "text-slate-500"
            }`}>
              <span>{c.ok ? "✓" : "○"}</span> {c.label}
            </li>
          ))}
        </ul>

        {msg && (
          <div className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</div>
        )}

        <button disabled={!valid || saving}
          className="btn-primary w-full">
          {saving ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </form>
    </div>
  );
}

const inp = "input";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
