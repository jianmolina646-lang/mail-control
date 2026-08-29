import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Archive,
  ArrowLeft,
  Check,
  Copy,
  Inbox,
  KeyRound,
  Paperclip,
  Sparkles,
  Star,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProviderIcon } from "@/components/mail/provider-icon";
import { cn } from "@/lib/utils";
import { apiBlob } from "@/lib/api";
import type { MailAccount, MailMessage } from "@/lib/mail-data";

interface ReadingPaneProps {
  message: MailMessage | null;
  account?: MailAccount | undefined;
  thread: MailMessage[];
  onBack: () => void;
  onToggleStar: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ReadingPane({
  message,
  account,
  thread,
  onBack,
  onToggleStar,
  onArchive,
  onDelete,
}: ReadingPaneProps) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const codes = useMemo(() => message ? extractCodes(`${message.subject}\n${message.preview}\n${message.body}\n${stripHtml(message.bodyHtml ?? "")}`) : [], [message]);
  async function copyCode(code: string) {
    await navigator.clipboard.writeText(code);
    setCopiedCode(code);
    window.setTimeout(() => setCopiedCode(null), 1800);
  }
  if (!message) {
    return (
      <div className="mail-reading-empty flex h-full flex-col items-center justify-center gap-5 px-8 text-center">
        <span className="mail-reading-empty__icon grid size-16 place-items-center rounded-2xl bg-surface-2 text-muted-foreground ring-1 ring-border">
          <Inbox className="size-7" />
        </span>
        <div className="space-y-1.5">
          <p className="text-[15px] font-semibold tracking-tight text-foreground">Selecciona un mensaje</p>
          <p className="mx-auto max-w-xs text-[12.5px] leading-relaxed text-muted-foreground">
            El contenido completo aparecerá aquí.
          </p>
        </div>
      </div>
    );
  }

  return (
    <article className="flex h-full min-h-0 flex-col bg-surface/20">
      <div className="flex h-12 shrink-0 items-center gap-1 border-b border-border px-3 sm:px-4">
        <ToolbarButton icon={ArrowLeft} label="Volver a la bandeja" onClick={onBack} />
        <ToolbarButton icon={Archive} label="Archivar" onClick={() => onArchive(message.id)} />
        <ToolbarButton icon={Trash2} label="Eliminar" onClick={() => onDelete(message.id)} />
        <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
          {message.date} · {message.time}
        </span>
      </div>

      <div className="scroll-slim min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-5 py-5 sm:px-8 sm:py-7">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-1.5">
                {message.critical && (
                  <span className="rounded bg-destructive/12 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-destructive">
                    Crítico
                  </span>
                )}
                <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                  Riesgo {message.risk}
                </span>
              </div>
              <h2 className="text-[22px] font-semibold leading-tight tracking-[-0.025em] text-foreground sm:text-[24px]">
                {message.subject}
              </h2>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label={message.starred ? "Quitar destacado" : "Destacar mensaje"}
              onClick={() => onToggleStar(message.id)}
              className="size-10 shrink-0 rounded-full"
            >
              <Star className={cn("size-4.5", message.starred && "fill-warning text-warning")} />
            </Button>
          </div>

          <div className="mt-5 flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-surface-3 ring-1 ring-border">
              {account ? (
                <ProviderIcon provider={account.provider} className="size-4.5" />
              ) : (
                <Inbox className="size-4.5 text-muted-foreground" />
              )}
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <p className="truncate text-[13.5px] font-semibold text-foreground">
                {message.senderName}
                <span className="ml-1.5 font-normal text-muted-foreground">&lt;{message.sender}&gt;</span>
              </p>
              <details className="group mt-0.5 text-[11.5px] text-muted-foreground">
                <summary className="w-fit cursor-pointer list-none rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
                  para {message.to} <span aria-hidden="true">⌄</span>
                </summary>
                <div className="mt-2 grid gap-1 rounded-lg bg-surface-2 px-3 py-2 text-[11.5px] sm:grid-cols-2">
                  <p><span className="text-foreground/70">De:</span> {message.sender}</p>
                  <p><span className="text-foreground/70">Para:</span> {message.to}</p>
                  <p><span className="text-foreground/70">Cuenta:</span> {account?.email ?? "—"}</p>
                  <p><span className="text-foreground/70">Fecha:</span> {message.date} {message.time}</p>
                </div>
              </details>
            </div>
          </div>

          {codes.length > 0 && (
            <section className="mt-5 rounded-xl border border-primary/25 bg-primary/[0.06] p-3" aria-label="Códigos detectados">
              <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-primary"><KeyRound className="size-4" /> Código detectado</div>
              <div className="flex flex-wrap gap-2">{codes.map((code) => <button key={code} type="button" onClick={() => void copyCode(code)} className="flex items-center gap-2 rounded-lg border border-primary/20 bg-card px-3 py-2 font-mono text-lg font-bold tracking-[0.16em] text-foreground shadow-sm transition hover:border-primary/50"><span>{code}</span>{copiedCode === code ? <Check className="size-4 text-primary" /> : <Copy className="size-4 text-muted-foreground" />}</button>)}</div>
              <p className="mt-1.5 text-[10.5px] text-muted-foreground">Pulsa el código para copiarlo.</p>
            </section>
          )}

          {message.bodyHtml ? (
            <EmailHtml key={message.id} messageId={message.id} subject={message.subject} html={message.bodyHtml} />
          ) : (
            <div className="mt-7 min-h-32 max-w-[72ch] whitespace-pre-wrap break-words text-[14.5px] leading-7 text-foreground/90">
              {message.body}
            </div>
          )}

          {message.attachments.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {message.attachments.map((file) => (
                <span key={file} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-[12px] text-foreground/85">
                  <Paperclip className="size-3.5 text-muted-foreground" /> {file}
                </span>
              ))}
            </div>
          )}

