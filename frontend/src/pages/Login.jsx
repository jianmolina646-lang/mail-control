import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Inbox,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "../lib/api";

const signalItems = [
  { icon: Inbox, label: "Bandeja unificada", meta: "Mensajes organizados", tone: "indigo" },
  { icon: AlertTriangle, label: "Alertas críticas", meta: "Pagos bajo vigilancia", tone: "amber" },
  { icon: Activity, label: "Sincronización", meta: "Cuentas supervisadas", tone: "emerald" },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.login(email.trim(), password);
      navigate("/");
    } catch (err) {
      setError(err.message || "No pudimos iniciar sesión. Revisa tus datos e inténtalo de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-shell">
      <section className="login-story" aria-label="Mail Control">
        <div className="login-grid" aria-hidden="true" />
        <div className="login-glow login-glow-one" aria-hidden="true" />
        <div className="login-glow login-glow-two" aria-hidden="true" />

        <header className="login-brand">
          <span className="login-brand-mark"><Mail size={18} strokeWidth={2.2} /></span>
          <span>Mail Control</span>
          <span className="login-brand-divider" aria-hidden="true" />
          <span className="login-brand-caption">Centro operativo</span>
        </header>

        <div className="login-story-copy">
          <div className="login-eyebrow"><Sparkles size={14} /> Inteligencia para tu operación</div>
          <h1>Tu correo deja de ser ruido.<br /><span>Se convierte en control.</span></h1>
          <p>
            Supervisa cuentas, detecta incidencias de suscripción y actúa antes de que un pago interrumpa el servicio.
          </p>
        </div>

        <div className="signal-stage" aria-label="Vista conceptual de la actividad operativa">
          <div className="signal-orbit signal-orbit-one" aria-hidden="true" />
          <div className="signal-orbit signal-orbit-two" aria-hidden="true" />
          <div className="signal-core">
            <span className="signal-core-pulse" aria-hidden="true" />
            <Mail size={23} />
          </div>
          <span className="signal-path signal-path-a" aria-hidden="true" />
          <span className="signal-path signal-path-b" aria-hidden="true" />
          <span className="signal-path signal-path-c" aria-hidden="true" />

          <div className="signal-stack">
            {signalItems.map(({ icon: Icon, label, meta, tone }, index) => (
              <div className="signal-item" style={{ "--signal-delay": `${index * 120}ms` }} key={label}>
                <span className={`signal-icon signal-${tone}`}><Icon size={16} /></span>
                <span><strong>{label}</strong><small>{meta}</small></span>
                <span className={`signal-status signal-${tone}`}><Check size={11} /> Activo</span>
              </div>
            ))}
          </div>
        </div>

        <footer className="login-story-footer">
          <span><ShieldCheck size={15} /> Acceso privado y cifrado</span>
          <span className="login-live"><i aria-hidden="true" /> Sistema operativo</span>
        </footer>
      </section>

      <section className="login-access">
        <div className="login-mobile-brand">
          <span className="login-brand-mark"><Mail size={18} /></span>
          <strong>Mail Control</strong>
        </div>

        <div className="login-form-wrap">
          <div className="login-form-heading">
            <span className="login-step">ACCESO SEGURO</span>
            <h2>Bienvenido de nuevo</h2>
            <p>Ingresa a tu espacio de trabajo para continuar.</p>
          </div>

          <form onSubmit={submit} className="login-form">
            <label className="login-field">
              <span>Correo electrónico</span>
              <span className="login-input-wrap">
                <Mail aria-hidden="true" size={18} />
                <input
                  type="email"
                  inputMode="email"
                  autoComplete="username"
                  placeholder="nombre@empresa.com"
                  required
                  aria-invalid={Boolean(error)}
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (error) setError("");
                  }}
                />
              </span>
            </label>

            <label className="login-field">
              <span>Contraseña</span>
              <span className="login-input-wrap">
                <LockKeyhole aria-hidden="true" size={18} />
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Ingresa tu contraseña"
                  required
                  aria-invalid={Boolean(error)}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) setError("");
                  }}
                />
                <button
                  className="login-password-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={showPassword}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
            </label>

            <div className={`login-message ${error ? "is-visible" : ""}`} role="alert" aria-live="polite">
              {error && <><AlertTriangle size={16} /><span>{error}</span></>}
            </div>

            <button disabled={loading || !email.trim() || !password} className="login-submit">
              <span>{loading ? "Verificando acceso" : "Entrar a Mail Control"}</span>
              {loading ? <span className="login-spinner" aria-hidden="true" /> : <ArrowRight size={18} />}
            </button>
          </form>

          <div className="login-trust">
            <ShieldCheck size={15} />
            <span>Tus credenciales viajan por una conexión segura.</span>
          </div>
        </div>

        <p className="login-copyright">© {new Date().getFullYear()} Mail Control · Operación de correo centralizada</p>
      </section>
    </main>
  );
}
