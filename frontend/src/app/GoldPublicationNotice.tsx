import { useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  isGoldPublicationStale,
  resetGoldPublication,
  subscribeGoldPublication,
} from "@/shared/analytics/goldPublication";
import Button from "@/shared/ui/Button";

const analyticGroups = new Set([
  "panorama",
  "operations",
  "inspection-queue",
  "inspection-suspicion",
]);

export default function GoldPublicationNotice() {
  const stale = useSyncExternalStore(
    subscribeGoldPublication,
    isGoldPublicationStale,
    isGoldPublicationStale,
  );
  const client = useQueryClient();
  if (!stale) return null;
  return (
    <div
      role="alert"
      className="border-b border-border bg-surface p-4 text-sm text-content"
    >
      <p>
        A publicação Gold mudou. Atualize as consultas para usar o mesmo lote
        nas jornadas analíticas.
      </p>
      <Button
        onClick={() => {
          const filters = {
            predicate: (query: { queryKey: readonly unknown[] }) =>
              analyticGroups.has(String(query.queryKey[0])),
          };
          void client.cancelQueries(filters).then(() => {
            resetGoldPublication();
            void client.resetQueries(filters);
          });
        }}
      >
        Atualizar dados Gold
      </Button>
    </div>
  );
}
