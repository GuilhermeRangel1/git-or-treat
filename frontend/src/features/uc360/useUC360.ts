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
    queryFn: async ({ signal }) => {
      const result = decodeUCOverview(
        await apiClient<unknown>(
          `/api/v1/ucs/${encodeURIComponent(uc)}/overview${params.size ? `?${params}` : ""}`,
          { signal },
        ),
      );
      if (
        result.data.profile.uc_id !== uc ||
        (start &&
          end &&
          (result.data.period.start !== start ||
            result.data.period.end !== end))
      )
        throw new Error("Resposta de UC ou período divergente.");
      return result;
    },
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
    queryFn: async ({ signal }) => {
      const result = decodeUCHistory(
        await apiClient<unknown>(
          `/api/v1/ucs/${encodeURIComponent(uc)}/history/${section}?${params}`,
          { signal },
        ),
        section as UCHistorySection,
      );
      if (
        start &&
        end &&
        (result.metadata.period.start !== start ||
          result.metadata.period.end !== end)
      )
        throw new Error("Período do histórico divergente.");
      return result;
    },
    staleTime: 30_000,
  });
}

export function useUCSeries(
  uc: string,
  start: string,
  end: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["uc360", "series", uc, start, end],
    enabled: enabled && Boolean(uc) && Boolean(start) && Boolean(end),
    queryFn: async ({ signal }) => {
      let page = 1;
      let version: string | null = null;
      let pages = 1;
      const items: Array<{
        competencia: string;
        measured_energy_kwh: number | null;
      }> = [];
      while (page <= pages) {
        const params = new URLSearchParams({
          start,
          end,
          page: String(page),
          page_size: "100",
          order_by: "competencia",
        });
        const response = decodeUCHistory(
          await apiClient<unknown>(
            `/api/v1/ucs/${encodeURIComponent(uc)}/history/consumption?${params}`,
            { signal },
          ),
          "consumption",
        );
        if (
          response.metadata.period.start !== start ||
          response.metadata.period.end !== end ||
          (version !== null && version !== response.metadata.source.version)
        )
          throw new Error("A publicação ou o período do histórico mudou.");
        version = response.metadata.source.version;
        pages = response.pagination.total_pages;
        if (pages > 100)
          throw new Error("Histórico muito extenso para o gráfico.");
        items.push(
          ...response.data.items.map((item) => ({
            competencia: String(item.competencia),
            measured_energy_kwh: item.measured_energy_kwh as number | null,
          })),
        );
        page += 1;
      }
      return { items, version };
    },
    staleTime: 30_000,
  });
}
