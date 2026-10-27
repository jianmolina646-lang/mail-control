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
  Maximize2,
  Minimize2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProviderIcon } from "@/components/mail/provider-icon";
import { cn } from "@/lib/utils";
import { apiBlob } from "@/lib/api";
import { useReadingPreference } from "@/lib/reading-preferences";
import type { MailAccount, MailMessage } from "@/lib/mail-data";
import type { Attachment } from "@/lib/types";
import { extractCodes } from "@/lib/extract-codes";

interface ReadingPaneProps {
  expanded?: boolean;
  onToggleExpand?: () => void;
  message: MailMessage | null;
  account?: MailAccount | undefined;
  thread: MailMessage[];
  onBack: () => void;
  onToggleStar: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  loading?: boolean;
  error?: string;
  onRetry: () => void;
  threadLoading?: boolean;
  threadError?: boolean;
  onRetryThread: () => void;
  onOpenThread: (id: string) => void;
  hasMoreThread?: boolean;
  loadingMoreThread?: boolean;
  onLoadMoreThread: () => void;
  returnSearch?: string;
  contentWarning?: string | null;
  attachmentsError?: string | null;
}

export function ReadingPane({
  message,
  account,
  thread,
  onBack,
  onToggleStar,
  onArchive,
  onDelete,
  loading, error, onRetry, threadLoading, threadError, onRetryThread, onOpenThread,
  hasMoreThread, loadingMoreThread, onLoadMoreThread, returnSearch,
  contentWarning, attachmentsError,
  expanded, onToggleExpand,
}: ReadingPaneProps) {
  const [textOnly, setTextOnly] = useReadingPreference("text", false, [false, true]);
  const [fontScale, setFontScale] = useReadingPreference<number>("scale", 1, [1, 1.15, 1.3, 1.5]);
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = 0; }, [message?.id]);
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
    <article className="mail-reader flex h-full min-h-0 w-full min-w-0 flex-1 flex-col bg-surface/20">
      <div className="mail-reader-toolbar flex shrink-0 items-center gap-1 border-b border-border px-3 sm:px-4">
        <ToolbarButton icon={ArrowLeft} label="Volver a la bandeja" onClick={onBack} />
        <ToolbarButton icon={Archive} label="Archivar" onClick={() => onArchive(message.id)} />
        <ToolbarButton icon={Trash2} label="Eliminar" onClick={() => onDelete(message.id)} />
        <div className="ml-auto flex flex-wrap items-center gap-1">
          <button type="button" className="reader-control" aria-pressed={textOnly} onClick={() => setTextOnly(!textOnly)}>{textOnly ? "Ver original" : "Solo texto"}</button>
          <label className="sr-only" htmlFor="reader-font-size">Tamaño de lectura</label>
          <select id="reader-font-size" className="reader-control" value={fontScale} onChange={event => setFontScale(Number(event.target.value))}><option value={1}>100%</option><option value={1.15}>115%</option><option value={1.3}>130%</option><option value={1.5}>150%</option></select>
          {onToggleExpand && <button type="button" className="reader-control reader-expand-label" aria-pressed={expanded} onClick={onToggleExpand}>{expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}{expanded ? "Volver a vista dividida" : "Ampliar lectura"}</button>}
        </div>
      </div>

      <div ref={scrollRef} className="mail-reader-scroll scroll-slim min-h-0 flex-1 overflow-y-auto">
        <div className="mail-reader-document w-full max-w-none px-5 py-5 sm:px-8 sm:py-7">
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
              <p className="break-words text-[13.5px] font-semibold text-foreground">
                {message.senderName}
                <span className="ml-1.5 font-normal text-muted-foreground">&lt;{message.sender}&gt;</span>
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">{message.date} · {message.time}</p>
              <details className="group mt-0.5 text-[11.5px] text-muted-foreground">
                <summary className="w-fit cursor-pointer list-none rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
                  para {message.to} <span aria-hidden="true">⌄</span>
                </summary>
                <div className="mt-2 grid gap-1 rounded-lg bg-surface-2 px-3 py-2 text-[11.5px] sm:grid-cols-2">
                  <p><span className="text-foreground/70">De:</span> {message.sender}</p>
                  <p><span className="text-foreground/70">Para:</span> {message.to}</p>
                  {message.cc && <p><span className="text-foreground/70">Cc:</span> {message.cc}</p>}
                  <p><span className="text-foreground/70">Cuenta:</span> {account?.email ?? "—"}</p>
                  <p><span className="text-foreground/70">Fecha:</span> {message.date} {message.time}</p>
                </div>
              </details>
            </div>
          </div>

          {!loading && !error && codes.length > 0 && (
            <section className="mt-5 rounded-xl border border-primary/25 bg-primary/[0.06] p-3" aria-label="Códigos detectados">
              <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-primary"><KeyRound className="size-4" /> Código detectado</div>
              <div className="flex flex-wrap gap-2">{codes.map((code) => <button key={code} type="button" onClick={() => void copyCode(code)} className="flex items-center gap-2 rounded-lg border border-primary/20 bg-card px-3 py-2 font-mono text-lg font-bold tracking-[0.16em] text-foreground shadow-sm transition hover:border-primary/50"><span>{code}</span>{copiedCode === code ? <Check className="size-4 text-primary" /> : <Copy className="size-4 text-muted-foreground" />}</button>)}</div>
              <p className="mt-1.5 text-[10.5px] text-muted-foreground">Pulsa el código para copiarlo.</p>
            </section>
          )}

          {contentWarning && <div role="alert" className="mt-5 rounded-xl border border-warning/30 bg-warning/10 p-3 text-[12px] text-foreground">{contentWarning} <button type="button" onClick={onRetry} className="underline">Reintentar contenido</button></div>}
          {attachmentsError && <div role="alert" className="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-3 text-[12px] text-foreground">{attachmentsError} <button type="button" onClick={onRetry} className="underline">Reintentar adjuntos</button></div>}
          {loading ? <p role="status" className="mt-7 text-sm text-muted-foreground">Cargando contenido completo…</p> : error ? <div role="alert" className="mt-7 rounded-xl border border-destructive/30 p-4 text-sm text-destructive">{error}<button type="button" className="ml-3 underline" onClick={onRetry}>Reintentar contenido</button></div> : message.bodyHtml && !textOnly ? (
            <EmailHtml key={message.id} messageId={message.id} subject={message.subject} html={message.bodyHtml} attachments={message.attachments} fontScale={fontScale} />
          ) : (
            <div style={{fontSize: 16 * fontScale, lineHeight: 1.75}} className="mt-7 min-h-32 max-w-[72ch] whitespace-pre-wrap break-words text-foreground/90">
              {message.body || readableText(message.bodyHtml ?? "")}
            </div>
          )}

          {!loading && !error && message.attachments.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {message.attachments.map((file) => (
                <AttachmentDownload key={file.id} attachment={file} />
              ))}
            </div>
          )}

          <Link to={`/analisis?message_id=${encodeURIComponent(message.id)}&return_to=${encodeURIComponent(`/correos${returnSearch ? `?${returnSearch}` : ""}`)}`} className="mt-8 flex items-center justify-between rounded-xl border border-primary/20 bg-primary/[0.05] p-3 text-[12px] font-semibold text-primary transition-colors hover:border-primary/35 hover:bg-primary/[0.08]">
            <span className="flex items-center gap-1.5"><Sparkles className="size-3.5" /> Ver análisis IA separado</span>
            <span aria-hidden="true">→</span>
          </Link>

          {(thread.length > 1 || threadLoading || threadError || hasMoreThread) && (
            <section className="mt-6 space-y-2">
              <p className="text-[12px] font-semibold text-foreground">Conversación</p>
              {threadLoading && <p role="status" className="text-[12px] text-muted-foreground">Cargando conversación…</p>}
              {threadError && <p role="alert" className="text-[12px] text-destructive">No se pudo cargar la conversación. <button type="button" className="underline" onClick={onRetryThread}>Reintentar conversación</button></p>}
              {thread.filter((item) => item.id !== message.id).map((item) => (
                <button type="button" key={item.id} onClick={() => onOpenThread(item.id)} className="block w-full rounded-xl border border-border px-3 py-3 text-left hover:bg-surface-2">
                  <span className="text-[12.5px] text-foreground/85">
                    <span className="font-medium">{item.senderName}</span>
                    <span className="text-muted-foreground"> · {item.date}</span>
                  </span>
                  <span className="mt-1 block text-[12px] text-muted-foreground">{item.subject} · Abrir mensaje completo</span>
                </button>
              ))}
              {hasMoreThread && <Button variant="ghost" size="sm" disabled={loadingMoreThread} onClick={onLoadMoreThread}>{loadingMoreThread ? "Cargando conversación…" : "Cargar más de la conversación"}</Button>}
            </section>
          )}
        </div>
      </div>
    </article>
  );
}

