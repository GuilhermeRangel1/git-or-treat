import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeUCOverview, decodeUCSearch, decodeUCHistory } from "./contract";
import type { UCHistorySection } from "./uc360-state";

export function useUCSearch(q: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ["uc360", "search", q, page],
    enabled,
    queryFn: async ({ signal }) =>
      decodeUCSearch(
        await apiClient<unknown>(
          `/api/v1/ucs?${new URLSearchParams({ q, page: String(page), page_size: "20", order_by: "uc_id" })}`,
          { signal },
        ),
      ),
    staleTime: 30_000,
  });
}
export function useUCOverview(
  uc: string,
  start: string,
  end: string,
  enabled: boolean,
) {
  const params = new URLSearchParams();
  if (start && end) {
    params.set("start", start);
    params.set("end", end);
  }
  return useQuery({
    queryKey: ["uc360", "overview", uc, start, end],
    enabled: enabled && Boolean(uc),
    queryFn: async ({ signal }) =>
      decodeUCOverview(
        await apiClient<unknown>(
          `/api/v1/ucs/${encodeURIComponent(uc)}/overview${params.size ? `?${params}` : ""}`,
          { signal },
        ),
      ),
    staleTime: 30_000,
  });
}
export function useUCHistory(
  uc: string,
  section: UCHistorySection | "",
  start: string,
  end: string,
  page: number,
  enabled: boolean,
) {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (start && end) {
    params.set("start", start);
    params.set("end", end);
  }
  return useQuery({
    queryKey: ["uc360", "history", uc, section, start, end, page],
    enabled: enabled && Boolean(uc) && Boolean(section),
    queryFn: async ({ signal }) =>
      decodeUCHistory(
        await apiClient<unknown>(
          `/api/v1/ucs/${encodeURIComponent(uc)}/history/${section}?${params}`,
          { signal },
        ),
        section as UCHistorySection,
      ),
    staleTime: 30_000,
  });
}