          <Link to={`/analisis?message_id=${encodeURIComponent(message.id)}`} className="mt-8 flex items-center justify-between rounded-xl border border-primary/20 bg-primary/[0.05] p-3 text-[12px] font-semibold text-primary transition-colors hover:border-primary/35 hover:bg-primary/[0.08]">
            <span className="flex items-center gap-1.5"><Sparkles className="size-3.5" /> Ver análisis IA separado</span>
            <span aria-hidden="true">→</span>
          </Link>

          {(thread.length > 1 || (message.thread?.length ?? 0) > 0) && (
            <section className="mt-6 space-y-2">
              <p className="text-[12px] font-semibold text-foreground">Conversación</p>
              {thread.filter((item) => item.id !== message.id).map((item) => (
                <details key={item.id} className="rounded-xl border border-border px-3 py-2">
                  <summary className="cursor-pointer list-none text-[12.5px] text-foreground/85">
                    <span className="font-medium">{item.senderName}</span>
                    <span className="text-muted-foreground"> · {item.date}</span>
                  </summary>
                  <p className="mt-3 whitespace-pre-wrap text-[13px] leading-6 text-muted-foreground">{item.body}</p>
                </details>
              ))}
            </section>
          )}
        </div>
      </div>
    </article>
  );
}

function stripHtml(html: string) {
  return html.replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<[^>]+>/g, " ").replace(/&nbsp;|&#160;/gi, " ");
}

function extractCodes(text: string) {
  const context = text.replace(/\s+/g, " ");
  const candidates = [...context.matchAll(/(?:c[oó]digo|code|pin|verification|verificaci[oó]n|inicio de sesi[oó]n)[^A-Z0-9]{0,40}([A-Z0-9](?:[ -]?[A-Z0-9]){3,9})/gi)]
    .map((match) => match[1]?.replace(/[ -]/g, "").toUpperCase())
    .filter((value): value is string => !!value && /\d/.test(value) && value.length >= 4 && value.length <= 10);
  return [...new Set(candidates)].slice(0, 4);
}

