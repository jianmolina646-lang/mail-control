import { useEffect, useMemo, useState } from "react";
import {
  Activity, Bell, Check, ChevronRight, Circle, KeyRound, LockKeyhole,
  MonitorSmartphone, ShieldCheck, SlidersHorizontal, UserRoundCog,
} from "lucide-react";
import { api } from "../lib/api";
import { InlineLoading, Notice } from "../components/ui";

const settingsSections = [
  { label: "Contraseña", icon: LockKeyhole, active: true },
  { label: "Sesiones activas", icon: MonitorSmartphone },
  { label: "Autenticación 2FA", icon: ShieldCheck },
  { label: "Notificaciones", icon: Bell },
  { label: "Preferencias", icon: SlidersHorizontal },
  { label: "Actividad reciente", icon: Activity },
];

export default function Security() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [twoFactor, setTwoFactor] = useState({ enabled: false });
  const [setup, setSetup] = useState(null);
  const [twoFactorPassword, setTwoFactorPassword] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState([]);

  useEffect(() => {
    api.twoFactorStatus().then(setTwoFactor).catch(() => {});
  }, []);

  const beginTwoFactor = async () => {
    setSaving(true); setMessage(null);
    try {
      setSetup(await api.setupTwoFactor(twoFactorPassword));
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally { setSaving(false); }
  };

  const confirmTwoFactor = async () => {
    setSaving(true); setMessage(null);
    try {
      const result = await api.confirmTwoFactor(twoFactorCode);
      setTwoFactor({ enabled: true });
      setRecoveryCodes(result.recovery_codes);
      setSetup(null); setTwoFactorCode(""); setTwoFactorPassword("");
      setMessage({ tone: "success", text: "Google Authenticator quedó activado." });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally { setSaving(false); }
  };

  const disableTwoFactor = async () => {
    setSaving(true); setMessage(null);
    try {
      await api.disableTwoFactor(twoFactorPassword, twoFactorCode);
      setTwoFactor({ enabled: false });
      setTwoFactorPassword(""); setTwoFactorCode(""); setRecoveryCodes([]);
      setMessage({ tone: "success", text: "La autenticación en dos pasos fue desactivada." });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally { setSaving(false); }
  };

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
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  return <div className="security-page">
    <header className="security-heading">
      <span>ADMINISTRACIÓN</span>
      <h1>Configuración</h1>
      <p>Seguridad y preferencias de acceso al panel.</p>
    </header>
    {message && <Notice tone={message.tone}>{message.text}</Notice>}

    <div className="security-layout">
      <nav className="security-nav" aria-label="Secciones de configuración">
        {settingsSections.map(({ label, icon: Icon, active }) =>
          <button type="button" key={label} className={active ? "is-active" : ""} disabled={!active}>
            <Icon size={15} /><span>{label}</span>{active && <ChevronRight size={14} />}
          </button>
        )}
      </nav>

      <section className="security-content">
        <form onSubmit={submit} className="security-card">
          <div className="security-card-heading">
            <span><KeyRound size={17} /></span>
            <div><h2>Cambiar contraseña</h2><p>Esta contraseña protege el acceso administrativo a Mail Control.</p></div>
          </div>
          <div className="security-form">
            <Field label="Contraseña actual"><input className="input" type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} placeholder="Ingresa tu contraseña actual" /></Field>
            <Field label="Nueva contraseña"><input className="input" type="password" autoComplete="new-password" required value={next} onChange={(event) => setNext(event.target.value)} placeholder="Ingresa una contraseña segura" /></Field>
            <Field label="Confirmar nueva contraseña"><input className="input" type="password" autoComplete="new-password" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="Confirma la nueva contraseña" /></Field>
            <ul className="security-checks">{checks.map((check) =>
              <li key={check.label} className={check.ok ? "is-valid" : ""}>
                {check.ok ? <Check size={12} /> : <Circle size={10} />}{check.label}
              </li>
            )}</ul>
            <div className="security-submit-row">
              <button disabled={!valid || saving} className="btn-primary">
                <LockKeyhole size={14} />{saving ? <InlineLoading label="Actualizando" /> : "Actualizar contraseña"}
              </button>
            </div>
          </div>
        </form>

        <section className="security-card">
          <div className="security-card-heading">
            <span><ShieldCheck size={17} /></span>
            <div><h2>Google Authenticator</h2><p>Segundo factor TOTP para proteger cada inicio de sesión.</p></div>
          </div>
          <div className="security-form">
            {twoFactor.enabled ? <div className="security-2fa-enabled">
              <p className="security-2fa-status"><Check size={15} /> Autenticación en dos pasos activa</p>
              <p>Para desactivarla, confirma tu contraseña y un código actual de Google Authenticator.</p>
              <Field label="Contraseña actual"><input className="input" type="password" autoComplete="current-password" value={twoFactorPassword} onChange={(event) => setTwoFactorPassword(event.target.value)} /></Field>
              <Field label="Código de 6 dígitos"><input className="input" inputMode="numeric" autoComplete="one-time-code" value={twoFactorCode} onChange={(event) => setTwoFactorCode(event.target.value)} /></Field>
              <button type="button" className="btn-secondary security-disable-2fa" disabled={!twoFactorPassword || twoFactorCode.length < 6 || saving} onClick={disableTwoFactor}>Desactivar 2FA</button>
            </div> : <>
              {!setup ? <>
                <Field label="Confirma tu contraseña actual"><input className="input" type="password" autoComplete="current-password" value={twoFactorPassword} onChange={(event) => setTwoFactorPassword(event.target.value)} /></Field>
                <button type="button" className="btn-primary" disabled={!twoFactorPassword || saving} onClick={beginTwoFactor}>Generar código QR</button>
              </> : <div className="security-2fa-setup">
                <img src={setup.qr_data_uri} alt="Código QR para Google Authenticator" />
                <div><strong>Escanea el QR</strong><p>Abre Google Authenticator, pulsa + y escanea este código.</p><code>{setup.secret}</code></div>
                <Field label="Código de 6 dígitos"><input className="input" inputMode="numeric" autoComplete="one-time-code" value={twoFactorCode} onChange={(event) => setTwoFactorCode(event.target.value)} /></Field>
                <button type="button" className="btn-primary" disabled={twoFactorCode.length < 6 || saving} onClick={confirmTwoFactor}>Confirmar y activar</button>
              </div>}
            </>}
            {recoveryCodes.length > 0 && <div className="security-recovery"><strong>Guarda estos códigos de recuperación</strong><p>Cada código funciona una sola vez. No volverán a mostrarse.</p><div>{recoveryCodes.map((code) => <code key={code}>{code}</code>)}</div></div>}
          </div>
        </section>

        <aside className="security-advice">
          <span><UserRoundCog size={18} /></span>
          <div><strong>Protege tu cuenta</strong><p>Mantén una contraseña única y no la compartas con nadie.</p></div>
          <small>Acceso administrativo</small>
        </aside>
      </section>
    </div>
  </div>;
}

function Field({ label, children }) {
  return <label className="security-field"><span>{label}</span>{children}</label>;
}
