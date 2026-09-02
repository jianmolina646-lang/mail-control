import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowUpDown, Bell, Bookmark, Filter, Inbox, LogOut,
  Mail, MailOpen, PanelLeft, PanelLeftClose, RefreshCw, Search, Sparkles, Users, Wifi, X,
} from "lucide-react";
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
import { matchesQuery, parseQuery } from "@/lib/mail-search";
import {
  attentionStatuses, folders, savedViews, type FolderId, type MailAccount,
  type MailMessage, type Provider, type Risk, type SyncStatus,
} from "@/lib/mail-data";
import { api, clearSession } from "@/lib/api";
import type { Account, Message, MessageContent, Page } from "@/lib/types";

const PAGE_SIZE = 25;
type SortBy = "fecha" | "prioridad" | "cuenta" | "cliente";
const sortOptions: { id: SortBy; label: string }[] = [
  { id: "fecha", label: "Fecha" }, { id: "prioridad", label: "Prioridad" },
  { id: "cuenta", label: "Cuenta" }, { id: "cliente", label: "Cliente" },
];
const riskWeight = { alto: 0, medio: 1, bajo: 2 } as const;

export function MailInbox() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [folder, setFolder] = useState<FolderId>("todos");
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [accountId, setAccountId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());
  const [syncing, setSyncing] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("fecha");
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [folderNavOpen, setFolderNavOpen] = useState(true);
  const [showOverview, setShowOverview] = useState(false);
  const [selectedContent, setSelectedContent] = useState<{ id: string; data: MessageContent } | null>(null);
  const [selectedContentError, setSelectedContentError] = useState<{ id: string; message: string } | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const mailbox = folder === "archivados" ? "archive" : folder === "papelera" ? "trash" : "inbox";

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(rawQuery), 220);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  const accountsQuery = useQuery({
    queryKey: ["accounts"], queryFn: () => api<Account[]>("/v1/mail/accounts"),
  });
  const messagesQuery = useInfiniteQuery({
    queryKey: ["messages", query, accountId, mailbox], initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => api<Page<Message>>(`/v1/mail/messages?limit=50&mailbox=${mailbox}${accountId ? `&account_id=${encodeURIComponent(accountId)}` : ""}${query.trim().length >= 2 ? `&search=${encodeURIComponent(query.trim())}` : ""}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`),
    getNextPageParam: (page) => page.next_cursor,
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
    staleTime: 8_000,
  });

  const rawAccounts = useMemo(() => accountsQuery.data ?? [], [accountsQuery.data]);
  const rawMessages = useMemo(() => messagesQuery.data?.pages.flatMap((page) => page.items) ?? [], [messagesQuery.data]);
  const accounts = useMemo(() => rawAccounts.map(mapAccount), [rawAccounts]);
  const messages = useMemo(
    () => rawMessages.map((message) => mapMessage(message, readIds, starredIds)),
    [rawMessages, readIds, starredIds],
  );
  const rawAccountById = useMemo(() => new Map(rawAccounts.map((a) => [a.id, a])), [rawAccounts]);
  const accountById = useMemo(() => new Map(accounts.map((a) => [a.id, a])), [accounts]);

  const counts = useMemo(() => {
    const base: Record<string, number> = {
      todos: messages.length,
      "no-leidos": messages.filter((m) => m.unread).length,
      destacados: messages.filter((m) => m.starred).length,
    };
    for (const item of folders) {
      if (base[item.id] === undefined) base[item.id] = messages.filter((m) => m.categories.includes(item.id)).length;
    }
    return base;
  }, [messages]);

  const parsed = useMemo(() => parseQuery(query), [query]);
  const filtered = useMemo(() => {
    const list = messages.filter((message) => {
      if (folder === "no-leidos" && !message.unread) return false;
      if (folder === "destacados" && !message.starred) return false;
      if (!["todos", "no-leidos", "destacados", "vistas"].includes(folder) && !message.categories.includes(folder)) return false;
      if (accountId && message.accountId !== accountId) return false;
      return matchesQuery(message, accountById.get(message.accountId), parsed);
    });
    return [...list].sort((a, b) => {
      if (sortBy === "prioridad") return Number(!!b.critical) - Number(!!a.critical) || riskWeight[a.risk] - riskWeight[b.risk] || b.isoDate.localeCompare(a.isoDate);
      if (sortBy === "cuenta") return (accountById.get(a.accountId)?.alias ?? "").localeCompare(accountById.get(b.accountId)?.alias ?? "");
      if (sortBy === "cliente") return (accountById.get(a.accountId)?.client ?? "").localeCompare(accountById.get(b.accountId)?.client ?? "");
      return b.isoDate.localeCompare(a.isoDate) || b.time.localeCompare(a.time);
    });
  }, [messages, folder, accountId, accountById, parsed, sortBy]);

  const rows: MessageRowData[] = useMemo(() => {
    const grouped = new Map<string, MailMessage[]>();
    filtered.forEach((message) => {
      const key = `${message.accountId}:${message.threadId}`;
      grouped.set(key, [...(grouped.get(key) ?? []), message]);
    });
    return [...grouped.values()].map((thread) => ({ message: thread[0]!, account: accountById.get(thread[0]!.accountId), threadCount: thread.length }));
  }, [filtered, accountById]);
  const pageRows = rows.slice(0, pageSize);
  useEffect(() => setPageSize(PAGE_SIZE), [folder, accountId, query, sortBy]);
  const selectedSummary = messages.find((message) => message.id === selectedId) ?? null;
  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setSelectedContentError(null);
    void queryClient.fetchQuery({
      queryKey: ["message-content", selectedId],
      queryFn: () => api<MessageContent>(`/v1/mail/messages/${encodeURIComponent(selectedId)}`),
      staleTime: 5 * 60_000,
    }).then((data) => {
      if (!cancelled) setSelectedContent({ id: selectedId, data });
    }).catch((error: unknown) => {
      if (!cancelled) {
        const message = error instanceof Error ? error.message : "No fue posible cargar el contenido completo.";
        setSelectedContentError({ id: selectedId, message });
      }
    });
    return () => { cancelled = true; };
  }, [queryClient, selectedId]);
  const currentContent = selectedContent?.id === selectedId ? selectedContent.data : null;
  const currentContentError = selectedContentError?.id === selectedId ? selectedContentError.message : "";
  const selected = selectedSummary ? {
    ...selectedSummary,
    body: currentContent?.body || currentContentError || selectedSummary.body,
    bodyHtml: currentContent?.body_html || selectedSummary.bodyHtml,
  } : null;
  const selectedAccount = selected ? accountById.get(selected.accountId) : undefined;
  const selectedThread = selected ? messages.filter((message) => message.accountId === selected.accountId && message.threadId === selected.threadId) : [];
  const allChecked = pageRows.length > 0 && pageRows.every((row) => checkedIds.has(row.message.id));
  const problemAccounts = accounts.filter((account) => attentionStatuses.includes(account.status));

  const metrics: Metric[] = [
    { id: "total", label: "Mensajes", value: messages.length, icon: Mail },
    { id: "unread", label: "No leídos", value: counts["no-leidos"] ?? 0, icon: MailOpen, tone: "primary", onClick: () => setFolder("no-leidos") },
    { id: "critical", label: "Críticos", value: messages.filter((m) => m.critical).length, icon: AlertTriangle, tone: "danger", onClick: () => setFolder("criticos") },
    { id: "accounts", label: "Cuentas", value: accounts.length, icon: Users },
    { id: "problems", label: "Con problemas", value: problemAccounts.length, icon: AlertTriangle, tone: "warning" },
    { id: "pending", label: "Sin analizar", value: rawMessages.filter((m) => !m.category).length, icon: Sparkles },
  ];

  const openMessage = (id: string) => { setSelectedId(id); setReadIds((prev) => new Set(prev).add(id)); };
  const prefetchMessage = (id: string) => { void queryClient.prefetchQuery({ queryKey: ["message-content", id], queryFn: () => api<MessageContent>(`/v1/mail/messages/${id}`), staleTime: 5 * 60_000 }); };
  const selectAccount = (id: string | null) => { setAccountId(id); setSelectedId(null); };
  const toggleCheck = (id: string) => setCheckedIds((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const toggleAll = () => setCheckedIds(allChecked ? new Set() : new Set(pageRows.map((row) => row.message.id)));
  const updateMessages = async (ids: string[], payload: Record<string, unknown>) => {
    await Promise.all(ids.map((id) => api(`/v1/mail/messages/${id}`, { method: "PATCH", body: JSON.stringify(payload) })));
    await queryClient.invalidateQueries({ queryKey: ["messages"] });
  };
  const toggleStar = (id: string) => {
    const nextValue = !(messages.find((message) => message.id === id)?.starred ?? false);
    setStarredIds((prev) => { const next = new Set(prev); if (nextValue) next.add(id); else next.delete(id); return next; });
    void updateMessages([id], { is_starred: nextValue });
  };
  const setReadState = (ids: string[], unread: boolean) => {
    setReadIds((prev) => { const next = new Set(prev); ids.forEach((id) => unread ? next.delete(id) : next.add(id)); return next; });
    void updateMessages(ids, { is_read: !unread });
  };
  const moveMessages = (ids: string[], destination: "inbox" | "archive" | "trash") => {
    setSelectedId(null); setCheckedIds(new Set());
    void updateMessages(ids, { mailbox: destination });
  };
  async function loadMoreMessages() {
    if (pageRows.length < rows.length) {
      setPageSize((size) => size + PAGE_SIZE);
      return;
    }
    if (messagesQuery.hasNextPage) {
      await messagesQuery.fetchNextPage();
      setPageSize((size) => size + PAGE_SIZE);
    }
  }
  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || messagesQuery.isFetchingNextPage) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) void loadMoreMessages();
    }, { rootMargin: "240px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [pageRows.length, rows.length, messagesQuery.hasNextPage, messagesQuery.isFetchingNextPage]);

  async function syncAccount(id: string) {
    const account = rawAccountById.get(id); if (!account) return;
    await api(`/v1/providers/${account.provider}/${account.id}/sync`, { method: "POST" });
    await Promise.all([queryClient.invalidateQueries({ queryKey: ["accounts"] }), queryClient.invalidateQueries({ queryKey: ["messages"] })]);
  }
  async function reauthorize(id: string) {
    const account = rawAccountById.get(id); if (!account) return;
    const result = await api<{ authorization_url: string }>(`/v1/providers/${account.provider}/authorize`, { method: "POST" });
    window.location.assign(result.authorization_url);
  }
  async function syncAll() {
    setSyncing(true);
    try { await Promise.all(rawAccounts.filter((a) => a.status === "connected").map((a) => syncAccount(a.id))); }
    finally { setSyncing(false); }
  }
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const editing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
      if (event.key === "/" && !editing) { event.preventDefault(); searchRef.current?.focus(); return; }
      if (editing) return;
      const currentIndex = pageRows.findIndex((row) => row.message.id === selectedId);
      if (event.key === "ArrowDown" || event.key.toLowerCase() === "j") { event.preventDefault(); const next = pageRows[Math.min(Math.max(currentIndex + 1, 0), pageRows.length - 1)]; if (next) openMessage(next.message.id); }
      if (event.key === "ArrowUp" || event.key.toLowerCase() === "k") { event.preventDefault(); const previous = pageRows[Math.max(currentIndex - 1, 0)]; if (previous) openMessage(previous.message.id); }
      if (selectedId && event.key.toLowerCase() === "e") moveMessages([selectedId], "archive");
      if (selectedId && event.key.toLowerCase() === "s") toggleStar(selectedId);
      if (selectedId && event.key === "Escape") setSelectedId(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [pageRows, selectedId, messages]);
  function logout() { clearSession(); queryClient.clear(); navigate("/login", { replace: true }); }

  const folderLabel = folders.find((item) => item.id === folder)?.label ?? "Todos";
  const checkedList = [...checkedIds];
  const filtersPanel = (
    <div className="space-y-4 p-4">
      <div><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Orden</p><div className="flex flex-wrap gap-1.5">{sortOptions.map((option) => <button key={option.id} type="button" onClick={() => setSortBy(option.id)} className={cn("rounded-md border px-2.5 py-1 text-[12px] transition-colors", sortBy === option.id ? "border-primary/30 bg-primary/12 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>{option.label}</button>)}</div></div>
      <div><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Filtros rápidos</p><div className="flex flex-wrap gap-1.5">{[
        ["No leídos", "estado:no-leido"], ["Riesgo alto", "riesgo:alto"], ["Gmail", "proveedor:gmail"], ["Outlook", "proveedor:outlook"], ["Hotmail", "proveedor:hotmail"], ["Live", "proveedor:live"], ["Pagos", "categoria:pagos"], ["Seguridad", "categoria:seguridad"],
      ].map(([label, value]) => <button key={value} type="button" onClick={() => setRawQuery((prev) => prev.includes(value) ? prev : `${prev} ${value}`.trim())} className="rounded-md border border-border px-2.5 py-1 text-[12px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground">{label}</button>)}</div></div>
      <div><p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Vistas guardadas</p><div className="flex flex-wrap gap-1.5">{savedViews.map((view) => <button key={view.id} type="button" onClick={() => setRawQuery(view.query)} className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-[12px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"><Bookmark className="size-3" />{view.label}</button>)}</div></div>
      <p className="text-[11px] leading-relaxed text-muted-foreground/80">Operadores: cuenta:, correo:, cliente:, proveedor:, plataforma:, categoria:, estado:, riesgo:, desde:, hasta:</p>
    </div>
  );

  return <main className="sleek-mail mail-inbox-live fixed inset-0 z-[70] flex h-[100dvh] w-full overflow-hidden bg-background">
    <AppSidebar compact className="hidden lg:flex" />
    <aside aria-hidden={!folderNavOpen} className={cn("hidden shrink-0 overflow-hidden bg-card/60 transition-[width,border-color] duration-200 xl:block", folderNavOpen ? "w-64 border-r border-border" : "w-0 border-r border-transparent")}><FolderNav activeFolder={folder} onSelect={setFolder} counts={counts} onApplyView={setRawQuery} activeView={rawQuery} className="h-full w-64" /></aside>
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="mail-inbox-header grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-border px-4 py-5 sm:px-6">
        <div className="flex min-w-0 items-center gap-2"><Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 lg:hidden" aria-label="Menú"><PanelLeft className="size-4" /></Button></SheetTrigger><SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0"><SheetTitle className="sr-only">Navegación</SheetTitle><AppSidebar className="flex w-full border-r-0" /></SheetContent></Sheet><Button type="button" variant="ghost" size="icon" onClick={() => setFolderNavOpen((open) => !open)} className="hidden size-8 shrink-0 xl:grid" aria-label={folderNavOpen ? "Ocultar clasificación" : "Mostrar clasificación"} aria-expanded={folderNavOpen} title={folderNavOpen ? "Ocultar clasificación" : "Mostrar clasificación"}>{folderNavOpen ? <PanelLeftClose className="size-4" /> : <PanelLeft className="size-4" />}</Button><div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Bandeja unificada</p><h1 className="truncate text-xl font-bold text-foreground">Correos</h1></div></div>
        <div className="flex shrink-0 items-center gap-2"><span className="mail-live-badge hidden items-center gap-1 rounded-full bg-primary/[0.08] px-2 py-1 text-[10.5px] font-medium text-primary md:flex" title="La bandeja comprueba mensajes nuevos automáticamente cada 10 segundos"><Wifi className="size-3" /> En vivo</span><Button variant="ghost" size="sm" onClick={() => setShowOverview((value) => !value)} className="hidden sm:flex"><Sparkles className="size-4" /> Estado</Button><Button onClick={syncAll} disabled={syncing || !accounts.length} size="sm" className="mail-sync-button h-10 gap-2 rounded-full px-5 text-sm font-semibold shadow-sm"><RefreshCw className={cn("size-4", syncing && "animate-spin")} /><span className="hidden sm:inline">{syncing ? "Sincronizando" : "Sincronizar"}</span></Button><Button variant="ghost" size="icon" className="mail-notification-button size-9" aria-label="Notificaciones"><Bell className="size-5" /></Button><Button onClick={logout} variant="ghost" size="icon" className="hidden size-9 sm:grid" aria-label="Salir"><LogOut className="size-5" /></Button></div>
      </header>
      {(showOverview || problemAccounts.length > 0) && <div className="space-y-3 border-b border-border px-4 py-3 sm:px-6">{showOverview && <MetricsGrid metrics={metrics} />}<SyncAlerts accounts={accounts} onSelectAccount={setAccountId} onRetry={syncAccount} onReauthorize={reauthorize} onConfigure={() => navigate("/cuentas")} /></div>}
      <div className="flex min-h-0 flex-1">
        <section className={cn("mail-list-panel m-3 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm sm:m-4", selected ? "hidden xl:flex xl:w-[46%] xl:flex-none" : "flex")}>
          <div className="space-y-3 border-b border-border px-4 py-3">
            <AccountPicker accounts={accounts} value={accountId} onChange={selectAccount} className="hidden w-full md:flex" />
            <div className="flex items-center gap-1.5">
              <Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 shrink-0 md:hidden" aria-label="Carpetas"><Inbox className="size-4" /></Button></SheetTrigger><SheetContent side="left" className="w-72 bg-surface p-0"><SheetTitle className="px-3 pt-4 text-sm">Bandejas</SheetTitle><FolderNav activeFolder={folder} onSelect={setFolder} counts={counts} onApplyView={setRawQuery} activeView={rawQuery} /></SheetContent></Sheet>
              <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><input ref={searchRef} value={rawQuery} onChange={(event) => setRawQuery(event.target.value)} placeholder="Buscar correo, asunto, fecha o categoría…" aria-label="Buscar mensajes" className="h-9 w-full rounded-lg border border-border bg-surface-2 pl-8 pr-8 text-[12.5px] text-foreground placeholder:text-muted-foreground/80 focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-ring/30" />{rawQuery && <button type="button" onClick={() => setRawQuery("")} aria-label="Limpiar búsqueda" className="absolute right-2 top-1/2 grid size-5 -translate-y-1/2 place-items-center rounded text-muted-foreground hover:text-foreground"><X className="size-3.5" /></button>}</div>
              <Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label="Filtros y orden"><Filter className="size-4" /></Button></SheetTrigger><SheetContent side="right" className="w-[320px] max-w-[90vw] bg-surface p-0"><SheetTitle className="px-4 pt-4 text-sm">Filtros y orden</SheetTitle>{filtersPanel}</SheetContent></Sheet>
            </div>
          </div>
          <BulkActions count={checkedIds.size} onClear={() => setCheckedIds(new Set())} onRead={() => setReadState(checkedList, false)} onUnread={() => setReadState(checkedList, true)} onStar={() => checkedList.forEach(toggleStar)} onArchive={() => moveMessages(checkedList, "archive")} onDelete={() => moveMessages(checkedList, "trash")} />
          <div className="flex items-center gap-2.5 border-b border-border px-3 py-1.5 sm:px-4"><Checkbox checked={allChecked} onCheckedChange={toggleAll} aria-label="Seleccionar todos" /><p className="min-w-0 truncate text-[11px] text-muted-foreground">{rows.length} conversaciones · {folderLabel}</p><button type="button" onClick={() => setSortBy((prev) => sortOptions[(sortOptions.findIndex((item) => item.id === prev) + 1) % sortOptions.length]!.id)} className="ml-auto flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"><ArrowUpDown className="size-3" />{sortOptions.find((item) => item.id === sortBy)?.label}</button></div>
          <MessageList rows={pageRows} selectedId={selectedId} checkedIds={checkedIds} loading={messagesQuery.isLoading} onOpen={openMessage} onToggleCheck={toggleCheck} onToggleStar={toggleStar} onToggleRead={(id, unread) => setReadState([id], !unread)} onArchive={(id) => moveMessages([id], "archive")} onDelete={(id) => moveMessages([id], "trash")} onPrefetch={prefetchMessage} emptyHint={accountId ? "Esta cuenta todavía no tiene correos sincronizados. Pulsa Sincronizar o elige una cuenta con mensajes." : undefined} />
          {(pageRows.length < rows.length || messagesQuery.hasNextPage) && <div ref={loadMoreRef} className="border-t border-border px-3 py-2 text-center text-[11px] text-muted-foreground">{messagesQuery.isFetchingNextPage ? "Cargando correos anteriores…" : "Desplázate para cargar más"}</div>}
        </section>
        <section className={cn("mail-reading-panel min-w-0 flex-1 overflow-hidden border-l border-border bg-surface/30", selected ? "flex" : "hidden xl:flex")}><ReadingPane message={selected} account={selectedAccount} thread={selectedThread} onBack={() => setSelectedId(null)} onToggleStar={toggleStar} onArchive={(id) => moveMessages([id], "archive")} onDelete={(id) => moveMessages([id], "trash")} /></section>
      </div>
      <nav className="flex items-center justify-around border-t border-border bg-surface px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1.5 md:hidden"><BottomItem icon={Inbox} label="Todos" active={folder === "todos"} onClick={() => { setFolder("todos"); setSelectedId(null); }} /><BottomItem icon={MailOpen} label="No leídos" active={folder === "no-leidos"} onClick={() => { setFolder("no-leidos"); setSelectedId(null); }} /><BottomItem icon={AlertTriangle} label="Críticos" active={folder === "criticos"} onClick={() => { setFolder("criticos"); setSelectedId(null); }} /><Sheet><SheetTrigger asChild><button type="button" className="flex min-w-14 flex-col items-center gap-0.5 rounded-lg px-2 py-1 text-[10px] text-muted-foreground"><Users className="size-4" />Cuentas</button></SheetTrigger><SheetContent side="bottom" className="bg-surface p-3"><SheetTitle className="pb-2 text-sm">Cuentas conectadas</SheetTitle><AccountPicker accounts={accounts} value={accountId} onChange={selectAccount} className="w-full" /></SheetContent></Sheet><Sheet><SheetTrigger asChild><button type="button" className="flex min-w-14 flex-col items-center gap-0.5 rounded-lg px-2 py-1 text-[10px] text-muted-foreground"><Filter className="size-4" />Filtros</button></SheetTrigger><SheetContent side="bottom" className="max-h-[80vh] overflow-y-auto bg-surface p-0"><SheetTitle className="px-4 pt-4 text-sm">Filtros y orden</SheetTitle>{filtersPanel}</SheetContent></Sheet></nav>
    </div>
  </main>;
}

function BottomItem({ icon: Icon, label, active, onClick }: { icon: typeof Inbox; label: string; active: boolean; onClick: () => void }) {
  return <button type="button" onClick={onClick} aria-current={active ? "page" : undefined} className={cn("flex min-w-14 flex-col items-center gap-0.5 rounded-lg px-2 py-1 text-[10px] transition-colors", active ? "text-primary" : "text-muted-foreground")}><Icon className="size-4" />{label}</button>;
}

function providerFor(account: Account): Provider {
  if (account.provider === "gmail") return "gmail";
  const domain = account.email.split("@")[1]?.toLowerCase() ?? "";
  if (domain.includes("hotmail")) return "hotmail";
  if (domain.includes("live")) return "live";
  return "outlook";
}
function statusFor(status: Account["status"]): SyncStatus {
  return ({ connected: "conectada", syncing: "sincronizando", error: "error", reauth_required: "requiere-autorizacion", disconnected: "pausada" } as const)[status];
}
function mapAccount(account: Account): MailAccount {
  const provider = providerFor(account);
  return { id: account.id, alias: account.email.split("@")[0] || account.email, email: account.email, provider, client: "—", platform: provider === "gmail" ? "Google Gmail" : "Microsoft Mail", group: "Cuentas conectadas", country: "—", labels: [], favorite: false, status: statusFor(account.status), lastSync: account.last_synced_at ? new Date(account.last_synced_at).toLocaleString("es-PE") : "Pendiente", messageCount: account.message_count, statusDetail: account.last_error ?? (account.status === "error" ? "La última sincronización falló." : undefined) };
}
function categoryFor(value: string | null): FolderId[] {
  const normalized = (value ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const direct: Record<string, FolderId> = { pago: "pagos", pagos: "pagos", renovacion: "renovaciones", renovaciones: "renovaciones", seguridad: "seguridad", codigo: "codigos", codigos: "codigos", factura: "facturas", facturas: "facturas", marketing: "promociones", promociones: "promociones" };
  return direct[normalized] ? [direct[normalized]] : [];
}
function riskFor(value: Message["risk_level"]): Risk { return value === "critical" || value === "high" ? "alto" : value === "medium" ? "medio" : "bajo"; }
function mapMessage(message: Message, readIds: Set<string>, starredIds: Set<string>): MailMessage {
  const received = message.received_at ? new Date(message.received_at) : null;
  const risk = riskFor(message.risk_level);
  const categories = categoryFor(message.category);
  if (message.mailbox === "archive") categories.push("archivados");
  if (message.mailbox === "trash") categories.push("papelera");
  if (risk === "alto") categories.push("criticos");
  const sender = message.sender || "Remitente desconocido";
  return { id: message.id, threadId: message.thread_id || message.id, sender, senderName: sender.includes("@") ? sender.split("@")[0] : sender, subject: message.subject || "Sin asunto", preview: message.snippet || "Sin vista previa", body: message.body || message.snippet || "El proveedor no entregó contenido para este mensaje.", bodyHtml: message.body_html || undefined, accountId: message.account_id, to: message.account_email, date: received ? received.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—", time: received ? received.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" }) : "—", isoDate: received ? received.toISOString().slice(0, 10) : "", unread: !(message.is_read || readIds.has(message.id)), starred: message.is_starred || starredIds.has(message.id), critical: risk === "alto", risk, attachments: [], categories, aiSummary: message.category ? `Clasificado como ${message.category} con riesgo ${risk}.` : "Análisis pendiente.", aiAction: message.alert_count > 0 ? `Revisar ${message.alert_count} alerta${message.alert_count === 1 ? "" : "s"} asociada${message.alert_count === 1 ? "" : "s"}.` : "Sin acción registrada.", thread: [] };
}
