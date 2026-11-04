import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeDetail, decodeQueue } from "./contract";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";

export function useInspectionQueue(
  request: string | null,
  detail: string | null,
) {
  const publication = useGoldPublicationKey();
  return useQuery({
    queryKey: ["inspection-queue", publication, request],
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
  const publication = useGoldPublicationKey();
  return useQuery({
    queryKey: ["inspection-suspicion", publication, detail],
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
    // Keep the last evidence mounted while a new publication is fetched. This
    // also keeps an unresolved order intent available for explicit recovery.
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}
