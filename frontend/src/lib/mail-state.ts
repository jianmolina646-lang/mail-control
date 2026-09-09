import type { Account, Message } from "./types";
import { folders, type FolderId, type MailAccount, type MailMessage, type Provider, type SyncStatus } from "./mail-data";
import { parseQuery } from "./mail-search";

export function scopedIds(ids: Iterable<string>, visibleIds: Iterable<string>) {
  const visible = new Set(visibleIds);
  return [...new Set(ids)].filter((id) => visible.has(id));
}

export function folderFrom(value: string | null): FolderId {
  return folders.some((folder) => folder.id === value) ? value as FolderId : "todos";
}

export function mailFilters(raw: string, accountId: string | null, folder: FolderId) {
  const { text, ops } = parseQuery(raw);
  const params = new URLSearchParams({ mailbox: folder === "archivados" ? "archive" : folder === "papelera" ? "trash" : "inbox" });
  const errors: string[] = [];
  if (accountId) params.set("account_id", accountId);
  if (text) params.set("search", text);
  const names: Record<string, string> = { cuenta: "account", correo: "account", proveedor: "provider", plataforma: "platform", categoria: "category", desde: "date_from", hasta: "date_to", de: "sender", para: "recipient" };
  for (const [key, value] of Object.entries(ops)) {
    if (names[key]) {
      if ((key === "desde" || key === "hasta") && !/^\d{4}-\d{2}-\d{2}$/.test(value)) errors.push(`Usa ${key}:AAAA-MM-DD.`);
      else params.set(names[key], value);
    } else if (key === "estado" && ["leido", "leído", "no-leido", "no-leído"].includes(value)) params.set("is_read", String(!value.startsWith("no")));
    else if (key === "riesgo" && ["alto", "medio", "bajo", "critico", "crítico"].includes(value)) params.set("risk_level", ({ alto: "high,critical", medio: "medium", bajo: "low", critico: "critical", crítico: "critical" } as Record<string, string>)[value]);
    else if (key === "tiene" && value.startsWith("adj")) params.set("has_attachments", "true");
    else errors.push(`El filtro «${key}:${value}» no está disponible.`);
  }
  if (folder === "no-leidos") params.set("is_read", "false");
  else if (folder === "destacados") params.set("is_starred", "true");
  else if (folder === "criticos") params.set("risk_level", "high,critical");
  else if (["pagos", "renovaciones", "seguridad", "codigos", "facturas", "promociones"].includes(folder)) params.set("category", folder);
  return { params, error: errors.join(" ") };
}

export function syncAge(timestamp: string | null, now = Date.now()) {
  if (!timestamp || !Number.isFinite(Date.parse(timestamp))) return { stale: true, label: "Sin sincronización registrada" };
  const seconds = Math.max(0, Math.floor((now - Date.parse(timestamp)) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const age = [days ? `${days} d` : "", hours ? `${hours} h` : "", `${minutes} min`, `${seconds % 60} s`].filter(Boolean).join(" ");
  return { stale: seconds > 900, label: `Hace ${age} · ${new Date(timestamp).toLocaleString("es-PE")}` };
}

export function providerFor(account: Account): Provider {
  if (account.provider === "gmail") return "gmail";
  const domain = account.email.split("@")[1]?.toLowerCase() ?? "";
  return domain.includes("hotmail") ? "hotmail" : domain.includes("live") ? "live" : "outlook";
}

export function mapAccount(account: Account, now = Date.now()): MailAccount {
  const provider = providerFor(account);
  const sync = syncAge(account.last_synced_at, now);
  const status: SyncStatus = ({ connected: "conectada", syncing: "sincronizando", error: "error", reauth_required: "requiere-autorizacion", disconnected: "pausada" } as const)[account.status];
  return { id: account.id, alias: account.email.split("@")[0] || account.email, email: account.email, provider, client: "Sin asignar", platform: provider === "gmail" ? "Google Gmail" : "Microsoft Mail", group: "Cuentas conectadas", country: "—", labels: [], favorite: false, status, lastSync: sync.label, syncStale: sync.stale, messageCount: account.message_count, statusDetail: account.last_error ?? (sync.stale ? "Sincronización pendiente de actualizar." : undefined) };
}

export function categoryFor(value: string | null): FolderId[] {
  const normalized = (value ?? "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const direct: Record<string, FolderId> = { payment: "pagos", payments: "pagos", pago: "pagos", pagos: "pagos", renewal: "renovaciones", renovacion: "renovaciones", renovaciones: "renovaciones", security: "seguridad", seguridad: "seguridad", verification: "codigos", verification_code: "codigos", code: "codigos", codigo: "codigos", codigos: "codigos", invoice: "facturas", factura: "facturas", facturas: "facturas", marketing: "promociones", promociones: "promociones", promotion: "promociones" };
  return direct[normalized] ? [direct[normalized]] : [];
}

export function mapMessage(message: Message): MailMessage {
  const received = message.received_at ? new Date(message.received_at) : null;
  const risk = message.risk_level === "critical" || message.risk_level === "high" ? "alto" : message.risk_level === "medium" ? "medio" : "bajo";
  const categories = categoryFor(message.category);
  if (message.mailbox === "archive") categories.push("archivados");
  if (message.mailbox === "trash") categories.push("papelera");
  if (risk === "alto") categories.push("criticos");
  const sender = message.sender || "Remitente desconocido";
  return { id: message.id, threadId: message.thread_id || message.id, sender, senderName: sender.includes("@") ? sender.split("@")[0] : sender, subject: message.subject || "Sin asunto", preview: message.snippet || "Sin vista previa", body: message.body || "El proveedor no entregó texto para este mensaje.", bodyHtml: message.body_html || undefined, accountId: message.account_id, to: message.to?.join(", ") || "Destinatarios no disponibles", cc: message.cc?.join(", ") || "", date: received ? received.toLocaleDateString("es-PE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—", time: received ? received.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" }) : "—", isoDate: received?.toISOString() ?? "", unread: !message.is_read, starred: message.is_starred, critical: risk === "alto", risk, attachments: message.attachments ?? [], categories, aiSummary: message.category ? `Clasificado como ${message.category} con riesgo ${risk}.` : "Análisis pendiente.", aiAction: "", thread: [] };
}
