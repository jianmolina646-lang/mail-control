import { describe, expect, it } from "vitest";
import { mapAccount, syncAge } from "./mail-state";
import type { Account } from "./types";

const now = Date.parse("2026-10-20T22:00:00Z");
const account: Account = { id: "first-sync-test", provider: "gmail", email: "test@example.test", status: "connected", last_synced_at: null, last_error: null, message_count: 0, alert_count: 0, unread_count: 0 };

describe("first synchronization state", () => {
  it("keeps newly connected accounts pending instead of declaring them late", () => {
    expect(mapAccount(account, now)).toMatchObject({ status: "conectada", syncPending: true, syncStale: false });
  });

  it("preserves the worker running state for a first synchronization", () => {
    expect(mapAccount({ ...account, status: "syncing" }, now)).toMatchObject({ status: "sincronizando", syncPending: true, syncStale: false });
  });

  it.each(["reauth_required", "error", "disconnected"] as const)("does not label %s accounts as ordinary first-sync pending", status => {
    expect(mapAccount({ ...account, status }, now).syncPending).toBe(false);
  });

  it("preserves a real initial-sync error even if the account status is connected", () => {
    expect(mapAccount({ ...account, last_error: "Provider rate limit; retry scheduled" }, now)).toMatchObject({ syncPending: false, syncStale: true, statusDetail: "Provider rate limit; retry scheduled" });
  });

  it("does not suppress authorization errors without a last-sync timestamp", () => {
    expect(mapAccount({ ...account, status: "reauth_required", last_error: "invalid_grant" }, now)).toMatchObject({ status: "requiere-autorizacion", syncPending: false, statusDetail: "invalid_grant" });
  });

  it("does not treat invalid nonempty dates as a new account", () => {
    expect(mapAccount({ ...account, last_synced_at: "invalid-date" }, now)).toMatchObject({ syncPending: false, syncStale: true, lastSync: "Fecha de sincronización no válida" });
  });

  it("keeps the existing fifteen-minute stale threshold", () => {
    expect(syncAge(new Date(now - 900_000).toISOString(), now).stale).toBe(false);
    expect(syncAge(new Date(now - 901_000).toISOString(), now).stale).toBe(true);
    expect(mapAccount({ ...account, last_synced_at: new Date(now - 901_000).toISOString() }, now)).toMatchObject({ syncPending: false, syncStale: true });
  });

  it("clears the first-sync flag once a successful timestamp is recorded", () => {
    expect(mapAccount({ ...account, last_synced_at: new Date(now).toISOString() }, now)).toMatchObject({ syncPending: false, syncStale: false });
  });
});