export function AttachmentDownload({ attachment }: { attachment: Attachment }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  async function download() {
    setDownloading(true); setError("");
    try {
      if (!attachment.download_url.startsWith("/v1/mail/messages/")) throw new Error("El adjunto no tiene una ruta de descarga válida.");
      const blob = await apiBlob(attachment.download_url);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = attachment.filename || "adjunto";
      document.body.append(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo descargar el adjunto."); }
    finally { setDownloading(false); }
  }
  return <div><button type="button" onClick={() => void download()} disabled={downloading} className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-[12px] text-foreground/85 hover:bg-surface-2 disabled:opacity-50"><Paperclip className="size-3.5 text-muted-foreground" />{downloading ? "Descargando…" : attachment.filename}<span className="text-muted-foreground">{attachment.size != null ? `${Math.max(1, Math.ceil(attachment.size / 1024))} KB` : ""}</span></button>{error && <p role="alert" className="mt-1 max-w-xs text-[11px] text-destructive">{error}</p>}</div>;
}

function stripHtml(html: string) {
  return html.replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<[^>]+>/g, " ").replace(/&nbsp;|&#160;/gi, " ");
}

export function readableText(html: string) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script,style,head").forEach(el => el.remove());
  doc.querySelectorAll("br,p,div,tr,h1,h2,h3,li").forEach(el => el.append(doc.createTextNode("\n")));
  return (doc.body.textContent ?? "").replace(/\n[ \t]*\n(?:[ \t]*\n)+/g, "\n\n").trim();
}

export function EmailHtml({ messageId, subject, html, attachments, fontScale = 1 }: { messageId: string; subject: string; html: string; attachments: Attachment[]; fontScale?: number }) {
  const [height, setHeight] = useState(420);
  const [proxiedHtml, setProxiedHtml] = useState(html);
  const [loadingImages, setLoadingImages] = useState(true);
  // Las imágenes se solicitan mediante el proxy seguro del backend; el navegador
  // nunca contacta directamente al remitente. Así el correo se muestra completo
  // como en Gmail/Outlook sin exponer la IP del usuario.
  const [allowRemote, setAllowRemote] = useState(true);
  const [imageErrors, setImageErrors] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const hasRemote = /<img\b[^>]*\bsrc\s*=\s*["']?https?:\/\//i.test(html);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];
    async function proxyImages() {
      setLoadingImages(true); setImageErrors(false);
      const document = new DOMParser().parseFromString(html, "text/html");
      const images = [...document.querySelectorAll("img")];
      let remoteIndex = 0;
      const jobs = images.map(async (image) => {
        const source = image.getAttribute("src") ?? "";
        image.removeAttribute("srcset");
        const imageIndex = /^https?:\/\//i.test(source) ? remoteIndex++ : -1;
        if (imageIndex >= 0 && !allowRemote) { image.removeAttribute("src"); return; }
        const cid = source.replace(/^cid:/i, "").replace(/^<|>$/g, "");
        const inline = /^cid:/i.test(source) ? attachments.find((file) => file.content_id?.replace(/^<|>$/g, "") === cid && file.inline_url) : undefined;
        if (imageIndex < 0 && !inline) { if (!/^data:image\/(png|gif|jpeg|webp);/i.test(source)) image.removeAttribute("src"); return; }
        const width = Number.parseInt(image.getAttribute("width") ?? "", 10);
        const height = Number.parseInt(image.getAttribute("height") ?? "", 10);
        if ((Number.isFinite(width) && width <= 2) || (Number.isFinite(height) && height <= 2)) {
          image.remove();
          return;
        }
        try {
          const path = inline?.inline_url ?? `/v1/mail/messages/${encodeURIComponent(messageId)}/images/${imageIndex}`;
          if (!path.startsWith("/v1/mail/messages/")) throw new Error("Ruta de imagen no válida.");
          const blob = await apiBlob(path);
          if (cancelled) return;
          const objectUrl = URL.createObjectURL(blob);
          objectUrls.push(objectUrl);
          image.setAttribute("src", objectUrl);
          image.removeAttribute("srcset");
        } catch {
          if (!cancelled) setImageErrors(true);
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
  }, [html, messageId, attachments, allowRemote, imageAttempt]);

  function resizeFrame() {
    const document = frameRef.current?.contentDocument;
    if (!document) return;
    const contentHeight = Math.max(
      220,
      document.documentElement.scrollHeight,
      document.body?.scrollHeight ?? 0,
    );
    // El panel lector ya tiene su propio desplazamiento. El iframe debe crecer
    // con el correo para evitar dos barras de scroll, como ocurre en Gmail.
    setHeight(Math.min(contentHeight, 30000));
  }

  return (
    <section className="mt-7 overflow-hidden rounded-xl border border-border bg-white">
      {hasRemote && !allowRemote && <div className="border-b border-border bg-surface-2 px-3 py-3 text-[11.5px] text-muted-foreground">Las imágenes externas están bloqueadas. Cargarlas puede confirmar la apertura al remitente.<button type="button" onClick={() => setAllowRemote(true)} className="ml-2 font-medium text-primary underline">Mostrar imágenes externas</button></div>}
      {loadingImages && <div role="status" className="border-b border-border bg-surface-2 px-3 py-2 text-[11.5px] text-muted-foreground">Preparando imágenes…</div>}
      {imageErrors && <div role="alert" className="border-b border-border px-3 py-2 text-[11.5px] text-destructive">Algunas imágenes no se pudieron cargar. <button type="button" className="underline" onClick={() => setImageAttempt((value) => value + 1)}>Reintentar imágenes</button></div>}
      <iframe
        ref={frameRef}
        title={`Contenido de ${subject}`}
        srcDoc={emailDocument(proxiedHtml, fontScale)}
        sandbox="allow-same-origin allow-popups"
        referrerPolicy="no-referrer"
        scrolling="no"
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

export function emailDocument(html: string, fontScale = 1) {
  const scale = [1, 1.15, 1.3, 1.5].includes(fontScale) ? fontScale : 1;
  const document = new DOMParser().parseFromString(html, "text/html");
  document.querySelectorAll("script,iframe,object,embed,form,base,meta,link").forEach((element) => element.remove());
  document.querySelectorAll("*").forEach((element) => {
    for (const attribute of [...element.attributes]) {
      if (/^on/i.test(attribute.name) || ["srcdoc", "srcset", "action", "formaction"].includes(attribute.name)) element.removeAttribute(attribute.name);
    }
    if (element.tagName === "A") {
      if (!/^(https?:|mailto:)/i.test(element.getAttribute("href") ?? "")) element.removeAttribute("href");
      element.setAttribute("target", "_blank"); element.setAttribute("rel", "noopener noreferrer");
    }
  });
  html = document.documentElement.outerHTML;
  const headContent = `
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; media-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      html { width: 100%; color-scheme: light; background: #fff; overflow: hidden; }
      body { box-sizing: border-box; width: ${100 / scale}% !important; zoom: ${scale}; min-width: 0 !important; margin: 0; padding: 16px; font: 16px/1.65 Arial, sans-serif; color: #202124; background: #fff; overflow-wrap: anywhere; }
      body > table, body > center, body > center > table, body > div { box-sizing: border-box; max-width: 100% !important; }
      body > center { display: block; }
      body > center > table, body > table { margin-left: 0 !important; margin-right: 0 !important; }
      img { max-width: 100% !important; height: auto !important; }
      table { max-width: 100% !important; }
      td { max-width: 100%; overflow-wrap: anywhere; }
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
