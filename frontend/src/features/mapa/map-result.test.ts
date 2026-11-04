import { describe, expect, it } from "vitest";
import { currentMapSummary } from "./map-result";

describe("currentMapSummary", () => {
  const cached = {
    mapped: { items: [{ municipality: "Igarassu", billed: 9876 }] },
    envelope: { metadata: { publication: "old" } },
  };

  it("hides prior municipal metrics and envelope after a publication conflict", () => {
    expect(currentMapSummary(true, false, cached)).toBeNull();
  });

  it("hides stale cached metrics when the current request fails", () => {
    expect(currentMapSummary(false, true, cached)).toBeNull();
  });

  it("returns only successful data for the current publication", () => {
    expect(currentMapSummary(false, false, cached)).toBe(cached);
    expect(currentMapSummary(false, false, undefined)).toBeNull();
  });
});
