import { describe, expect, it } from "vitest";
import { folderFrom, mailFilters, scopedIds } from "./mail-state";

describe("mail state boundaries", () => {
  it("never keeps IDs that are outside the current visible account scope", () => {
    expect(scopedIds(["owned", "other", "owned"], ["owned", "visible"])).toEqual(["owned"]);
  });

  it("maps an account and structured search query to server-side filters", () => {
    const result = mailFilters(
      "proveedor:hotmail estado:no-leido factura vencida",
      "account-owned-by-current-tenant",
      "todos",
    );

    expect(result.error).toBe("");
    expect(result.params.get("account_id")).toBe("account-owned-by-current-tenant");
    expect(result.params.get("provider")).toBe("hotmail");
    expect(result.params.get("is_read")).toBe("false");
    expect(result.params.get("search")).toBe("factura vencida");
  });

  it("rejects invalid scope values instead of inventing a folder", () => {
    expect(folderFrom("not-a-folder")).toBe("todos");
    expect(mailFilters("desde:09-09-2026", null, "todos").error).toContain("AAAA-MM-DD");
  });
});
