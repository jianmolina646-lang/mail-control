import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

const EMPTY = {
  email: "",
  provider: "outlook",
  imap_host: "outlook.office365.com",
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.accounts().then(setAccounts);
  useEffect(() => {
    load();
    const oauth = searchParams.get("oauth");
    if (oauth === "connected") {
      setMsg({ ok: true, text: "Cuenta Microsoft vinculada con OAuth2." });
      setSearchParams({}, { replace: true });
    } else if (oauth === "error") {
      setMsg({
        ok: false,
        text: searchParams.get("detail") || "Microsoft rechazó la autorización.",
      });
      setSearchParams({}, { replace: true });
    }
  }, []);

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
      const account = await api.createAccount(form);
      if (["outlook", "hotmail"].includes(form.provider)) {
        const { authorization_url } = await api.authorizeMicrosoft(account.id);
        window.location.assign(authorization_url);
        return;
      }
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
    <div className="mx-auto h-full max-w-6xl space-y-6 overflow-auto p-4 md:p-8">
      <div><p className="text-sm font-semibold text-brand-600">Integraciones</p><h1 className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">Cuentas de correo</h1><p className="mt-1 text-sm text-slate-500">Conecta y supervisa todas tus bandejas desde un solo lugar.</p></div>
      <form onSubmit={submit} className="card space-y-4 p-5 md:p-6">
        <h2 className="font-bold text-slate-900 dark:text-white">Agregar una cuenta</h2>
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
          <Field label={
            ["outlook", "hotmail"].includes(form.provider)
              ? "Microsoft usa OAuth2 (no necesita contraseña)"
              : "App Password (se guarda encriptada)"
          }>
            <input
              required={!["outlook", "hotmail"].includes(form.provider)}
              disabled={["outlook", "hotmail"].includes(form.provider)}
              type="password" value={form.password}
              onChange={(e) => setField("password", e.target.value)} className={inp} />
          </Field>
        </div>
        {msg && (
          <div className={`text-sm ${msg.ok ? "text-emerald-400" : "text-red-400"}`}>{msg.text}</div>
        )}
        <button disabled={saving}
          className="btn-primary">
          {saving ? "Guardando…" : "Agregar casilla"}
        </button>
      </form>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-200/80 p-5 font-bold text-slate-900 dark:border-white/10 dark:text-white">
          Casillas ({accounts.length})
        </div>
        <div className="divide-y divide-slate-100 dark:divide-white/5">
          {accounts.map((a) => (
            <div key={a.id} className="p-4 flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-slate-800 dark:text-white">{a.email}</div>
                <div className="text-xs text-slate-500">
                  {a.imap_host}:{a.imap_port} ·{" "}
                  <StatusBadge status={a.last_status} error={a.last_error} />
                  {a.last_synced_at && (
                    <> · {new Date(a.last_synced_at).toLocaleString()}</>
                  )}
                </div>
              </div>
              <div className="flex gap-2 text-xs">
                {["outlook", "hotmail"].includes(a.provider) && (
                  <button
                    onClick={async () => {
                      try {
                        const { authorization_url } = await api.authorizeMicrosoft(a.id);
                        window.location.assign(authorization_url);
                      } catch (err) {
                        setMsg({ ok: false, text: err.message });
                      }
                    }}
                    className="btn-secondary text-blue-600">
                    {a.oauth_connected ? "Revincular Microsoft" : "Vincular Microsoft"}
                  </button>
                )}
                <button onClick={() => act(api.testAccount, a.id, "Conexión OK")}
                  className="btn-secondary">Probar</button>
                <button onClick={() => act(api.syncAccount, a.id, "Escaneo encolado")}
                  className="btn-secondary">Sincronizar</button>
                <button
                  onClick={() => act((id) => api.updateAccount(id, { is_enabled: !a.is_enabled }), a.id, "Actualizado")}
                  className="btn-secondary">
                  {a.is_enabled ? "Pausar" : "Activar"}
                </button>
                <button
                  onClick={() => confirm(`¿Eliminar ${a.email}?`) && act(api.deleteAccount, a.id, "Eliminada")}
                  className="btn-secondary text-rose-600 hover:bg-rose-50">
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

const inp = "input";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{label}</span>
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
