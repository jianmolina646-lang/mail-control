import type { MailAccount, MailMessage } from "@/lib/mail-data";

export interface ParsedQuery {
  text: string;
  ops: Record<string, string>;
}

const OP_RE = /(\w+):("[^"]*"|[^\s]+)/g;

/** Parses `cuenta:"Netflix Perú #023" riesgo:alto texto libre` */
export function parseQuery(raw: string): ParsedQuery {
  const ops: Record<string, string> = {};
  const text = raw
    .replace(OP_RE, (_m, key: string, value: string) => {
      ops[key.toLowerCase()] = value.replace(/^"|"$/g, "").toLowerCase();
      return "";
    })
    .trim()
    .toLowerCase();
  return { text, ops };
}

function has(value: string | undefined, needle: string) {
  return (value ?? "").toLowerCase().includes(needle);
}

export function matchesQuery(
  message: MailMessage,
  account: MailAccount | undefined,
  parsed: ParsedQuery,
) {
  const { text, ops } = parsed;

  for (const [key, value] of Object.entries(ops)) {
    switch (key) {
      case "cuenta":
        if (!has(account?.alias, value)) return false;
        break;
      case "correo":
        if (!has(account?.email, value)) return false;
        break;
      case "cliente":
        if (!has(account?.client, value)) return false;
        break;
      case "proveedor":
        if (!has(account?.provider, value)) return false;
        break;
      case "plataforma":
        if (!has(account?.platform, value)) return false;
        break;
      case "categoria":
        if (!message.categories.some((c) => c.includes(value))) return false;
        break;
      case "estado":
        if (value.startsWith("no") ? !message.unread : message.unread) return false;
        break;
      case "riesgo":
        if (message.risk !== value) return false;
        break;
      case "tiene":
        if (value.startsWith("adj") && message.attachments.length === 0) return false;
        break;
      case "desde":
        if (message.isoDate < value) return false;
        break;
      case "hasta":
        if (message.isoDate > value) return false;
        break;
      default:
        break;
    }
  }

  if (!text) return true;
  return [
    message.senderName,
    message.sender,
    message.subject,
    message.preview,
    account?.alias,
    account?.email,
    account?.client,
    account?.platform,
  ].some((v) => has(v, text));
}
