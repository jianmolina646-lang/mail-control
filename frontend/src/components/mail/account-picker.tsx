import { useState } from "react";
import { Check, ChevronDown, Inbox } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { providerLabels, type MailAccount } from "@/lib/mail-data";
import { ProviderIcon } from "@/components/mail/provider-icon";

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
  const selected = accounts.find((account) => account.id === value) ?? null;
  const visibleAccounts = [...accounts].sort((a, b) => a.email.localeCompare(b.email, "es"));

  const totalMessages = accounts.reduce((total, account) => total + account.messageCount, 0);

  function selectAccount(id: string | null) {
    onChange(id);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
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
        className="w-[360px] max-w-[calc(100vw-1rem)] overflow-hidden border-border bg-popover p-0 shadow-lg"
      >
        <div className="border-b border-border px-4 py-3">
          <p className="text-[13px] font-semibold text-foreground">Elegir correo</p>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">Selecciona la bandeja que quieres leer</p>
        </div>

        <div aria-label="Cuentas de correo" className="scroll-slim max-h-[400px] overflow-y-auto p-1.5">
          <AccountRow
            active={value === null}
            onClick={() => selectAccount(null)}
            title="Todas las cuentas"
            subtitle={`${accounts.length} cuentas · ${totalMessages.toLocaleString("es")} mensajes`}
          />

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
      className={cn(
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
        <span className="block truncate text-[13px] font-medium text-foreground">{title}</span>
        <span className="mt-0.5 block truncate text-[11.5px] text-muted-foreground">{subtitle}</span>
      </span>
      {active ? <Check className="size-4 text-primary" aria-hidden="true" /> : <span />}
    </button>
  );
}
