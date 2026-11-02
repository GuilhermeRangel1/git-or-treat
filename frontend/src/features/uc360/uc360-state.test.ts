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
    expect(
      applyUCSearch(selected, { q: "UC-1002", municipio: "", classe: "" }).has(
        "uc",
      ),
    ).toBe(false);
  });

  it("parses and applies municipality and class with the text query", () => {
    const parsed = parseUC360SearchParams(
      new URLSearchParams(
        "q=UC-10&municipio=Recife&classe=Comercial&search_page=3&start=2025-01&end=2025-12",
      ),
    );
    expect(parsed).toMatchObject({
      q: "UC-10",
      municipio: "Recife",
      classe: "Comercial",
      searchPage: 3,
      start: "2025-01",
      end: "2025-12",
      invalid: [],
    });

    const applied = applyUCSearch(
      new URLSearchParams("start=2025-01&end=2025-12&search_page=4"),
      { q: "UC-10", municipio: "Recife", classe: "Comercial" },
    );
    expect(applied.get("q")).toBe("UC-10");
    expect(applied.get("municipio")).toBe("Recife");
    expect(applied.get("classe")).toBe("Comercial");
    expect(applied.has("search_page")).toBe(false);
    expect(applied.get("start")).toBe("2025-01");
    expect(applied.get("end")).toBe("2025-12");
  });

  it("rejects duplicate municipality and class URL filters", () => {
    const parsed = parseUC360SearchParams(
      new URLSearchParams(
        "municipio=Recife&municipio=Olinda&classe=Comercial&classe=Rural",
      ),
    );
    expect(parsed.invalid).toContain("Parâmetro municipio duplicado.");
    expect(parsed.invalid).toContain("Parâmetro classe duplicado.");
  });
});
