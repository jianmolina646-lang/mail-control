import { FormEvent, useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Activity, ArrowRight, AtSign, BellRing, Building2, Eye, EyeOff,
  CheckCircle2, KeyRound, Loader2, Lock, Mail, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { GmailLogo, OutlookLogo } from "@/components/mail/brand-logos";
import { api, clearSession, saveSession } from "@/lib/api";
import type { TokenPair } from "@/lib/types";

export function LoginManager() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [tenant, setTenant] = useState("");
  const [email, setEmail] = useState("");
  const [recoveryOpen, setRecoveryOpen] = useState(false);
  const [recoverySent, setRecoverySent] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [recoveryError, setRecoveryError] = useState("");
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const login = useMutation({
    mutationFn: (body: { tenant_slug: string; email: string; password: string }) =>
      api<TokenPair>("/v1/auth/login", { method: "POST", body: JSON.stringify(body) }, false),
    onSuccess: (tokens) => { saveSession(tokens); navigate("/", { replace: true }); },
    onError: (reason: Error) => setError(reason.message),
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticket = params.get("ticket");
    const oauthError = params.get("oauth_error");
    if (oauthError) setError("No se pudo iniciar sesión con esa cuenta. Verifica que pertenezca al workspace.");
    if (!ticket) return;
    api<TokenPair>("/v1/auth/oauth/exchange", { method: "POST", body: JSON.stringify({ ticket }) }, false)
      .then((tokens) => { saveSession(tokens); navigate("/", { replace: true }); })
      .catch((reason: Error) => setError(reason.message));
  }, [navigate]);

  async function socialLogin(provider: "google" | "microsoft") {
    if (!tenant.trim()) { setError("Escribe primero el workspace."); return; }
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(`/v1/auth/oauth/${provider}/authorize`, { method: "POST", body: JSON.stringify({ tenant_slug: tenant.trim().toLowerCase() }) }, false);
      window.location.assign(result.authorization_url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo iniciar OAuth."); }
  }

  async function requestRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setRecoveryBusy(true); setRecoveryError("");
    try { await api("/v1/auth/password/request", { method: "POST", body: JSON.stringify({ tenant_slug: tenant.trim().toLowerCase(), email: email.trim().toLowerCase() }) }, false); setRecoverySent(true); }
    catch (reason) { setRecoveryError(reason instanceof Error ? reason.message : "No se pudo enviar el código."); }
    finally { setRecoveryBusy(false); }
  }

  async function confirmRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setRecoveryBusy(true); setRecoveryError("");
    try { await api("/v1/auth/password/confirm", { method: "POST", body: JSON.stringify({ tenant_slug: tenant.trim().toLowerCase(), email: email.trim().toLowerCase(), code: recoveryCode, password: newPassword }) }, false); setRecoveryOpen(false); setRecoverySent(false); setError("Contraseña actualizada. Ya puedes iniciar sesión."); }
    catch (reason) { setRecoveryError(reason instanceof Error ? reason.message : "El código no es válido."); }
    finally { setRecoveryBusy(false); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    clearSession();
    const data = new FormData(event.currentTarget);
    login.mutate({
      tenant_slug: String(data.get("tenant")).trim().toLowerCase(),
      email: String(data.get("email")).trim().toLowerCase(),
      password: String(data.get("password")),
    });
  }

  return (
    <main className="sleek-mail clear-login min-h-screen bg-background font-sans text-foreground lg:grid lg:grid-cols-[1.1fr_1fr]">
      <section className="relative isolate flex min-h-[100dvh] flex-col justify-between overflow-hidden px-8 py-10 sm:px-14 lg:py-14">
        <div aria-hidden className="absolute inset-0 -z-10" style={{ background: "radial-gradient(110% 80% at 8% 4%, color-mix(in oklab, var(--primary) 26%, transparent), transparent 62%), radial-gradient(90% 70% at 96% 96%, var(--accent), transparent 60%), var(--background)" }} />
        <div aria-hidden className="absolute inset-0 -z-10 opacity-50" style={{ backgroundImage: "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)", backgroundSize: "80px 80px", maskImage: "radial-gradient(130% 100% at 10% 0%, black, transparent 72%)" }} />

        <header className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm"><Mail className="size-5" /></span>
          <div className="leading-tight"><p className="font-display text-base font-bold tracking-tight">Mail Control</p><p className="text-[10px] font-semibold tracking-[0.2em] text-primary">ENTERPRISE</p></div>
        </header>

        <div className="my-12 max-w-xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-card/70 px-3.5 py-1.5 text-[11px] font-bold tracking-wide text-primary backdrop-blur"><Sparkles className="size-3.5" />Clasificación automática con IA</span>
          <h1 className="mt-6 font-display text-[2.6rem] font-extrabold leading-[0.98] tracking-tight sm:text-6xl">La operación<br />de correo,<br /><span className="bg-gradient-to-r from-primary to-foreground bg-clip-text text-transparent">bajo control.</span></h1>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">Supervisa cuentas, detecta incidencias y actúa antes de que un problema afecte a tus clientes.</p>
          <div className="mt-9 grid max-w-lg gap-3 sm:grid-cols-3">
            <Proof icon={Activity} value="6.7k" label="Mensajes analizados" />
            <Proof icon={BellRing} value="98%" label="Alertas resueltas" />
            <Proof icon={ShieldCheck} value="21" label="Cuentas activas" />
          </div>
        </div>

        <footer className="flex flex-wrap items-center gap-x-5 gap-y-3 text-[11px] font-semibold text-muted-foreground"><span className="inline-flex items-center gap-2"><GmailLogo className="size-4" /> Gmail</span><span className="inline-flex items-center gap-2"><OutlookLogo className="size-4" /> Outlook</span><span className="h-4 w-px bg-border" /><span>OAuth seguro · Datos aislados · Auditoría por distribuidor</span></footer>
      </section>

      <section className="flex items-center justify-center border-border/70 px-6 py-12 lg:min-h-[100dvh] lg:border-l lg:bg-card/40 lg:px-12 lg:backdrop-blur">
        <div className="w-full max-w-md">
          <div className="rounded-[1.75rem] border border-border/80 bg-card p-7 shadow-sm sm:p-9">
            <form onSubmit={submit} className="space-y-6">
              <div><p className="text-[10px] font-semibold tracking-[0.2em] text-primary">ACCESO AL WORKSPACE</p><h2 className="mt-2.5 font-display text-[1.7rem] font-bold leading-tight tracking-tight">Iniciar sesión</h2><p className="mt-1.5 text-sm text-muted-foreground">Usa las credenciales de tu distribuidor.</p></div>
              <div className="grid grid-cols-2 gap-3"><ProviderButton logo={<GmailLogo className="size-4" />} label="Google" onClick={() => socialLogin("google")} /><ProviderButton logo={<OutlookLogo className="size-4" />} label="Microsoft" onClick={() => socialLogin("microsoft")} /></div>
              <div className="flex items-center gap-3"><span className="h-px flex-1 bg-border" /><span className="text-[10px] font-semibold tracking-[0.18em] text-muted-foreground">O CON TU CORREO</span><span className="h-px flex-1 bg-border" /></div>
              <div className="space-y-4">
                <Field label="WORKSPACE" icon={Building2}><input name="tenant" value={tenant} onChange={(event) => setTenant(event.target.value)} placeholder="mi-distribuidor" autoComplete="organization" required className="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none placeholder:font-normal placeholder:text-muted-foreground" /></Field>
                <Field label="CORREO" icon={AtSign}><input name="email" value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" required className="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none placeholder:text-muted-foreground" /></Field>
                <Field label="CONTRASEÑA" icon={Lock}><input name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required className="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none" /><button type="button" onClick={() => setShowPassword((value) => !value)} className="shrink-0 rounded-lg p-1 text-muted-foreground hover:text-foreground" aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></Field>
              </div>
              <div className="flex items-center justify-between gap-3"><label className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground"><input type="checkbox" className="size-4 rounded-md border-border accent-[var(--primary)]" />Mantener sesión activa</label><button type="button" onClick={() => { setRecoveryOpen(true); setRecoveryError(""); }} className="text-xs font-bold text-primary hover:underline">¿Olvidaste tu contraseña?</button></div>
              {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive" role="alert">{error}</p>}
              <button type="submit" disabled={login.isPending} className="group inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-4 text-sm font-bold text-primary-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:opacity-95 disabled:opacity-70">{login.isPending && <Loader2 className="size-4 animate-spin" />}{login.isPending ? "Verificando…" : "Entrar al workspace"}{!login.isPending && <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />}</button>
            </form>
          </div>
          <p className="mt-5 text-center text-[11px] text-muted-foreground">Protegido con cifrado en tránsito y registro de auditoría por cuenta.</p>
        </div>
      </section>
      {recoveryOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-foreground/20 p-5 backdrop-blur-sm"><div className="relative w-full max-w-md rounded-[1.75rem] border border-border bg-card p-7 shadow-xl sm:p-9"><button type="button" onClick={() => setRecoveryOpen(false)} aria-label="Cerrar" className="absolute right-5 top-5 grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-secondary"><X className="size-4" /></button>{!recoverySent ? <form onSubmit={requestRecovery} className="space-y-5"><KeyRound className="size-7 text-primary" /><div><p className="text-[10px] font-semibold tracking-[.2em] text-primary">RECUPERAR ACCESO</p><h2 className="mt-2 text-2xl font-bold">Olvidé mi contraseña</h2><p className="mt-2 text-sm text-muted-foreground">Enviaremos un código de seis dígitos al correo registrado.</p></div><Field label="WORKSPACE" icon={Building2}><input value={tenant} onChange={(event) => setTenant(event.target.value)} required className="min-w-0 flex-1 bg-transparent text-sm outline-none" /></Field><Field label="CORREO" icon={AtSign}><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required className="min-w-0 flex-1 bg-transparent text-sm outline-none" /></Field>{recoveryError && <p className="text-xs text-destructive">{recoveryError}</p>}<button disabled={recoveryBusy} className="flex w-full items-center justify-center rounded-2xl bg-primary px-5 py-4 text-sm font-bold text-primary-foreground">{recoveryBusy ? "Enviando…" : "Enviar código"}</button></form> : <form onSubmit={confirmRecovery} className="space-y-5"><CheckCircle2 className="size-8 text-primary" /><div><p className="text-[10px] font-semibold tracking-[.2em] text-primary">CÓDIGO ENVIADO</p><h2 className="mt-2 text-2xl font-bold">Revisa tu correo</h2><p className="mt-2 text-sm text-muted-foreground">Caduca en 10 minutos y solo puede utilizarse una vez.</p></div><Field label="CÓDIGO DE 6 DÍGITOS" icon={KeyRound}><input value={recoveryCode} onChange={(event) => setRecoveryCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" pattern="[0-9]{6}" required className="min-w-0 flex-1 bg-transparent text-sm tracking-[.3em] outline-none" /></Field><Field label="CONTRASEÑA NUEVA" icon={Lock}><input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} type="password" minLength={12} required className="min-w-0 flex-1 bg-transparent text-sm outline-none" /></Field>{recoveryError && <p className="text-xs text-destructive">{recoveryError}</p>}<button disabled={recoveryBusy} className="flex w-full items-center justify-center rounded-2xl bg-primary px-5 py-4 text-sm font-bold text-primary-foreground">{recoveryBusy ? "Actualizando…" : "Cambiar contraseña"}</button></form>}</div></div>}
    </main>
  );
}

