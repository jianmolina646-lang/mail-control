import {
  AlertTriangle, Archive, Bookmark, CreditCard, FileText, Inbox, KeyRound,
  MailOpen, Megaphone, RefreshCcw, Shield, Star, Trash2, type LucideIcon,
} from "lucide-react";

export type FolderId = "todos" | "no-leidos" | "destacados" | "criticos" | "pagos" | "renovaciones" | "seguridad" | "codigos" | "facturas" | "promociones" | "archivados" | "papelera" | "vistas";
export type FolderGroup = "principal" | "categorias" | "sistema";
export interface Folder { id: FolderId; label: string; icon: LucideIcon; group: FolderGroup; showCount?: boolean; }
export const folders: Folder[] = [
  { id: "todos", label: "Todos los mensajes", icon: Inbox, group: "principal", showCount: true },
  { id: "no-leidos", label: "No leídos", icon: MailOpen, group: "principal", showCount: true },
  { id: "destacados", label: "Destacados", icon: Star, group: "principal", showCount: true },
  { id: "criticos", label: "Críticos", icon: AlertTriangle, group: "categorias", showCount: true },
  { id: "pagos", label: "Pagos", icon: CreditCard, group: "categorias", showCount: true },
  { id: "renovaciones", label: "Renovaciones", icon: RefreshCcw, group: "categorias", showCount: true },
  { id: "seguridad", label: "Seguridad", icon: Shield, group: "categorias", showCount: true },
  { id: "codigos", label: "Códigos", icon: KeyRound, group: "categorias", showCount: true },
  { id: "facturas", label: "Facturas", icon: FileText, group: "categorias", showCount: true },
  { id: "promociones", label: "Promociones", icon: Megaphone, group: "categorias" },
  { id: "archivados", label: "Archivados", icon: Archive, group: "sistema" },
  { id: "papelera", label: "Papelera", icon: Trash2, group: "sistema" },
  { id: "vistas", label: "Vistas guardadas", icon: Bookmark, group: "sistema" },
];
export const folderGroupLabels: Record<FolderGroup, string> = { principal: "Bandeja", categorias: "Clasificación", sistema: "Sistema" };

export type Provider = "gmail" | "outlook" | "hotmail" | "live";
export type SyncStatus = "conectada" | "sincronizando" | "requiere-autorizacion" | "credenciales-vencidas" | "error" | "pausada";
export const providerLabels: Record<Provider, string> = { gmail: "Gmail", outlook: "Outlook", hotmail: "Hotmail", live: "Live" };
export const syncStatusLabels: Record<SyncStatus, string> = { conectada: "Conectada", sincronizando: "Sincronizando", "requiere-autorizacion": "Requiere autorización", "credenciales-vencidas": "Credenciales vencidas", error: "Error de sincronización", pausada: "Pausada" };
export const attentionStatuses: SyncStatus[] = ["requiere-autorizacion", "credenciales-vencidas", "error", "pausada"];
export interface MailAccount { id: string; alias: string; email: string; provider: Provider; client: string; platform: string; group: string; country: string; labels: string[]; favorite: boolean; status: SyncStatus; lastSync: string; syncStale?: boolean; messageCount: number; statusDetail?: string; }

export type Risk = "alto" | "medio" | "bajo";
export interface ThreadEntry { id: string; senderName: string; date: string; body: string; }
export interface MailMessage { id: string; threadId: string; sender: string; senderName: string; subject: string; preview: string; body: string; bodyHtml?: string; accountId: string; to: string; cc?: string; date: string; time: string; isoDate: string; unread: boolean; starred: boolean; critical?: boolean; risk: Risk; attachments: import("./types").Attachment[]; categories: FolderId[]; aiSummary: string; aiAction: string; thread?: ThreadEntry[]; }

export interface SavedView { id: string; label: string; query: string; }
export const savedViews: SavedView[] = [
  { id: "v1", label: "Pagos críticos", query: "categoria:pagos riesgo:alto" },
  { id: "v2", label: "Cuentas Hotmail", query: "proveedor:hotmail" },
  { id: "v3", label: "No leídos", query: "estado:no-leido" },
  { id: "v4", label: "Seguridad", query: "categoria:seguridad" },
];
export const categoryLabels: Partial<Record<FolderId, string>> = { criticos: "Crítico", pagos: "Pagos", renovaciones: "Renovaciones", seguridad: "Seguridad", codigos: "Códigos", facturas: "Facturas", promociones: "Promociones", archivados: "Archivado", papelera: "Papelera" };
