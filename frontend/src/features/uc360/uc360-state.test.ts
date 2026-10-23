import { describe, expect, it } from "vitest";
import { applyUCSearch, parseUC360SearchParams, selectUC } from "./uc360-state";

describe("UC 360 URL state", () => {
  it("rejects malformed, partial, reversed, and duplicated URL state", () => {
    for (const query of [
      "?start=2025-02",
      "?start=2025-13&end=2025-02",
      "?start=2025-02&end=2025-01",
      "?q=one&q=two",
      "?history_page=0",
    ]) {
      expect(
        parseUC360SearchParams(new URLSearchParams(query)).invalid.length,
      ).toBeGreaterThan(0);
    }
  });

  it("selects canonical IDs and clears state that belongs to a prior search", () => {
    const initial = new URLSearchParams(
      "start=2025-01&end=2025-02&section=invoices&history_page=3",
    );
    const selected = selectUC(initial, "UC-1001");
    expect(selected.get("uc")).toBe("UC-1001");
    expect(selected.get("start")).toBe("2025-01");
    expect(selected.has("section")).toBe(false);
    expect(selected.has("history_page")).toBe(false);
    expect(applyUCSearch(selected, "UC-1002").has("uc")).toBe(false);
  });
});
