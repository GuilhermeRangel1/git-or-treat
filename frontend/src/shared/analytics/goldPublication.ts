import { useSyncExternalStore } from "react";
import type { GoldMetadata } from "./goldContract";

export type GoldPublicationIdentity = { lote: string; fingerprint: string };
let publication: GoldPublicationIdentity | null = null;
let generation = 0;
let stale = false;
export const isGoldPublicationStale = () => stale;
export function markGoldPublicationStale() {
  stale = true;
  listeners.forEach((listener) => listener());
}
const listeners = new Set<() => void>();
export const getGoldPublication = () => publication;
export const getGoldGeneration = () => generation;
export const goldPublicationKey = () =>
  publication ? `${publication.lote}:${publication.fingerprint}` : "unbound";
export function subscribeGoldPublication(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function useGoldPublicationKey() {
  return useSyncExternalStore(
    subscribeGoldPublication,
    goldPublicationKey,
    goldPublicationKey,
  );
}
export function useGoldPublicationRevision() {
  const snapshot = () => `${generation}:${goldPublicationKey()}:${stale}`;
  return useSyncExternalStore(subscribeGoldPublication, snapshot, snapshot);
}
export function resetGoldPublication() {
  publication = null;
  stale = false;
  generation += 1;
  listeners.forEach((listener) => listener());
}
export function acceptGoldPublication(metadata: GoldMetadata) {
  return acceptGoldIdentity({
    lote: metadata.source.version,
    fingerprint: metadata.fingerprint,
  });
}
export function acceptGoldIdentity(next: GoldPublicationIdentity) {
  if (
    publication &&
    (publication.lote !== next.lote ||
      publication.fingerprint !== next.fingerprint)
  ) {
    markGoldPublicationStale();
    return false;
  }
  if (!publication) {
    publication = next;
    listeners.forEach((listener) => listener());
  }
  return true;
}
export function withGoldPublication(params: URLSearchParams) {
  const result = new URLSearchParams(params);
  if (publication) {
    result.set("expected_lote", publication.lote);
    result.set("expected_fingerprint", publication.fingerprint);
  }
  return result;
}
