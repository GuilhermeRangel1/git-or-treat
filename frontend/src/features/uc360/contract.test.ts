import { describe, expect, it } from "vitest";
import { decodeUCSearch, UCContractError } from "./contract";

describe("UC API contract", () => {
  it("preserves a valid empty search as distinct from malformed data", () => {
    expect(
      decodeUCSearch({
        data: { items: [] },
        pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
        metadata: { status: "empty" },
      }).data.items,
    ).toEqual([]);
    expect(() =>
      decodeUCSearch({
        data: { items: [] },
        pagination: {},
        metadata: { status: "empty" },
      }),
    ).toThrow(UCContractError);
  });
});
