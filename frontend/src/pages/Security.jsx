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
    <div className="h-full overflow-auto p-4 md:p-6 max-w-lg mx-auto">
      <form onSubmit={submit} className="bg-panel border border-edge rounded-2xl p-6 space-y-4">
        <div>
          <h2 className="font-bold text-white flex items-center gap-2">🔐 Seguridad</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Cambiá la contraseña de acceso al panel.</p>
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
                    : "bg-edge"
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
              c.ok ? "text-emerald-400" : "text-zinc-500"
            }`}>
              <span>{c.ok ? "✓" : "○"}</span> {c.label}
            </li>
          ))}
        </ul>

        {msg && (
          <div className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</div>
        )}

        <button disabled={!valid || saving}
          className="w-full bg-accent hover:bg-red-700 disabled:opacity-40 text-white font-semibold rounded-lg py-2.5 text-sm transition">
          {saving ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </form>
    </div>
  );
}

const inp =
  "w-full bg-surface border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs text-zinc-400">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
