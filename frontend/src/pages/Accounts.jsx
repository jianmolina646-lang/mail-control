import { useEffect, useState } from "react";
import { api } from "../lib/api";

const EMPTY = {
  email: "",
  provider: "outlook",
  imap_host: "",
  imap_port: 993,
  imap_user: "",
  password: "",
};

const PRESETS = {
  outlook: "outlook.office365.com",
  hotmail: "outlook.office365.com",
  gmail: "imap.gmail.com",
  custom: "",
};

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.accounts().then(setAccounts);
  useEffect(() => { load(); }, []);

  const setField = (k, v) => {
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === "provider") next.imap_host = PRESETS[v] ?? "";
      return next;
    });
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      await api.createAccount(form);
      setForm(EMPTY);
      setMsg({ ok: true, text: "✓ Casilla agregada. Se está sincronizando automáticamente…" });
      load();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const act = async (fn, id, okText) => {
    try {
      await fn(id);
      setMsg({ ok: true, text: okText });
      load();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  };

  return (
    <div className="h-full overflow-auto p-4 md:p-6 max-w-4xl mx-auto space-y-6">
      <form onSubmit={submit} className="bg-panel border border-edge rounded-2xl p-5 space-y-3">
        <h2 className="font-bold text-white">Agregar casilla</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Email">
            <input required type="email" value={form.email}
              onChange={(e) => setField("email", e.target.value)} className={inp} />
          </Field>
          <Field label="Proveedor">
            <select value={form.provider} onChange={(e) => setField("provider", e.target.value)} className={inp}>
              <option value="outlook">Outlook / Office365</option>
              <option value="hotmail">Hotmail</option>
              <option value="gmail">Gmail</option>
              <option value="custom">Otro (IMAP manual)</option>
            </select>
          </Field>
          <Field label="Servidor IMAP">
            <input required value={form.imap_host}
              onChange={(e) => setField("imap_host", e.target.value)} className={inp} />
          </Field>
          <Field label="Puerto">
            <input type="number" value={form.imap_port}
              onChange={(e) => setField("imap_port", +e.target.value)} className={inp} />
          </Field>
          <Field label="Usuario IMAP (opcional)">
            <input value={form.imap_user} placeholder="por defecto = email"
              onChange={(e) => setField("imap_user", e.target.value)} className={inp} />
          </Field>
          <Field label="App Password (se guarda encriptada)">
            <input required type="password" value={form.password}
              onChange={(e) => setField("password", e.target.value)} className={inp} />
          </Field>
        </div>
        {msg && (
          <div className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</div>
        )}
        <button disabled={saving}
          className="bg-accent hover:bg-red-700 disabled:opacity-60 text-white font-semibold rounded-lg px-4 py-2 text-sm">
          {saving ? "Guardando…" : "Agregar casilla"}
        </button>
      </form>

      <div className="bg-panel border border-edge rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-edge font-bold text-white">
          Casillas ({accounts.length})
        </div>
        <div className="divide-y divide-edge/60">
          {accounts.map((a) => (
            <div key={a.id} className="p-4 flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm text-white truncate">{a.email}</div>
                <div className="text-xs text-zinc-500">
                  {a.imap_host}:{a.imap_port} ·{" "}
                  <StatusBadge status={a.last_status} error={a.last_error} />
                  {a.last_synced_at && (
                    <> · {new Date(a.last_synced_at).toLocaleString()}</>
                  )}
                </div>
              </div>
              <div className="flex gap-2 text-xs">
                <button onClick={() => act(api.testAccount, a.id, "Conexión OK")}
                  className="px-2.5 py-1.5 rounded-lg bg-edge hover:bg-edge/70">Probar</button>
                <button onClick={() => act(api.syncAccount, a.id, "Escaneo encolado")}
                  className="px-2.5 py-1.5 rounded-lg bg-edge hover:bg-edge/70">Sincronizar</button>
                <button
                  onClick={() => act((id) => api.updateAccount(id, { is_enabled: !a.is_enabled }), a.id, "Actualizado")}
                  className="px-2.5 py-1.5 rounded-lg bg-edge hover:bg-edge/70">
                  {a.is_enabled ? "Pausar" : "Activar"}
                </button>
                <button
                  onClick={() => confirm(`¿Eliminar ${a.email}?`) && act(api.deleteAccount, a.id, "Eliminada")}
                  className="px-2.5 py-1.5 rounded-lg bg-red-900/40 text-red-300 hover:bg-red-900/70">
                  Eliminar
                </button>
              </div>
            </div>
          ))}
          {accounts.length === 0 && (
            <div className="p-6 text-center text-sm text-zinc-500">Sin casillas cargadas.</div>
          )}
        </div>
      </div>
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

function StatusBadge({ status, error }) {
  const map = {
    ok: ["text-emerald-400", "OK"],
    error: ["text-red-400", "Error"],
    pending: ["text-zinc-400", "Pendiente"],
  };
  const [cls, label] = map[status] || map.pending;
  return <span className={cls} title={error || ""}>{label}</span>;
}
