import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Bookmark, Filter, Inbox, LogOut, Mail, MailOpen, PanelLeft, PanelLeftClose, RefreshCw, Search, Sparkles, Users, X } from "lucide-react";
import { AppSidebar } from "@/components/mail/app-sidebar";
import { FolderNav } from "@/components/mail/folder-nav";
import { MessageList, type MessageRowData } from "@/components/mail/message-list";
import { ReadingPane } from "@/components/mail/reading-pane";
import { AccountPicker } from "@/components/mail/account-picker";
import { MetricsGrid, type Metric } from "@/components/mail/metrics-grid";
import { SyncAlerts } from "@/components/mail/sync-alerts";
import { BulkActions } from "@/components/mail/bulk-actions";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { categoryFor, folderFrom, mailFilters, mapAccount, mapMessage, scopedIds } from "@/lib/mail-state";
import { attentionStatuses, folders, savedViews, type FolderId, type MailMessage } from "@/lib/mail-data";
import { api, clearSession, currentUser } from "@/lib/api";
import type { Account, MessageContent, MessageCounts, MessagePage, Page } from "@/lib/types";

const PAGE_SIZE = 25;

export function MailInbox() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const accountId = params.get("account_id");
  const folder = folderFrom(params.get("folder"));
  const query = params.get("q") ?? "";
  const [rawQuery, setRawQuery] = useState(query);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSeed, setSelectedSeed] = useState<MailMessage | null>(null);
  const [threadRoot, setThreadRoot] = useState<{ id: string; accountId: string } | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [syncing, setSyncing] = useState(false);
  const [mutationError, setMutationError] = useState("");
  const [mutating, setMutating] = useState(false);
  const mutationLock = useRef(false);
  const [folderNavOpen, setFolderNavOpen] = useState(true);
  const [showOverview, setShowOverview] = useState(false);
  const [now, setNow] = useState(Date.now());
  const searchRef = useRef<HTMLInputElement>(null);
  const canManage = currentUser()?.role !== "viewer";

  const changeScope = useCallback((key: "account_id" | "folder" | "q", value: string | null) => {
    setCheckedIds(new Set()); setSelectedId(null); setSelectedSeed(null); setThreadRoot(null);
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value); else next.delete(key);
      return next;
    }, { replace: key === "q" });
  }, [setParams]);
  const setFolder = (value: FolderId) => changeScope("folder", value === "todos" ? null : value);
  const selectAccount = (id: string | null) => changeScope("account_id", id);
  useEffect(() => { setRawQuery(query); }, [query]);
  useEffect(() => {
    if (rawQuery === query) return;
    const timer = window.setTimeout(() => changeScope("q", rawQuery || null), 220);
    return () => window.clearTimeout(timer);
  }, [changeScope, rawQuery, query]);
  useEffect(() => { setCheckedIds(new Set()); setSelectedId(null); setSelectedSeed(null); setThreadRoot(null); }, [accountId, folder, rawQuery]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 30_000); return () => window.clearInterval(timer); }, []);

  const filter = useMemo(() => mailFilters(query, accountId, folder), [query, accountId, folder]);
  const countFilters = useMemo(() => { const result = mailFilters(query, accountId, "todos"); result.params.delete("mailbox"); return result; }, [query, accountId]);
  const filterKey = filter.params.toString();
  const accountsQuery = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/v1/mail/accounts"), staleTime: 60_000 });
  const messagesQuery = useInfiniteQuery({
    queryKey: ["messages", filterKey], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api<MessagePage>(`/v1/mail/messages?limit=${PAGE_SIZE}&${filterKey}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`, { signal }),
    getNextPageParam: (page) => page.next_cursor, staleTime: 60_000, enabled: !filter.error,
  });
  const countsQuery = useQuery({
    queryKey: ["message-counts", countFilters.params.toString()],
    queryFn: ({ signal }) => api<MessageCounts>(`/v1/mail/messages/counts?${countFilters.params}`, { signal }),
    staleTime: 60_000, enabled: !countFilters.error,
  });
  const contentQuery = useQuery({
    queryKey: ["message-content", selectedId],
    queryFn: ({ signal }) => api<MessageContent>(`/v1/mail/messages/${encodeURIComponent(selectedId!)}`, { signal }),
    enabled: !!selectedId, staleTime: 5 * 60_000,
  });
  const threadQuery = useInfiniteQuery({
    queryKey: ["message-thread", threadRoot?.accountId, threadRoot?.id], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api<Page<MessageContent> & { total_count: number }>(`/v1/mail/messages/${encodeURIComponent(threadRoot!.id)}/thread?account_id=${encodeURIComponent(threadRoot!.accountId)}&limit=30${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`, { signal }),
    getNextPageParam: (page) => page.next_cursor, enabled: !!threadRoot, staleTime: 5 * 60_000,
  });
  const rawAccounts = useMemo(() => accountsQuery.data ?? [], [accountsQuery.data]);
  const accounts = useMemo(() => rawAccounts.map((item) => mapAccount(item, now)), [rawAccounts, now]);
  const accountById = useMemo(() => new Map(accounts.map((item) => [item.id, item])), [accounts]);
  const rawMessages = useMemo(() => messagesQuery.data?.pages.flatMap((page) => page.items) ?? [], [messagesQuery.data]);
  const messages = useMemo(() => rawMessages.map(mapMessage), [rawMessages]);
  const rows: MessageRowData[] = useMemo(() => {
    const grouped = new Map<string, MailMessage[]>();
    messages.forEach((message) => { const key = `${message.accountId}:${message.threadId}`; grouped.set(key, [...(grouped.get(key) ?? []), message]); });
    return [...grouped.values()].map((thread) => ({ message: thread[0]!, account: accountById.get(thread[0]!.accountId), threadCount: rawMessages.find((item) => item.id === thread[0]!.id)?.thread_count ?? thread.length }));
  }, [messages, accountById, rawMessages]);
  const selectedThread = useMemo(() => threadQuery.data?.pages.flatMap((page) => page.items).map(mapMessage) ?? [], [threadQuery.data]);
  const selected = selectedId ? contentQuery.data ? mapMessage(contentQuery.data) : messages.find((message) => message.id === selectedId) ?? selectedThread.find((message) => message.id === selectedId) ?? selectedSeed : null;
  const selectedAccount = selected ? accountById.get(selected.accountId) : undefined;
  const checkedList = scopedIds(checkedIds, rows.map((row) => row.message.id));
  const allChecked = rows.length > 0 && rows.every((row) => checkedIds.has(row.message.id));
  const problemAccounts = accounts.filter((account) => attentionStatuses.includes(account.status) || account.syncStale);
  const counts = useMemo(() => {
    const data = countsQuery.data;
    if (!data) return {};
    const result: Record<string, number> = { todos: data.total, "no-leidos": data.unread, destacados: data.starred, criticos: data.critical, archivados: data.archive, papelera: data.trash };
    for (const [category, count] of Object.entries(data.categories)) for (const id of categoryFor(category)) result[id] = (result[id] ?? 0) + count;
    return result;
  }, [countsQuery.data]);
  const metrics: Metric[] = [
    { id: "total", label: "Mensajes", value: countsQuery.data?.total ?? 0, icon: Mail },
    { id: "unread", label: "No leídos", value: countsQuery.data?.unread ?? 0, icon: MailOpen, tone: "primary", onClick: () => setFolder("no-leidos") },
    { id: "critical", label: "Críticos", value: countsQuery.data?.critical ?? 0, icon: AlertTriangle, tone: "danger", onClick: () => setFolder("criticos") },
    { id: "accounts", label: "Cuentas", value: accounts.length, icon: Users },
    { id: "problems", label: "Requieren atención", value: problemAccounts.length, icon: AlertTriangle, tone: "warning" },
    { id: "pending", label: "Sin analizar", value: countsQuery.data?.unanalyzed ?? 0, icon: Sparkles },
  ];
  const refreshMail = useCallback(async () => {
    await Promise.all(["messages", "message-counts", "accounts", "message-content", "message-thread"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  }, [queryClient]);
  const updateMessages = useCallback(async (ids: string[], payload: Record<string, unknown>) => {
    if (!canManage || mutationLock.current) return false;
    const allowed = rows.map((row) => row.message.id);
    if (selected && (!accountId || selected.accountId === accountId)) allowed.push(selected.id);
    const targets = scopedIds(ids, allowed);
    if (!targets.length) return false;
    mutationLock.current = true; setMutating(true); setMutationError("");
    try {
      const results = await Promise.allSettled(targets.map((id) => api(`/v1/mail/messages/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) })));
      const failures = results.filter((result) => result.status === "rejected");
      if (failures.length) setMutationError(`${failures.length} de ${targets.length} cambios no se guardaron. ${failures[0].reason instanceof Error ? failures[0].reason.message : "Reintenta la acción."}`);
      await refreshMail();
      return failures.length === 0;
    } finally { mutationLock.current = false; setMutating(false); }
  }, [accountId, canManage, refreshMail, rows, selected]);
  const openMessage = useCallback((id: string, fromThread = false) => {
    const message = (fromThread ? selectedThread : messages).find((item) => item.id === id);
    if (!message) return;
    setSelectedId(id); setSelectedSeed(message);
    if (!fromThread) setThreadRoot({ id, accountId: message.accountId });
    if (message.unread && canManage) void updateMessages([id], { is_read: true });
  }, [canManage, messages, selectedThread, updateMessages]);
  function toggleStar(id: string) {
    const message = messages.find((item) => item.id === id) ?? (selected?.id === id ? selected : null);
    if (message) void updateMessages([id], { is_starred: !message.starred });
  }
  async function moveMessages(ids: string[], destination: "archive" | "trash") {
    const scoped = scopedIds(ids, [...rows.map((row) => row.message.id), ...(selected ? [selected.id] : [])]);
    if (!scoped.length || !canManage || mutationLock.current) return;
    if ((destination === "trash" || scoped.length > 1) && !window.confirm(`${destination === "trash" ? "Mover a la papelera" : "Archivar"} ${scoped.length} mensaje${scoped.length === 1 ? "" : "s"} seleccionado${scoped.length === 1 ? "" : "s"} de esta vista?`)) return;
    if (await updateMessages(scoped, { mailbox: destination })) { setSelectedId(null); setSelectedSeed(null); setThreadRoot(null); setCheckedIds(new Set()); }
  }
  async function syncAccount(id: string) {
    const account = rawAccounts.find((item) => item.id === id); if (!account || !canManage) return;
    try { await api(`/v1/providers/${account.provider}/${account.id}/sync`, { method: "POST" }); await refreshMail(); }
    catch (error) { setMutationError(error instanceof Error ? error.message : "No se pudo sincronizar la cuenta."); }
  }
  async function reauthorize(id: string) {
    const account = rawAccounts.find((item) => item.id === id); if (!account || !canManage) return;
    try {
      const result = await api<{ authorization_url: string }>(`/v1/providers/${account.provider}/authorize`, { method: "POST", body: JSON.stringify({ account_id: account.id }) });
      window.location.assign(result.authorization_url);
    } catch (error) { setMutationError(error instanceof Error ? error.message : "No se pudo iniciar la autorización."); }
  }
  async function syncAll() {
    setSyncing(true); setMutationError("");
    try { await Promise.all(rawAccounts.filter((account) => account.status === "connected" && (!accountId || account.id === accountId)).map((account) => syncAccount(account.id))); }
    finally { setSyncing(false); }
  }
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input,textarea,button,[contenteditable=true],[role=dialog],[role=checkbox]")) return;
      if (event.key === "/") { event.preventDefault(); searchRef.current?.focus(); }
      if (event.key === "Escape") setSelectedId(null);
      const currentIndex = rows.findIndex((row) => row.message.id === selectedId);
      if (["ArrowDown", "j", "ArrowUp", "k"].includes(event.key)) { event.preventDefault(); const direction = ["ArrowDown", "j"].includes(event.key) ? 1 : -1; const row = rows[Math.max(0, Math.min(rows.length - 1, currentIndex + direction))]; if (row) openMessage(row.message.id); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openMessage, rows, selectedId]);
  function logout() { clearSession(); queryClient.clear(); navigate("/login", { replace: true }); }
  const folderLabel = folders.find((item) => item.id === folder)?.label ?? "Todos";
  const filtersPanel = <div className="space-y-4 p-4"><p className="text-[12px] text-muted-foreground">Los filtros se aplican a todos los mensajes sincronizados.</p><div className="flex flex-wrap gap-1.5">{[["No leídos", "estado:no-leido"], ["Riesgo alto", "riesgo:alto"], ["Gmail", "proveedor:gmail"], ["Outlook", "proveedor:outlook"], ["Hotmail", "proveedor:hotmail"], ["Live", "proveedor:live"], ["Pagos", "categoria:pagos"], ["Seguridad", "categoria:seguridad"]].map(([label, value]) => <button key={value} type="button" onClick={() => setRawQuery((previous) => previous.includes(value) ? previous : `${previous} ${value}`.trim())} className="rounded-lg border border-border px-3 py-1.5 text-[12px] text-muted-foreground hover:text-foreground">{label}</button>)}</div><p className="text-[11px] font-semibold text-muted-foreground">Vistas guardadas</p><div className="flex flex-wrap gap-1.5">{savedViews.map((view) => <button key={view.id} type="button" onClick={() => setRawQuery(view.query)} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12px] text-muted-foreground"><Bookmark className="size-3" />{view.label}</button>)}</div><p className="text-[11px] leading-relaxed text-muted-foreground">Operadores: cuenta:, correo:, proveedor:, plataforma:, categoria:, estado:, riesgo:, desde:AAAA-MM-DD, hasta:AAAA-MM-DD, de:, para:, tiene:adjuntos</p></div>;

  return <main className="sleek-mail mail-inbox-live fixed inset-0 z-[70] flex h-[100dvh] w-full overflow-hidden bg-background">
    <AppSidebar compact className="hidden lg:flex" />
    <aside aria-hidden={!folderNavOpen} className={cn("hidden shrink-0 overflow-hidden bg-card/60 transition-[width,border-color] duration-200 xl:block", folderNavOpen ? "w-64 border-r border-border" : "w-0 border-r border-transparent")}><FolderNav activeFolder={folder} onSelect={setFolder} counts={counts} onApplyView={setRawQuery} activeView={rawQuery} className="h-full w-64" /></aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="mail-inbox-header grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-border px-4 py-5 sm:px-6">
        <div className="flex min-w-0 items-center gap-2"><Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 lg:hidden" aria-label="Menú"><PanelLeft className="size-4" /></Button></SheetTrigger><SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0"><SheetTitle className="sr-only">Navegación</SheetTitle><AppSidebar className="flex w-full border-r-0" /></SheetContent></Sheet><Button variant="ghost" size="icon" onClick={() => setFolderNavOpen((open) => !open)} className="hidden size-8 xl:grid" aria-label={folderNavOpen ? "Ocultar clasificación" : "Mostrar clasificación"} aria-expanded={folderNavOpen}>{folderNavOpen ? <PanelLeftClose className="size-4" /> : <PanelLeft className="size-4" />}</Button><div className="min-w-0"><p className="truncate text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{accountId ? accountById.get(accountId)?.email ?? "Bandeja de cuenta" : "Bandeja unificada"}</p><h1 className="truncate text-xl font-bold text-foreground">Correos</h1></div></div>
        <div className="flex shrink-0 items-center gap-2"><Button variant="ghost" size="sm" onClick={() => setShowOverview((value) => !value)} className="hidden sm:flex"><Sparkles className="size-4" />Estado</Button><Button variant="ghost" size="icon" onClick={() => void refreshMail()} aria-label="Actualizar bandeja" disabled={messagesQuery.isFetching}><RefreshCw className={cn("size-4", messagesQuery.isFetching && "animate-spin")} /></Button><Button onClick={() => void syncAll()} disabled={syncing || !accounts.length || !canManage} size="sm" className="mail-sync-button h-10 gap-2 rounded-full px-4 text-sm font-semibold shadow-sm"><RefreshCw className={cn("size-4", syncing && "animate-spin")} /><span>{syncing ? "Sincronizando" : "Sincronizar"}</span></Button><Button onClick={logout} variant="ghost" size="icon" className="hidden size-9 sm:grid" aria-label="Salir"><LogOut className="size-5" /></Button></div>
      </header>
      {params.has("oauth_error") && <div role="alert" className="border-b border-warning/20 bg-warning/10 px-4 py-2 text-[12px] text-foreground">La conexión no se completó. Puedes volver a autorizar la cuenta desde Cuentas.</div>}
      {mutationError && <div role="alert" className="flex items-center gap-2 border-b border-destructive/20 bg-destructive/10 px-4 py-2 text-[12px] text-destructive"><span className="flex-1">{mutationError}</span><button type="button" onClick={() => setMutationError("")} aria-label="Cerrar error"><X className="size-4" /></button></div>}
      {mutating && <p role="status" className="border-b border-border px-4 py-1 text-[11px] text-muted-foreground">Guardando cambios…</p>}
      {(showOverview || problemAccounts.length > 0) && <div className="max-h-[28vh] space-y-3 overflow-y-auto border-b border-border px-4 py-3 sm:px-6">{showOverview && countsQuery.data && <MetricsGrid metrics={metrics} />}<SyncAlerts accounts={accounts} onSelectAccount={selectAccount} onRetry={syncAccount} onReauthorize={reauthorize} onConfigure={() => navigate("/cuentas")} /></div>}
      {accountsQuery.isError && <ErrorNotice text="No se pudieron cargar las cuentas." retry={() => void accountsQuery.refetch()} />}
      {countsQuery.isError && <ErrorNotice text="No se pudieron actualizar los contadores." retry={() => void countsQuery.refetch()} />}
      <div className="flex min-h-0 flex-1">
        <section className={cn("mail-list-panel m-3 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm sm:m-4", selected ? "hidden xl:flex xl:w-[46%] xl:flex-none" : "flex")}>
          <div className="space-y-3 border-b border-border px-4 py-3"><AccountPicker accounts={accounts} value={accountId} onChange={selectAccount} className="w-full" /><div className="flex items-center gap-1.5"><Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 shrink-0 xl:hidden" aria-label="Carpetas"><Inbox className="size-4" /></Button></SheetTrigger><SheetContent side="left" className="w-72 bg-surface p-0"><SheetTitle className="px-3 pt-4 text-sm">Bandejas</SheetTitle><FolderNav activeFolder={folder} onSelect={setFolder} counts={counts} onApplyView={setRawQuery} activeView={rawQuery} /></SheetContent></Sheet><div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><input ref={searchRef} value={rawQuery} onChange={(event) => setRawQuery(event.target.value)} placeholder="Buscar correo, asunto o categoría…" aria-label="Buscar mensajes" className="h-9 w-full rounded-lg border border-border bg-surface-2 pl-8 pr-8 text-[12.5px] text-foreground placeholder:text-muted-foreground/80 focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring/30" />{rawQuery && <button type="button" onClick={() => setRawQuery("")} aria-label="Limpiar búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"><X className="size-3.5" /></button>}</div><Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label="Filtros"><Filter className="size-4" /></Button></SheetTrigger><SheetContent side="right" className="w-[320px] max-w-[90vw] bg-surface p-0"><SheetTitle className="px-4 pt-4 text-sm">Filtros</SheetTitle>{filtersPanel}</SheetContent></Sheet></div></div>
          <fieldset disabled={mutating || !canManage} className="contents"><BulkActions count={checkedList.length} onClear={() => setCheckedIds(new Set())} onRead={() => void updateMessages(checkedList, { is_read: true })} onUnread={() => void updateMessages(checkedList, { is_read: false })} onStar={() => void updateMessages(checkedList, { is_starred: true })} onArchive={() => void moveMessages(checkedList, "archive")} onDelete={() => void moveMessages(checkedList, "trash")} /></fieldset>
          <div className="flex items-center gap-2.5 border-b border-border px-4 py-2"><Checkbox checked={allChecked} onCheckedChange={() => setCheckedIds(allChecked ? new Set() : new Set(rows.map((row) => row.message.id)))} aria-label="Seleccionar mensajes visibles" disabled={!canManage || mutating} /><p className="min-w-0 truncate text-[11px] text-muted-foreground">{messagesQuery.data ? `${messagesQuery.data.pages[0].total_count} mensajes · ${rows.length} conversaciones cargadas · ` : ""}{folderLabel}</p></div>
          {filter.error ? <div role="alert" className="p-5 text-sm text-destructive">{filter.error}</div> : messagesQuery.isError && !messagesQuery.data ? <ErrorNotice text="No se pudieron cargar los mensajes." retry={() => void messagesQuery.refetch()} /> : <MessageList rows={rows} selectedId={selectedId} checkedIds={new Set(checkedList)} loading={messagesQuery.isLoading} onOpen={openMessage} onToggleCheck={(id) => { if (!mutating && canManage) setCheckedIds((previous) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }} onToggleStar={toggleStar} onToggleRead={(id, unread) => void updateMessages([id], { is_read: unread })} onArchive={(id) => void moveMessages([id], "archive")} onDelete={(id) => void moveMessages([id], "trash")} />}
          {messagesQuery.isError && messagesQuery.data && <ErrorNotice text="No se pudo actualizar esta página. Se conserva lo ya cargado." retry={() => void (messagesQuery.isFetchNextPageError ? messagesQuery.fetchNextPage() : messagesQuery.refetch())} />}
          {messagesQuery.hasNextPage && !filter.error && <div className="shrink-0 border-t border-border px-3 py-2 text-center"><Button variant="ghost" size="sm" disabled={messagesQuery.isFetchingNextPage} onClick={() => void messagesQuery.fetchNextPage()}>{messagesQuery.isFetchingNextPage ? "Cargando mensajes…" : "Cargar más mensajes"}</Button></div>}
        </section>
        <section className={cn("mail-reading-panel min-w-0 flex-1 overflow-hidden border-l border-border bg-surface/30", selected ? "flex" : "hidden xl:flex")}><ReadingPane message={selected} account={selectedAccount} thread={selectedThread} loading={!!selectedId && contentQuery.isLoading} error={contentQuery.isError ? "No se pudo cargar el contenido completo." : undefined} onRetry={() => void contentQuery.refetch()} threadLoading={threadQuery.isLoading} threadError={threadQuery.isError} onRetryThread={() => void threadQuery.refetch()} onOpenThread={(id) => openMessage(id, true)} hasMoreThread={threadQuery.hasNextPage} loadingMoreThread={threadQuery.isFetchingNextPage} onLoadMoreThread={() => void threadQuery.fetchNextPage()} returnSearch={params.toString()} contentWarning={contentQuery.data?.content_warning} attachmentsError={contentQuery.data?.attachments_error} onBack={() => setSelectedId(null)} onToggleStar={toggleStar} onArchive={(id) => void moveMessages([id], "archive")} onDelete={(id) => void moveMessages([id], "trash")} /></section>
      </div>
    </div>
  </main>;
}

function ErrorNotice({ text, retry }: { text: string; retry: () => void }) {
  return <div role="alert" className="flex items-center justify-between gap-3 border-b border-destructive/20 bg-destructive/[0.06] px-4 py-3 text-[12px] text-destructive"><span>{text}</span><button type="button" onClick={retry} className="shrink-0 rounded-lg border border-destructive/30 px-3 py-1.5 font-medium">Reintentar</button></div>;
}
