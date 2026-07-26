import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowRight, BellRing, Eye, EyeOff,
  LockKeyhole, Mail, ShieldCheck, Sparkles,
} from "lucide-react";
import { api } from "../lib/api";

const benefits = [
  { icon: ShieldCheck, title: "Supervisa", text: "Monitoriza todas tus cuentas de correo en tiempo real." },
  { icon: BellRing, title: "Detecta", text: "Recibe alertas ante incidencias o pagos fallidos." },
  { icon: Activity, title: "Actúa", text: "Toma acción inmediata antes de que se suspenda el servicio." },
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

  return <main className="login-reference">
    <div className="login-reference-grid" aria-hidden="true" />
    <header className="login-reference-header">
      <div className="login-reference-brand">
        <span><Mail size={17} /></span>
        <div><strong>Mail Control</strong><small>Centro operativo</small></div>
      </div>
      <div className="login-reference-status"><i /> Estado de los servicios</div>
    </header>

    <section className="login-reference-main">
      <div className="login-reference-story">
        <div className="login-reference-copy">
          <span className="login-reference-eyebrow"><Sparkles size={12} /> Inteligencia para tu operación</span>
          <h1>Tu correo deja<br />de ser ruido.<br /><em>Se convierte en<br />control.</em></h1>
          <p>Supervisa cuentas, detecta incidencias de suscripción y actúa antes de que un pago interrumpa el servicio.</p>
        </div>

        <div className="login-envelope-scene" aria-hidden="true">
          <span className="login-orbit orbit-one" />
          <span className="login-orbit orbit-two" />
          <div className="login-envelope-back" />
          <div className="login-envelope"><Mail size={34} /></div>
          <span className="login-data-card card-one"><BellRing size={14} /></span>
          <span className="login-data-card card-two"><ShieldCheck size={14} /></span>
        </div>

        <div className="login-benefits">
          {benefits.map(({ icon: Icon, title, text }) => <article key={title}>
            <span><Icon size={16} /></span><h2>{title}</h2><p>{text}</p><i><ArrowRight size={12} /></i>
          </article>)}
        </div>
      </div>

      <aside className="login-reference-access">
        <div className="login-access-card">
          <span className="login-access-icon"><Mail size={24} /></span>
          <span className="login-access-kicker">ACCESO SEGURO</span>
          <h2>Bienvenido de nuevo</h2>
          <p>Ingresa a tu espacio de trabajo para continuar.</p>

          <form onSubmit={submit} className="login-reference-form">
            <label><span>Correo electrónico</span><div><Mail size={15} /><input type="email" inputMode="email" autoComplete="username" required aria-invalid={Boolean(error)} value={email} onChange={(event) => { setEmail(event.target.value); if (error) setError(""); }} placeholder="nombre@empresa.com" /></div></label>
            <label><span>Contraseña</span><div><LockKeyhole size={15} /><input type={showPassword ? "text" : "password"} autoComplete="current-password" required aria-invalid={Boolean(error)} value={password} onChange={(event) => { setPassword(event.target.value); if (error) setError(""); }} placeholder="Ingresa tu contraseña" /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>{showPassword ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></label>
            <div className={`login-reference-error ${error ? "is-visible" : ""}`} role="alert">{error && <><AlertTriangle size={14} /> {error}</>}</div>
            <button className="login-reference-submit" disabled={loading || !email.trim() || !password}><span>{loading ? "Verificando acceso" : "Entrar a Mail Control"}</span>{loading ? <i /> : <ArrowRight size={15} />}</button>
          </form>

          <div className="login-reference-trust"><ShieldCheck size={13} /> Tus datos están protegidos y cifrados</div>
        </div>
      </aside>
    </section>

    <footer className="login-reference-footer"><span><LockKeyhole size={12} /> Sistema seguro y cifrado</span><span>Todos los derechos reservados</span></footer>
  </main>;
}
