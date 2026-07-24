import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, LockKeyhole, Mail, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault(); setError(""); setLoading(true);
    try { await api.login(email, password); nav("/"); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="app-background grid min-h-screen bg-slate-50 dark:bg-slate-950 lg:grid-cols-2">
      <section className="hidden overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-violet-700 shadow-glow"><Mail size={22} /></span><div><strong className="block">Mail Control</strong><small className="uppercase tracking-[.2em] text-brand-200">Team Jheliz</small></div></div>
        <div className="max-w-xl">
          <span className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10"><ShieldCheck size={24} /></span>
          <h1 className="text-4xl font-bold leading-tight">Tu centro de operaciones para cada conversación.</h1>
          <p className="mt-5 text-lg leading-7 text-slate-400">Correo, alertas y cuentas en un espacio seguro diseñado para trabajar más rápido.</p>
        </div>
        <p className="text-xs text-slate-500">Acceso empresarial protegido · Mail Control</p>
      </section>
      <section className="flex items-center justify-center p-5">
        <form onSubmit={submit} className="glass w-full max-w-md rounded-3xl p-7 md:p-9">
          <div className="mb-8 lg:hidden"><span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-glow"><Mail size={23} /></span></div>
          <p className="text-sm font-semibold text-brand-600">Bienvenido de nuevo</p>
          <h2 className="mt-1 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Inicia sesión</h2>
          <p className="mt-2 text-sm text-slate-500">Ingresa tus credenciales para continuar.</p>
          <div className="mt-7 space-y-4">
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-slate-300">Correo electrónico</span><span className="relative block"><Mail className="absolute left-3.5 top-3 text-slate-400" size={17} /><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="input pl-11" placeholder="admin@empresa.com" /></span></label>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-slate-300">Contraseña</span><span className="relative block"><LockKeyhole className="absolute left-3.5 top-3 text-slate-400" size={17} /><input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input pl-11" placeholder="••••••••••••" /></span></label>
          </div>
          {error && <div className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-600 dark:bg-rose-500/10 dark:text-rose-300">{error}</div>}
          <button disabled={loading} className="btn-primary mt-6 w-full py-3">{loading ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Entrando…</> : <>Entrar al panel <ArrowRight size={17} /></>}</button>
        </form>
      </section>
    </div>
  );
}
