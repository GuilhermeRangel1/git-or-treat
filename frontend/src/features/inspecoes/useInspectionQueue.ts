import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeDetail, decodeQueue } from "./contract";

export function useInspectionQueue(
  request: string | null,
  detail: string | null,
) {
  return useQuery({
    queryKey: ["inspection-queue", request],
    enabled: request !== null && detail === null,
    queryFn: async ({ signal }) =>
      decodeQueue(
        await apiClient<unknown>(`/api/v1/inspections/queue?${request}`, {
          signal,
        }),
      ),
    staleTime: 30_000,
  });
}
export function useSuspicion(detail: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["inspection-suspicion", detail],
    enabled: enabled && detail !== null,
    queryFn: async ({ signal }) => {
      const response = decodeDetail(
        await apiClient<unknown>(
          `/api/v1/inspections/queue/${encodeURIComponent(detail ?? "")}`,
          { signal },
        ),
      );
      if (response.data.uc_id !== detail)
        throw new Error("UC divergente na resposta.");
      return response;
    },
    staleTime: 30_000,
  });
}
