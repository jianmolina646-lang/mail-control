import { useState } from "react";
import { cn } from "@/lib/utils";
import { ProviderIcon } from "@/components/mail/provider-icon";
import { attentionStatuses, syncStatusLabels, type MailAccount } from "@/lib/mail-data";

export function SyncAlerts({ accounts, showAll = false, onSelectAccount, onRetry, onReauthorize, onConfigure, className }: {
  accounts: MailAccount[];
  showAll?: boolean;
  onSelectAccount: (id: string) => void;
  onRetry?: (id: string) => void | Promise<void>;
  onReauthorize?: (id: string) => void | Promise<void>;
  onConfigure?: () => void;
  className?: string;
}) {
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const visible = accounts.filter(a => showAll || attentionStatuses.includes(a.status) || a.syncStale || a.syncPending);
  async function run(id: string, action: (id: string) => void | Promise<void>) {
    if (pending) return;
    setPending(id); setError("");
    try { await action(id); } catch { setError("No se pudo completar la acción. Inténtalo de nuevo."); }
    finally { setPending(null); }
  }
  if (!visible.length) return null;
  return <section className={cn("mail-sync-status", className)} aria-label="Estado de sincronización">
    {error && <p role="alert">{error}</p>}
    {visible.map(a => {
      const needsAuth = a.status === "requiere-autorizacion" || a.status === "credenciales-vencidas";
      const warning = attentionStatuses.includes(a.status) || a.syncStale;
      const initialSync = a.syncPending && !warning && (a.status === "conectada" || a.status === "sincronizando");
      return <div key={a.id} className="mail-sync-status-row" data-warning={!!warning}>
        <ProviderIcon provider={a.provider} className="size-4" />
        <div className="min-w-0 flex-1"><button type="button" className="mail-sync-account" onClick={() => onSelectAccount(a.id)}>{a.email}</button>
          <p>{initialSync ? a.status === "sincronizando" ? "Primera sincronización en curso" : "Primera sincronización pendiente" : a.syncStale && a.status === "conectada" ? "Conectada · sincronización atrasada" : syncStatusLabels[a.status]}</p>
          <p>Última sincronización: {a.lastSync}</p>
          {warning && <p>{needsAuth ? "Vuelve a autorizar el acceso para recibir nuevos correos." : a.status === "pausada" ? "Revisa la conexión desde Cuentas." : "Revisa el estado o solicita una sincronización."}</p>}
          {a.statusDetail && <details><summary>Detalles</summary><p className="break-words">{a.statusDetail}</p></details>}
        </div>
        <div className="mail-sync-actions">
          {needsAuth && onReauthorize && <button type="button" disabled={!!pending} onClick={() => void run(a.id, onReauthorize)}>{pending === a.id ? "Abriendo…" : "Reautorizar"}</button>}
          {!needsAuth && a.status !== "pausada" && a.status !== "sincronizando" && onRetry && <button type="button" disabled={!!pending} onClick={() => void run(a.id, onRetry)}>{pending === a.id ? "Solicitando…" : "Sincronizar"}</button>}
          {onConfigure && <button type="button" onClick={() => { onSelectAccount(a.id); onConfigure(); }}>Configurar</button>}
        </div>
      </div>;
    })}
  </section>;
}
