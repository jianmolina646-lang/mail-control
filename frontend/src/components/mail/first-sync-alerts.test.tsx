import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SyncAlerts } from "./sync-alerts";
import { mapAccount } from "@/lib/mail-state";
import type { Account } from "@/lib/types";

const account: Account = { id: "first-sync-test", provider: "gmail", email: "test@example.test", status: "connected", last_synced_at: null, last_error: null, message_count: 0, alert_count: 0, unread_count: 0 };
function render(overrides: Partial<Account> = {}, authorized = true) {
  return renderToStaticMarkup(<SyncAlerts accounts={[mapAccount({ ...account, ...overrides })]} onSelectAccount={() => {}} onRetry={authorized ? () => {} : undefined} onReauthorize={authorized ? () => {} : undefined} />);
}

describe("first synchronization notice", () => {
  it("shows a neutral pending notice and an available synchronize action", () => {
    const html = render();
    expect(html).toContain("Primera sincronización pendiente");
    expect(html).toContain('data-warning="false"');
    expect(html).toContain(">Sincronizar</button>");
    expect(html).not.toContain("sincronización atrasada");
    expect(html).not.toContain(">Reautorizar</button>");
  });

  it("only calls the first sync running when the backend says syncing", () => {
    const html = render({ status: "syncing" });
    expect(html).toContain("Primera sincronización en curso");
    expect(html).not.toContain(">Sincronizar</button>");
  });

  it("keeps authorization failures prominent", () => {
    const html = render({ status: "reauth_required", last_error: "invalid_grant" });
    expect(html).toContain("Requiere autorización");
    expect(html).toContain("invalid_grant");
    expect(html).toContain(">Reautorizar</button>");
    expect(html).toContain('data-warning="true"');
    expect(html).not.toContain("Primera sincronización pendiente");
  });

  it("keeps provider errors visible even if no first timestamp exists", () => {
    const html = render({ status: "error", last_error: "Retry scheduled" });
    expect(html).toContain("Error de sincronización");
    expect(html).toContain("Retry scheduled");
    expect(html).toContain('data-warning="true"');
  });

  it("keeps genuinely late previously synchronized accounts visible", () => {
    const html = render({ last_synced_at: new Date(Date.now() - 901_000).toISOString() });
    expect(html).toContain("sincronización atrasada");
    expect(html).toContain('data-warning="true"');
  });

  it("does not add synchronization or authorization permissions", () => {
    expect(render({}, false)).not.toContain(">Sincronizar</button>");
    expect(render({ status: "reauth_required" }, false)).not.toContain(">Reautorizar</button>");
  });

  it("removes the pending notice after a successful sync", () => {
    expect(render({ last_synced_at: new Date().toISOString() })).toBe("");
  });
});
