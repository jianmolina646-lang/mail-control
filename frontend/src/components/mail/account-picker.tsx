import { useState } from "react";
import { Check, ChevronDown, Inbox, Search, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { providerLabels, syncStatusLabels, type MailAccount } from "@/lib/mail-data";
import { ProviderIcon } from "@/components/mail/provider-icon";

export function filterPickerAccounts(accounts: MailAccount[], query: string, provider: string) {
  const term = query.trim().toLocaleLowerCase("es");
  return accounts.filter(a => (provider === "all" || (provider === "gmail" ? a.provider === "gmail" : a.provider !== "gmail")) && `${a.email} ${a.alias}`.toLocaleLowerCase("es").includes(term)).sort((a,b) => a.email.localeCompare(b.email, "es"));
}

export function AccountPicker({
  accounts,
  value,
  onChange,
  className,
}: {
  accounts: MailAccount[];
  value: string | null;
  onChange: (id: string | null) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("all");
  const selected = accounts.find((account) => account.id === value) ?? null;
  const visibleAccounts = filterPickerAccounts(accounts, query, provider);

  const totalMessages = accounts.reduce((total, account) => total + account.messageCount, 0);

  function selectAccount(id: string | null) {
    onChange(id);
    setOpen(false);
    setQuery(""); setProvider("all");
  }

  return (
    <Popover open={open} onOpenChange={next => { setOpen(next); if (!next) { setQuery(""); setProvider("all"); } }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Elegir correo"
          aria-expanded={open}
          className={cn(
            "flex h-11 min-w-0 items-center gap-2 rounded-lg border border-border bg-surface-2 px-2.5 text-[12.5px] text-foreground transition-colors hover:border-border-strong hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 md:h-9",
            className,
          )}
        >
          {selected ? (
            <ProviderIcon provider={selected.provider} className="size-4 shrink-0" />
          ) : (
            <Inbox className="size-4 shrink-0 text-muted-foreground" />
          )}
          <span className="truncate font-medium">{selected?.email ?? "Todas las cuentas"}</span>
          <ChevronDown className="ml-auto size-3.5 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        className="mail-account-menu w-[400px] max-w-[calc(100vw-1rem)] overflow-hidden border-border bg-popover p-0 shadow-lg"
      >
        <div className="border-b border-border px-4 py-3">
          <p className="text-[13px] font-semibold text-foreground">Tus cuentas de correo</p>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">Busca y abre la bandeja que necesitas</p>
          <div className="account-menu-search"><Search size={16} aria-hidden="true" /><input aria-label="Buscar cuenta por correo o nombre" placeholder="Buscar correo o nombre…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button type="button" aria-label="Limpiar búsqueda de cuentas" onClick={() => setQuery("")}><X size={16}/></button>}</div>
          <div className="account-menu-filters" role="group" aria-label="Filtrar cuentas por proveedor">{[["all", "Todas"], ["gmail", "Gmail"], ["microsoft", "Outlook / Hotmail"]].map(([id,label]) => <button key={id} type="button" aria-pressed={provider === id} onClick={() => setProvider(id)}>{label}</button>)}</div>
        </div>

        <div className="account-menu-unified">
          <AccountRow
            active={value === null}
            onClick={() => selectAccount(null)}
            title="Todas las cuentas"
            subtitle={`${accounts.length} cuentas · ${totalMessages.toLocaleString("es")} mensajes`}
          />
        </div>
        <p className="account-menu-count" role="status">{visibleAccounts.length} de {accounts.length} cuentas</p>
        <div aria-label="Cuentas de correo" className="account-menu-results scroll-slim overflow-y-auto p-1.5">
          {!visibleAccounts.length && <div className="account-menu-empty"><Inbox size={24} aria-hidden="true" /><strong>No encontramos cuentas</strong><span>Prueba otro correo o cambia el filtro.</span><button type="button" onClick={() => {setQuery("");setProvider("all");}}>Mostrar todas</button></div>}
          {visibleAccounts.map((account) => (
            <AccountRow
              key={account.id}
              active={account.id === value}
              onClick={() => selectAccount(account.id)}
              title={account.email}
              subtitle={`${providerLabels[account.provider]} · ${account.messageCount.toLocaleString("es")} mensajes`}
              account={account}
            />
          ))}

        </div>
      </PopoverContent>
    </Popover>
  );
}

function AccountRow({
  active,
  onClick,
  title,
  subtitle,
  account,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  subtitle: string;
  account?: MailAccount;
}) {
  return (
    <button
      type="button"
      aria-current={active ? "true" : undefined}
      onClick={onClick}
      className={cn("account-menu-row",
        "grid min-h-14 w-full grid-cols-[36px_minmax(0,1fr)_20px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40",
        active ? "bg-primary/12" : "hover:bg-surface-2",
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-full bg-surface-3">
        {account ? (
          <ProviderIcon provider={account.provider} className="size-4.5" />
        ) : (
          <Inbox className="size-4.5 text-muted-foreground" />
        )}
      </span>
      <span className="min-w-0">
        <span className="account-menu-email block text-[13px] font-medium text-foreground">{title}</span>
        <span className="mt-0.5 block truncate text-[11.5px] text-muted-foreground">{subtitle}</span>
        {account && <span className="account-menu-state" data-tone={account.status === "conectada" && !account.syncStale ? "good" : account.status === "sincronizando" ? "sync" : "warning"}><i aria-hidden="true" />{account.status === "conectada" && account.syncStale ? "Sincronización pendiente" : syncStatusLabels[account.status]}</span>}
      </span>
      {active ? <Check className="size-4 text-primary" aria-hidden="true" /> : <span />}
    </button>
  );
}