function Field({ label, icon: Icon, children }: { label: string; icon: typeof Mail; children: React.ReactNode }) {
  return <label className="group block"><span className="text-[10px] font-semibold tracking-[0.2em] text-muted-foreground">{label}</span><span className="mt-2 flex items-center gap-2.5 rounded-2xl border border-border/80 bg-secondary/50 px-4 py-3.5 transition-all focus-within:border-primary/60 focus-within:bg-card focus-within:ring-4 focus-within:ring-primary/10"><Icon className="size-4 shrink-0 text-muted-foreground group-focus-within:text-primary" />{children}</span></label>;
}

function Proof({ icon: Icon, value, label }: { icon: typeof Activity; value: string; label: string }) {
  return <div className="rounded-2xl border border-border/70 bg-card/70 p-4 backdrop-blur-md transition-transform hover:-translate-y-1"><Icon className="size-4 text-primary" /><p className="mt-3 font-display text-2xl font-bold leading-none">{value}</p><p className="mt-1.5 text-[11px] font-medium text-muted-foreground">{label}</p></div>;
}

function ProviderButton({ logo, label, onClick }: { logo: React.ReactNode; label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-border bg-background px-3 py-3 text-xs font-bold transition-colors hover:bg-secondary">{logo}{label}</button>;
}
