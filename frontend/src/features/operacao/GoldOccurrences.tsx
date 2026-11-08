import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import Button from "@/shared/ui/Button";
import { decodeGoldMetadata } from "@/shared/analytics/goldContract";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";
import Pagination from "@/shared/ui/Pagination";

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
  const [pageSize, setPageSize] = useState(20);
  const publication = useGoldPublicationKey();
  const query = useQuery({
    // Mantém a página anterior na tela enquanto a próxima carrega, para a
    // paginação não sumir a cada clique.
    placeholderData: keepPreviousData,
    queryKey: [
      "operations",
      "occurrences",
      publication,
      feeder,
      start,
      end,
      page,
      pageSize,
    ],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({
        competencia_inicio: start,
        competencia_fim: end,
        page: String(page),
        page_size: String(pageSize),
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
    <section
      className="grid min-w-0 gap-3 rounded-xl bg-surface p-4"
      aria-label="Ocorrências observadas"
    >
      <div>
        <h3 className="font-heading text-lg font-semibold">
          Ocorrências observadas
        </h3>
        <p className="mt-1 text-sm text-muted">
          Registros por UC e data de abertura. Ausência de registros não
          comprova ausência de interrupções; o alimentador pode refletir o
          cadastro atual.
        </p>
      </div>
      {query.isPending ? (
        <p role="status" className="text-sm text-muted">
          Carregando ocorrências…
        </p>
      ) : query.isError ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
          <p>Não foi possível consultar ocorrências.</p>
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            Tentar novamente
          </Button>
        </div>
      ) : query.data.items.length === 0 ? (
        <p role="status" className="text-sm text-muted">
          Não há ocorrências observadas neste recorte.
        </p>
      ) : (
        <div className="min-w-0 overflow-x-auto rounded-xl bg-surface p-4">
          <table className="w-full min-w-[680px] table-fixed text-left font-sans">
            <caption className="sr-only">
              Ocorrências observadas por unidade consumidora e data de abertura
            </caption>
            <colgroup>
              <col className="w-[20%]" />
              <col className="w-[16%]" />
              <col className="w-[17%]" />
              <col className="w-[29%]" />
              <col className="w-[18%]" />
            </colgroup>
            <thead className="font-sans text-xs leading-[18px] text-muted">
              <tr className="h-11">
                <th scope="col" className="pr-2 font-normal">
                  Ocorrência
                </th>
                <th scope="col" className="pr-2 font-normal">
                  UC
                </th>
                <th scope="col" className="pr-2 font-normal">
                  Abertura
                </th>
                <th scope="col" className="pr-2 font-normal">
                  Causa
                </th>
                <th scope="col" className="font-normal">
                  Duração
                </th>
              </tr>
            </thead>
            <tbody className="text-sm leading-[22px]">
              {query.data.items.map((row) => (
                <tr
                  key={`${row.event_id}-${row.uc_id}`}
                  className="h-14 border-t border-border/60 align-middle"
                >
                  <th scope="row" className="break-words py-3 pr-2 font-medium">
                    {row.event_id}
                  </th>
                  <td className="break-words py-3 pr-2">{row.uc_id}</td>
                  <td className="py-3 pr-2">
                    {new Date(row.opened_at).toLocaleDateString("pt-BR", {
                      timeZone: "UTC",
                    })}
                  </td>
                  <td className="break-words py-3 pr-2">
                    {row.cause ?? "Não informada"}
                  </td>
                  <td className="py-3">
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
      {query.data && query.data.pages > 0 ? (
        <Pagination
          label="Paginação das ocorrências"
          page={page}
          totalPages={query.data.pages}
          onPageChange={setPage}
          pageSize={pageSize}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      ) : null}
    </section>
  );
}
