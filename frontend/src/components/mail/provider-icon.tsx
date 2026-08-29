import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/mail-data";
import gmailLogo from "@/assets/brands/gmail.svg";
import microsoftLogo from "@/assets/brands/microsoft.svg";

const providerStyles: Record<Provider, { label: string; logo: string }> = {
  gmail: { label: "Gmail", logo: gmailLogo },
  outlook: { label: "Outlook", logo: microsoftLogo },
  hotmail: { label: "Hotmail", logo: microsoftLogo },
  live: { label: "Live", logo: microsoftLogo },
};

export function ProviderIcon({
  provider,
  className,
}: {
  provider: Provider;
  className?: string;
}) {
  const style = providerStyles[provider];
  return (
    <span
      title={style.label}
      aria-label={style.label}
      className={cn(
        "grid shrink-0 place-items-center overflow-hidden rounded-[5px] bg-white p-[2px] ring-1 ring-border shadow-sm",
        className,
      )}
    >
      <img src={style.logo} alt="" className="size-full object-contain" />
    </span>
  );
}
