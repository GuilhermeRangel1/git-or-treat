import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeGoldMetadata } from "@/shared/analytics/goldContract";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";

type Item = {
  event_id: string;
  uc_id: string;
  opened_at: string;
  cause: string | null;
  duration_hours: number | null;
};

function decode(value: unknown, feeder: string, start: string, end: string) {
  if (!value || typeof value !== "object")
    throw new Error("Resposta de ocorrências inválida.");
  const root = value as Record<string, unknown>;
  const metadata = decodeGoldMetadata(root.metadata);
  if (
    metadata.period?.start !== start ||
    metadata.period.end !== end ||
    metadata.filters.alimentador !== feeder
  )
    throw new Error("Recorte de ocorrências divergente.");
  if (
    !Array.isArray(root.data) ||
    !root.pagination ||
    typeof root.pagination !== "object"
  )
    throw new Error("Lista de ocorrências inválida.");
  const pagination = root.pagination as Record<string, unknown>;
  if (
    !Number.isInteger(pagination.total_pages) ||
    Number(pagination.total_pages) < 0
  )
    throw new Error("Paginação inválida.");
  const items = root.data.map((value): Item => {
    if (!value || typeof value !== "object")
      throw new Error("Ocorrência inválida.");
    const row = value as Record<string, unknown>;
    if (
      typeof row.event_id !== "string" ||
      typeof row.uc_id !== "string" ||
      typeof row.opened_at !== "string" ||
      !Number.isFinite(Date.parse(row.opened_at)) ||
      !(row.cause === null || typeof row.cause === "string") ||
      !(
        row.duration_hours === null ||
        (typeof row.duration_hours === "number" &&
          Number.isFinite(row.duration_hours) &&
          row.duration_hours >= 0)
      )
    )
      throw new Error("Ocorrência inválida.");
    return row as Item;
  });
  return {
    items,
    pages: Number(pagination.total_pages),
    limitations: metadata.limitations,
  };
}

export default function GoldOccurrences({
  feeder,
  start,
  end,
}: {
  feeder: string;
  start: string;
  end: string;
}) {
  const [page, setPage] = useState(1);
  const publication = useGoldPublicationKey();
  const query = useQuery({
    queryKey: [
      "operations",
      "occurrences",
      publication,
      feeder,
      start,
      end,
      page,
    ],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({
        competencia_inicio: start,
        competencia_fim: end,
        page: String(page),
        page_size: "20",
      });
      return decode(
        await apiClient<unknown>(
          `/api/v1/operations/feeders/${encodeURIComponent(feeder)}/occurrences?${params}`,
          { signal },
        ),
        feeder,
        start,
        end,
      );
    },
  });
  return (
    <section className="grid gap-3" aria-label="Ocorrências observadas">
      <h3 className="font-semibold">Ocorrências observadas</h3>
      <p className="text-sm text-muted">
        Registros por UC e data de abertura. Ausência de registros não comprova
        ausência de interrupções; o alimentador pode refletir o cadastro atual.
      </p>
      {query.isPending ? (
        <p role="status">Carregando ocorrências…</p>
      ) : query.isError ? (
        <p role="alert">
          Não foi possível consultar ocorrências.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => query.refetch()}
          >
            Tentar novamente
          </button>
        </p>
      ) : query.data.items.length === 0 ? (
        <p>Não há ocorrências observadas neste recorte.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <th>Ocorrência</th>
                <th>UC</th>
                <th>Abertura</th>
                <th>Causa</th>
                <th>Duração</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((row) => (
                <tr key={`${row.event_id}-${row.uc_id}`}>
                  <td>{row.event_id}</td>
                  <td>{row.uc_id}</td>
                  <td>
                    {new Date(row.opened_at).toLocaleDateString("pt-BR", {
                      timeZone: "UTC",
                    })}
                  </td>
                  <td>{row.cause ?? "Não informada"}</td>
                  <td>
                    {row.duration_hours === null
                      ? "Indisponível"
                      : `${row.duration_hours.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} h`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.data && query.data.pages > 1 ? (
        <div className="flex items-center gap-3 text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Anterior
          </button>
          <span>
            Página {page} de {query.data.pages}
          </span>
          <button
            type="button"
            disabled={page >= query.data.pages}
            onClick={() => setPage(page + 1)}
          >
            Próxima
          </button>
        </div>
      ) : null}
    </section>
  );
}
