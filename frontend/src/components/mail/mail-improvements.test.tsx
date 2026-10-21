import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SearchFields, replaceSearchOperator } from "./search-fields";
import { SyncAlerts } from "./sync-alerts";
import { mailFilters } from "@/lib/mail-state";
import { readPreference } from "@/lib/reading-preferences";
import type { MailAccount } from "@/lib/mail-data";

const account: MailAccount = { id: "a", alias: "Test", email: "test@example.test", provider: "gmail", client: "", platform: "", group: "", country: "", labels: [], favorite: false, status: "conectada", lastSync: "Hace 20 min", syncStale: true, messageCount: 0 };
afterEach(() => vi.unstubAllGlobals());
describe("mail usability improvements", () => {
  it("replaces a filter without losing other filters or free text", () => {
    const q = replaceSearchOperator('factura de:"old@example.test" tiene:adjuntos', "de", "new@example.test");
    const result = mailFilters(q, "account", "todos");
    expect(result.params.get("sender")).toBe("new@example.test");
    expect(result.params.get("search")).toBe("factura");
    expect(result.params.get("has_attachments")).toBe("true");
    expect(result.params.get("account_id")).toBe("account");
  });
  it("removes cleared filters and does not allow injected operators", () => {
    expect(replaceSearchOperator("hello de:old", "de", "")).toBe("hello");
    expect(mailFilters(replaceSearchOperator("", "de", 'a" estado:leido'), null, "todos").params.has("is_read")).toBe(false);
  });
  it("rejects impossible dates and reversed ranges", () => {
    expect(mailFilters("desde:2026-02-30", null, "todos").error).toBeTruthy();
    expect(mailFilters("desde:2026-10-15 hasta:2026-10-01", null, "todos").error).toBeTruthy();
    expect(mailFilters("desde:2026-10-01 hasta:2026-10-15", null, "todos").error).toBe("");
  });
  it("renders labeled search fields", () => {
    const html = renderToStaticMarkup(<SearchFields query="" onChange={() => {}} />);
    for (const label of ["Remitente", "Desde", "Hasta", "Solo con adjuntos"]) expect(html).toContain(label);
  });
  it("shows stale connected accounts and removes non-functional actions", () => {
    const html = renderToStaticMarkup(<SyncAlerts accounts={[account]} onSelectAccount={() => {}} onRetry={() => {}} />);
    expect(html).toContain("sincronización atrasada");
    expect(html).toContain(account.lastSync);
    expect(html).not.toContain("Pausar");
    expect(html).not.toContain("Reanudar");
  });
  it("only renders mutation actions when callbacks are authorized", () => {
    const html = renderToStaticMarkup(<SyncAlerts accounts={[{...account, status:"requiere-autorizacion"}]} onSelectAccount={() => {}} />);
    expect(html).not.toContain(">Reautorizar</button>");
  });
  it("hides healthy accounts unless overview requested", () => {
    const healthy = {...account, syncStale:false};
    expect(renderToStaticMarkup(<SyncAlerts accounts={[healthy]} onSelectAccount={() => {}} />)).toBe("");
    expect(renderToStaticMarkup(<SyncAlerts showAll accounts={[healthy]} onSelectAccount={() => {}} />)).toContain(account.email);
  });
  it("restores only validated preferences", () => {
    vi.stubGlobal("localStorage", {getItem: () => "1.3"});
    expect(readPreference<number>("scale", 1, [1,1.3])).toBe(1.3);
    vi.stubGlobal("localStorage", {getItem: () => "999"});
    expect(readPreference<number>("scale", 1, [1,1.3])).toBe(1);
  });
  it("remains usable with blocked or corrupt browser storage", () => {
    vi.stubGlobal("localStorage", {getItem: () => {throw new Error("blocked");}});
    expect(readPreference("text", false, [false,true])).toBe(false);
    vi.stubGlobal("localStorage", {getItem: () => "invalid json"});
    expect(readPreference("text", false, [false,true])).toBe(false);
  });
});
