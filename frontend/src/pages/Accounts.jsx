import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MailPlus, MoreHorizontal, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { EmptyState, InlineLoading, Notice, PageHeader, StatusBadge } from "../components/ui";

const EMPTY = { email: "", provider: "outlook", imap_host: "outlook.office365.com", imap_port: 993, imap_user: "", password: "" };
const PRESETS = { outlook: "outlook.office365.com", hotmail: "outlook.office365.com", gmail: "imap.gmail.com", custom: "" };

export default function Accounts() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = () => { setLoading(true); api.accounts().then(setAccounts).catch((error) => setMessage({ tone: "error", text: error.message })).finally(() => setLoading(false)); };
  useEffect(() => {
    load();
    const oauth = searchParams.get("oauth");
    if (oauth === "connected") setMessage({ tone: "success", text: "La cuenta Microsoft se vinculó correctamente mediante OAuth2." });
    if (oauth === "error") setMessage({ tone: "error", text: searchParams.get("detail") || "Microsoft rechazó la autorización." });
    if (oauth) setSearchParams({}, { replace: true });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setField = (field, value) => setForm((current) => {
    const next = { ...current, [field]: value };
    if (field === "provider") next.imap_host = PRESETS[value] ?? "";
    return next;
  });

  const submit = async (event) => {
    event.preventDefault(); setSaving(true); setMessage(null);
    try {
      const account = await api.createAccount(form);
      if (["outlook", "hotmail"].includes(form.provider)) {
        const { authorization_url } = await api.authorizeMicrosoft(account.id);
        window.location.assign(authorization_url); return;
      }
      setForm(EMPTY); setMessage({ tone: "success", text: "La cuenta se agregó y su primera sincronización fue programada." }); load();
    } catch (error) { setMessage({ tone: "error", text: error.message }); } finally { setSaving(false); }
  };

  const act = async (id, operation, successText) => {
    setBusyId(id); setMessage(null);
    try { await operation(id); setMessage({ tone: "success", text: successText }); load(); }
    catch (error) { setMessage({ tone: "error", text: error.message }); }
    finally { setBusyId(null); }
  };

  const reconnectMicrosoft = async (id) => {
    setBusyId(id);
    try { const { authorization_url } = await api.authorizeMicrosoft(id); window.location.assign(authorization_url); }
    catch (error) { setMessage({ tone: "error", text: error.message }); setBusyId(null); }
  };

  const microsoft = ["outlook", "hotmail"].includes(form.provider);

  const connected = accounts.filter((account) => account.last_status === "ok" && account.is_enabled).length;
  const failed = accounts.filter((account) => account.last_status === "error").length;
  const pending = Math.max(0, accounts.length - connected - failed);

  return <div className="accounts-page mx-auto max-w-6xl space-y-6 p-4 md:p-7">
    <PageHeader eyebrow="Infraestructura de correo" title="Cuentas conectadas" description="Conecta y supervisa las bandejas que Mail Control debe sincronizar." />
    {message && <Notice tone={message.tone}>{message.text}</Notice>}
    <div className="accounts-kpis">
      <AccountKpi tone="violet" label="Total de cuentas" value={accounts.length} detail="Bandejas registradas" />
      <AccountKpi tone="green" label="Conectadas" value={connected} detail="Sincronización activa" />
      <AccountKpi tone="red" label="Con error" value={failed} detail="Requieren revisión" />
      <AccountKpi tone="amber" label="Pendientes" value={pending} detail="Esperando validación" />
    </div>
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="panel order-1">
        <div className="border-b border-slate-200 px-5 py-3 dark:border-slate-800"><h2 className="text-sm font-semibold text-slate-900 dark:text-white">Cuentas ({accounts.length})</h2></div>
        {loading ? <div className="p-5 text-sm text-slate-500">Cargando cuentas…</div> : !accounts.length ? <EmptyState icon={MailPlus} title="No hay cuentas conectadas" description="Usa el formulario para conectar Outlook, Hotmail, Gmail u otro proveedor IMAP." /> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{accounts.map((account) => <AccountRow key={account.id} account={account} busy={busyId === account.id} onSync={() => act(account.id, api.syncAccount, "La sincronización fue programada.")} onTest={() => act(account.id, api.testAccount, "La conexión funciona correctamente.")} onToggle={() => act(account.id, (id) => api.updateAccount(id, { is_enabled: !account.is_enabled }), account.is_enabled ? "La cuenta quedó pausada." : "La cuenta quedó activa.")} onReconnect={() => reconnectMicrosoft(account.id)} onDelete={() => window.confirm(`¿Desconectar ${account.email}? Los mensajes guardados de esta cuenta se eliminarán.`) && act(account.id, api.deleteAccount, "La cuenta fue desconectada.")} />)}</div>}
      </section>
      <form onSubmit={submit} className="panel order-2 self-start p-5">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Conectar una cuenta</h2>
        <p className="mt-1 text-sm leading-5 text-slate-500">Microsoft usa autorización OAuth2. Gmail requiere una contraseña de aplicación.</p>
        <div className="mt-5 space-y-4">
          <Field label="Proveedor"><select className="input" value={form.provider} onChange={(event) => setField("provider", event.target.value)}><option value="outlook">Outlook / Microsoft 365</option><option value="hotmail">Hotmail</option><option value="gmail">Gmail</option><option value="custom">Otro proveedor IMAP</option></select></Field>
          <Field label="Correo electrónico"><input className="input" type="email" required value={form.email} onChange={(event) => setField("email", event.target.value)} /></Field>
          {!microsoft && <Field label="Contraseña de aplicación"><input className="input" type="password" required value={form.password} onChange={(event) => setField("password", event.target.value)} /></Field>}
          <details className="account-advanced border-t border-slate-200 pt-3 dark:border-slate-800"><summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">Configuración IMAP avanzada</summary><div className="mt-4 space-y-4"><Field label="Servidor IMAP"><input className="input" required value={form.imap_host} onChange={(event) => setField("imap_host", event.target.value)} /></Field><Field label="Puerto"><input className="input" type="number" value={form.imap_port} onChange={(event) => setField("imap_port", Number(event.target.value))} /></Field><Field label="Usuario IMAP (opcional)"><input className="input" value={form.imap_user} placeholder="Se usará el correo si está vacío" onChange={(event) => setField("imap_user", event.target.value)} /></Field></div></details>
          <button disabled={saving} className="btn-primary w-full">{saving ? <InlineLoading label="Conectando" /> : microsoft ? "Continuar con Microsoft" : "Conectar cuenta"}</button>
        </div>
      </form>
    </div>
  </div>;
}

function AccountKpi({ tone, label, value, detail }) {
  return <article className={`account-kpi is-${tone}`}>
    <small>{label}</small><strong>{value}</strong><p>{detail}</p><i><em /></i>
  </article>;
}

function AccountRow({ account, busy, onSync, onTest, onToggle, onReconnect, onDelete }) {
  const microsoft = ["outlook", "hotmail"].includes(account.provider);
  const status = account.last_status === "ok" ? "ok" : account.last_status === "error" ? "error" : "neutral";
  const label = account.last_status === "ok" ? "Conectada" : account.last_status === "error" ? "Error de conexión" : "Pendiente";
  return <article className="account-row p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-start"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="truncate text-sm font-semibold text-slate-900 dark:text-white">{account.email}</h3><StatusBadge status={status}>{label}</StatusBadge>{!account.is_enabled && <StatusBadge status="neutral">Pausada</StatusBadge>}</div><p className="mt-1 text-xs text-slate-500">{account.provider} · {account.imap_host}:{account.imap_port}</p>{account.last_synced_at && <p className="mt-1 text-xs text-slate-400">Última sincronización: {new Date(account.last_synced_at).toLocaleString()}</p>}{account.last_error && <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{account.last_error}</p>}</div><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={onSync} className="btn-secondary"><RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Sincronizar</button>{microsoft && <button disabled={busy} onClick={onReconnect} className="btn-secondary">{account.oauth_connected ? "Renovar acceso" : "Autorizar Microsoft"}</button>}<details className="account-actions relative"><summary aria-label="Más acciones" className="btn-secondary cursor-pointer list-none px-2.5"><MoreHorizontal size={16} /></summary><div className="absolute right-0 z-10 mt-1 w-44 border border-slate-200 bg-white p-1 shadow-panel dark:border-slate-700 dark:bg-slate-900"><button onClick={onTest} className="btn-quiet w-full justify-start">Probar conexión</button><button onClick={onToggle} className="btn-quiet w-full justify-start">{account.is_enabled ? "Pausar cuenta" : "Activar cuenta"}</button><button onClick={onDelete} className="btn-quiet w-full justify-start text-rose-700 dark:text-rose-300"><Trash2 size={14} /> Desconectar</button></div></details></div></div></article>;
}

function Field({ label, children }) { return <label className="block"><span className="label">{label}</span>{children}</label>; }
