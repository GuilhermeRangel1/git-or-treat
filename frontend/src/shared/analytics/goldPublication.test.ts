import { beforeEach, describe, expect, it } from "vitest";
import { decodeGoldMetadata } from "./goldContract";
import {
  acceptGoldPublication,
  getGoldGeneration,
  getGoldPublication,
  isGoldPublicationStale,
  resetGoldPublication,
  withGoldPublication,
} from "./goldPublication";

const metadata = () =>
  decodeGoldMetadata({
    contract_version: "2.0.0",
    status: "partial",
    period: null,
    temporal_scope: "snapshot",
    schema_version: "gold-csv-v2",
    fingerprint: "a".repeat(64),
    filters: { municipio: null, bairro: null, classe: null, alimentador: null },
    source: {
      kind: "gold",
      version: "artificial-batch",
      is_demo: false,
      updated_at: "2026-10-29T12:00:00Z",
    },
    limitations: [],
  });
beforeEach(resetGoldPublication);
describe("Gold publication coherence", () => {
  it("pins first batch and prevents a parallel response from another publication", () => {
    expect(acceptGoldPublication(metadata())).toBe(true);
    expect(
      acceptGoldPublication({ ...metadata(), fingerprint: "b".repeat(64) }),
    ).toBe(false);
    expect(getGoldPublication()?.fingerprint).toBe("a".repeat(64));
    expect(isGoldPublicationStale()).toBe(true);
  });
  it("copies query parameters and sends both publication guards", () => {
    acceptGoldPublication(metadata());
    const original = new URLSearchParams("page=2");
    const guarded = withGoldPublication(original);
    expect(original.has("expected_lote")).toBe(false);
    expect(guarded.get("expected_lote")).toBe("artificial-batch");
    expect(guarded.get("expected_fingerprint")).toBe("a".repeat(64));
    expect(guarded.get("page")).toBe("2");
  });
  it("refresh resets publication and advances the generation for stale in-flight requests", () => {
    acceptGoldPublication(metadata());
    const before = getGoldGeneration();
    resetGoldPublication();
    expect(getGoldGeneration()).toBe(before + 1);
    expect(getGoldPublication()).toBeNull();
    expect(isGoldPublicationStale()).toBe(false);
  });
  it("rejects unknown versions, invalid identities and a dated snapshot", () => {
    for (const change of [
      { contract_version: "9" },
      { schema_version: "gold-csv-v1" },
      { fingerprint: "" },
      { period: { start: "2026-01", end: "2026-01", granularity: "month" } },
    ]) {
      expect(() => decodeGoldMetadata({ ...metadata(), ...change })).toThrow(
        "Metadados Gold inválidos",
      );
    }
  });
});
