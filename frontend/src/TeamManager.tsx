import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Moon, PanelLeft, Search, ShieldCheck, Sun, UserPlus, Users } from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, clearSession } from "@/lib/api";
import type { WorkspaceUser } from "@/lib/types";
import { cn } from "@/lib/utils";

type DisplayRole = "Owner" | "Admin" | "Editor" | "Viewer";
type ApiRole = WorkspaceUser["role"];

const roleTone: Record<DisplayRole, string> = {
  Owner: "border-primary/30 bg-primary/10 text-primary",
  Admin: "border-chart-2/30 bg-chart-2/10 text-chart-2",
  Editor: "border-border-strong bg-surface-3/60 text-foreground",
  Viewer: "border-border bg-surface-2 text-muted-foreground",
};

function displayRole(role: ApiRole): DisplayRole {
  return ({ owner: "Owner", admin: "Admin", operator: "Editor", viewer: "Viewer" } as const)[role];
}

function initials(name: string) {
  return name.trim().charAt(0).toUpperCase() || "?";
}

export function TeamManager() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(() => document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const [formError, setFormError] = useState("");
  const query = useQuery({ queryKey: ["workspace-users"], queryFn: () => api<WorkspaceUser[]>("/v1/saas/users") });
  const members = useMemo(() => query.data ?? [], [query.data]);
  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return members;
    return members.filter((member) => [member.display_name, member.email, displayRole(member.role)].some((value) => value.toLowerCase().includes(normalized)));
  }, [members, search]);
  const activeCount = members.filter((member) => member.is_active).length;

  const create = useMutation({
    mutationFn: (body: { display_name: string; email: string; password: string; role: ApiRole }) => api<WorkspaceUser>("/v1/saas/users", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["workspace-users"] }); },
  });
  const update = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api<WorkspaceUser>(`/v1/saas/users/${id}`, { method: "PATCH", body: JSON.stringify({ is_active }) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["workspace-users"] }); },
    onError: (reason: Error) => setFormError(reason.message),
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await create.mutateAsync({
        display_name: String(data.get("display_name") ?? "").trim(),
        email: String(data.get("email") ?? "").trim().toLowerCase(),
        password: String(data.get("password") ?? ""),
        role: String(data.get("role") ?? "viewer") as ApiRole,
      });
      form.reset();
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "No se pudo crear el usuario.");
    }
  }

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
  }

  function logout() {
    clearSession();
    client.clear();
    navigate("/login", { replace: true });
  }

  return (
    <main className="sleek-mail fixed inset-0 z-[70] flex h-[100dvh] min-w-0 overflow-hidden bg-background text-foreground">
      <AppSidebar className="hidden lg:flex" />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="grid shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-b border-border bg-surface/70 px-3 py-2.5 backdrop-blur lg:px-5">
          <div className="flex items-center gap-2">
            <Sheet>
              <SheetTrigger asChild><button type="button" aria-label="Abrir navegación" className="grid size-9 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground lg:hidden"><PanelLeft className="size-4" /></button></SheetTrigger>
              <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0"><SheetTitle className="sr-only">Navegación</SheetTitle><AppSidebar className="w-full border-r-0" /></SheetContent>
            </Sheet>
            <span className="min-w-0"><span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workspace</span><span className="block truncate text-[13px] font-semibold">Equipo</span></span>
          </div>
          <div />
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={toggleTheme} aria-label="Tema" className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground">{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</button>
            <button type="button" onClick={() => navigate("/alertas")} aria-label="Alertas" className="grid size-9 place-items-center rounded-xl border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><Bell className="size-4" /></button>
            <button type="button" onClick={logout} className="flex h-9 items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><LogOut className="size-4" /><span className="hidden sm:inline">Salir</span></button>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-y-auto px-4 py-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-6xl">
            <section className="relative overflow-hidden rounded-3xl border border-border bg-surface/70 p-6 shadow-section lg:p-8">
              <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-full bg-primary/12 blur-3xl" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-primary">Accesos</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight lg:text-4xl">Equipo</h1>
              <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-muted-foreground">Usuarios y permisos aislados dentro de este workspace.</p>
              <div className="mt-5 flex flex-wrap gap-2"><Stat icon={Users} label={`${members.length} usuarios`} /><Stat icon={ShieldCheck} label={`${activeCount} activos`} /><Stat icon={UserPlus} label="Alta inmediata" /></div>
            </section>

            <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] lg:items-start">
              <section className="rounded-3xl border border-border bg-surface/60 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
                  <h2 className="text-[15px] font-semibold tracking-tight">Usuarios</h2>
                  <div className="flex items-center gap-2"><label className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar usuario" aria-label="Buscar usuario" className="h-9 w-44 rounded-xl border border-border bg-surface-2 pl-8 pr-3 text-[12.5px] outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/40 sm:w-56" /></label><span className="grid size-7 place-items-center rounded-lg bg-surface-2 text-[11.5px] font-semibold text-muted-foreground tabular-nums">{filtered.length}</span></div>
                </div>
                {query.isLoading ? <div className="space-y-px">{[0, 1, 2].map((item) => <div key={item} className="h-[65px] animate-pulse border-b border-border/60 bg-surface-2/20" />)}</div> : query.isError ? <button type="button" onClick={() => query.refetch()} className="m-5 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">No se pudieron cargar los usuarios. Reintentar</button> : (
                  <ul className="divide-y divide-border/60">
                    {filtered.map((member) => {
                      const role = displayRole(member.role);
                      return <li key={member.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5 transition-colors hover:bg-surface-2/50"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/12 text-[13px] font-semibold text-primary ring-1 ring-primary/25">{initials(member.display_name)}</span><span className="min-w-0 flex-1"><span className="block truncate text-[13.5px] font-medium">{member.display_name}</span><span className="block truncate text-[11.5px] text-muted-foreground">{member.email}</span></span><span className={cn("rounded-full border px-2.5 py-1 text-[11px] font-medium", roleTone[role])}>{role}</span><button type="button" onClick={() => { setFormError(""); update.mutate({ id: member.id, is_active: !member.is_active }); }} disabled={update.isPending} aria-label={`${member.display_name}: ${member.is_active ? "activo" : "inactivo"}`} className={cn("rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50", member.is_active ? "border-primary/30 bg-primary/10 text-primary" : "border-border bg-surface-2 text-muted-foreground")}>{member.is_active ? "Activo" : "Inactivo"}</button></li>;
                    })}
                    {filtered.length === 0 && <li className="px-5 py-14 text-center text-[12.5px] text-muted-foreground">Sin usuarios que coincidan con la búsqueda.</li>}
                  </ul>
                )}
              </section>

              <section className="rounded-3xl border border-border bg-surface/60 shadow-card">
                <div className="flex items-center gap-2 border-b border-border px-5 py-4"><UserPlus className="size-4 text-primary" /><h2 className="text-[15px] font-semibold tracking-tight">Agregar usuario</h2></div>
                <form onSubmit={submit} className="space-y-4 px-5 py-5">
                  <Field label="Nombre"><input name="display_name" required className={inputCls} placeholder="Nombre del usuario" /></Field>
                  <Field label="Correo"><input name="email" type="email" required className={inputCls} placeholder="usuario@empresa.com" /></Field>
                  <Field label="Contraseña temporal"><input name="password" type="password" minLength={12} required className={inputCls} placeholder="••••••••••••" /></Field>
                  <Field label="Rol"><select name="role" defaultValue="viewer" className={cn(inputCls, "appearance-none pr-8")}><option value="viewer">Viewer</option><option value="operator">Editor</option><option value="admin">Admin</option></select></Field>
                  {formError && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-[11.5px] text-destructive">{formError}</p>}
                  <button type="submit" disabled={create.isPending} className="h-10 w-full rounded-xl bg-primary text-[13px] font-semibold text-primary-foreground shadow-[0_8px_24px_-10px_var(--primary)] transition-transform hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:translate-y-0 disabled:opacity-50">{create.isPending ? "Guardando…" : "Guardar usuario"}</button>
                </form>
              </section>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

const inputCls = "h-10 w-full rounded-xl border border-border bg-surface-2 px-3 text-[12.5px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/40";
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block"><span className="mb-1.5 block text-[11.5px] font-medium text-muted-foreground">{label}</span>{children}</label>; }
function Stat({ icon: Icon, label }: { icon: typeof Users; label: string }) { return <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2/80 px-3 py-1.5 text-[11.5px] text-muted-foreground"><Icon className="size-3.5 text-primary" />{label}</span>; }