function EmailHtml({ messageId, subject, html }: { messageId: string; subject: string; html: string }) {
  const [height, setHeight] = useState(420);
  const [frameScrollable, setFrameScrollable] = useState(false);
  const [proxiedHtml, setProxiedHtml] = useState(html);
  const [loadingImages, setLoadingImages] = useState(true);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];
    async function proxyImages() {
      const document = new DOMParser().parseFromString(html, "text/html");
      const images = [...document.querySelectorAll("img")];
      let remoteIndex = 0;
      const jobs = images.map(async (image) => {
        const source = image.getAttribute("src") ?? "";
        if (!/^https?:\/\//i.test(source)) return;
        const imageIndex = remoteIndex++;
        const width = Number.parseInt(image.getAttribute("width") ?? "", 10);
        const height = Number.parseInt(image.getAttribute("height") ?? "", 10);
        if ((Number.isFinite(width) && width <= 2) || (Number.isFinite(height) && height <= 2)) {
          image.remove();
          return;
        }
        try {
          const blob = await apiBlob(`/v1/mail/messages/${encodeURIComponent(messageId)}/images/${imageIndex}`);
          const objectUrl = URL.createObjectURL(blob);
          objectUrls.push(objectUrl);
          image.setAttribute("src", objectUrl);
          image.removeAttribute("srcset");
        } catch {
          image.removeAttribute("src");
          image.removeAttribute("srcset");
        }
      });
      await Promise.all(jobs);
      if (!cancelled) {
        setProxiedHtml(document.documentElement.outerHTML);
        setLoadingImages(false);
      }
    }
    void proxyImages();
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [html, messageId]);

  function resizeFrame() {
    const document = frameRef.current?.contentDocument;
    if (!document) return;
    const contentHeight = Math.max(
      220,
      document.documentElement.scrollHeight,
      document.body?.scrollHeight ?? 0,
    );
    const maximumHeight = Math.max(480, Math.min(1800, window.innerHeight * 1.75));
    setFrameScrollable(contentHeight > maximumHeight);
    setHeight(Math.min(contentHeight, maximumHeight));
  }

  return (
    <section className="mt-7 overflow-hidden rounded-xl border border-border bg-white">
      {loadingImages && <div className="border-b border-border bg-surface-2 px-3 py-2 text-[11.5px] text-muted-foreground">Cargando imágenes de forma segura…</div>}
      <iframe
        ref={frameRef}
        title={`Contenido de ${subject}`}
        srcDoc={emailDocument(proxiedHtml)}
        sandbox="allow-same-origin allow-popups"
        referrerPolicy="no-referrer"
        scrolling={frameScrollable ? "auto" : "no"}
        onLoad={() => {
          resizeFrame();
          const body = frameRef.current?.contentDocument?.body;
          if (!body || typeof ResizeObserver === "undefined") return;
          const observer = new ResizeObserver(resizeFrame);
          observer.observe(body);
          window.setTimeout(() => observer.disconnect(), 10000);
        }}
        style={{ height }}
        className="block w-full bg-white"
      />
    </section>
  );
}

function emailDocument(html: string) {
  const headContent = `
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; media-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      html { color-scheme: light; background: #fff; }
      body { margin: 0; padding: 24px; color: #202124; background: #fff; overflow-wrap: anywhere; }
      img { max-width: 100%; height: auto; }
      table { max-width: 100%; }
      pre { white-space: pre-wrap; }
    </style>`;
  if (/<head[\s>]/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${headContent}`);
  }
  if (/<html[\s>]/i.test(html)) {
    return html.replace(/<html([^>]*)>/i, `<html$1><head>${headContent}</head>`);
  }
  if (/<body[\s>]/i.test(html)) {
    return `<!doctype html><html><head>${headContent}</head>${html}</html>`;
  }
  return `<!doctype html><html><head>${headContent}</head><body>${html}</body></html>`;
}

function ToolbarButton({
  icon: Icon,
  label,
  onClick,
  className,
}: {
  icon: typeof Archive;
  label: string;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-11 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-surface-3 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:size-9",
        className,
      )}
    >
      <Icon className="size-4" />
    </button>
  );
}
