import { useMemo, useState } from "react";
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
