import { cn } from "@/lib/utils";
import type { Provider } from "@/lib/mail-data";

export function GmailLogo({ className }: { className?: string }) {
  return <svg viewBox="0 0 48 48" className={className} aria-hidden="true"><path fill="#4285f4" d="M6 14v22a2 2 0 0 0 2 2h5V18.5L6 14z" /><path fill="#34a853" d="M42 14v22a2 2 0 0 1-2 2h-5V18.5L42 14z" /><path fill="#fbbc04" d="M13 38V18.5l11 8.2 11-8.2V38h-8V27l-3 2.2L21 27v11h-8z" /><path fill="#ea4335" d="M6 14a4 4 0 0 1 6.4-3.2L24 19.4l11.6-8.6A4 4 0 0 1 42 14L24 27.4 6 14z" /></svg>;
}

export function OutlookLogo({ className }: { className?: string }) {
  return <svg viewBox="0 0 48 48" className={className} aria-hidden="true"><path fill="#0364b8" d="M44 13.5v21a1.5 1.5 0 0 1-1.5 1.5H22V12h20.5a1.5 1.5 0 0 1 1.5 1.5z" /><path fill="#0f78d4" d="M44 20H22v8h22z" /><path fill="#28a8ea" d="M44 28H22v8h20.5a1.5 1.5 0 0 0 1.5-1.5z" /><rect x="4" y="9" width="22" height="30" rx="2.5" fill="#0a5ca4" /><path fill="#fff" d="M15 16.6c-3.2 0-5.4 2.9-5.4 7.4s2.2 7.4 5.4 7.4 5.4-2.9 5.4-7.4-2.2-7.4-5.4-7.4zm0 12c-1.7 0-2.8-1.8-2.8-4.6s1.1-4.6 2.8-4.6 2.8 1.8 2.8 4.6-1.1 4.6-2.8 4.6z" /></svg>;
}

export function AccountProviderLogo({ provider, className }: { provider: Provider; className?: string }) {
  return <span className={cn("flex shrink-0 items-center justify-center rounded-full border border-border bg-card", className)}>{provider === "gmail" ? <GmailLogo className="size-4" /> : <OutlookLogo className="size-4" />}</span>;
}

export function ProviderBrandLogo({ provider }: { provider: Provider }) {
  return provider === "gmail" ? <GmailLogo className="size-4" /> : <OutlookLogo className="size-4" />;
}
