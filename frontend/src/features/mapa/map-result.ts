export function currentMapSummary<T>(
  publicationStale: boolean,
  queryError: boolean,
  data: T | undefined,
) {
  return publicationStale || queryError ? null : (data ?? null);
}
