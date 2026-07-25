import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LockKeyhole, Mail } from "lucide-react";
import { api } from "../lib/api";
import { InlineLoading, Notice } from "../components/ui";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault(); setError(""); setLoading(true);
    try { await api.login(email, password); navigate("/"); } catch (err) { setError(err.message); } finally { setLoading(false); }
  };

  return <main className="grid min-h-screen bg-white dark:bg-slate-950 lg:grid-cols-[minmax(360px,42%)_1fr]">
    <section className="flex items-center justify-center border-b border-slate-200 bg-slate-950 p-8 text-white lg:border-b-0 lg:border-r lg:p-12">
      <div className="max-w-md">
        <div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-md bg-brand-600"><Mail size={18} /></span><strong>Mail Control</strong></div>
        <h1 className="mt-10 text-3xl font-semibold leading-tight">Control operativo de correo y suscripciones.</h1>
        <p className="mt-4 leading-7 text-slate-400">Centraliza tus cuentas, identifica incidencias de pago y revisa cada mensaje desde un entorno privado.</p>
      </div>
    </section>
    <section className="flex items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm">
        <h2 className="text-2xl font-semibold text-slate-950 dark:text-white">Iniciar sesión</h2>
        <p className="mt-2 text-sm text-slate-500">Accede con la cuenta administradora de Mail Control.</p>
        <div className="mt-7 space-y-4">
          <label><span className="label">Correo electrónico</span><span className="relative block"><Mail className="absolute left-3 top-3 text-slate-400" size={16} /><input className="input pl-9" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></span></label>
          <label><span className="label">Contraseña</span><span className="relative block"><LockKeyhole className="absolute left-3 top-3 text-slate-400" size={16} /><input className="input pl-9" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></span></label>
        </div>
        {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
        <button disabled={loading} className="btn-primary mt-6 w-full">{loading ? <InlineLoading label="Verificando" /> : "Entrar"}</button>
      </form>
    </section>
  </main>;
}
