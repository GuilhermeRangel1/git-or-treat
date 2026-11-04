import { useRef, useState } from "react";
import { RotateCcw, SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import FilterSelect from "@/shared/filters/FilterSelect";
import type { MapLayer, MapQuery } from "./map-state";

const layers: Array<{ value: MapLayer; label: string }> = [
  { value: "revenue", label: "Faturamento no mês final · R$" },
  { value: "consumption", label: "Consumo medido no mês final · kWh" },
  { value: "revenue_change", label: "Variação absoluta do faturamento · R$" },
  { value: "consumption_change", label: "Variação absoluta do consumo · kWh" },
];

function monthLabel(value: string) {
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value))
    return "Competência inválida";
  const names = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  return `${names[Number(value.slice(5, 7)) - 1]}/${value.slice(0, 4)}`;
}

function preserveInvalid(
  value: string,
  options: { value: string; label: string }[],
  label: string,
) {
  return value && !options.some((option) => option.value === value)
    ? [{ value, label }]
    : [];
}

export default function MapFilters({
  months,
  classes,
  searchValues,
  onApply,
}: {
  months: readonly string[];
  classes: readonly string[];
  searchValues: Partial<MapQuery>;
  onApply: (query: MapQuery) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Partial<MapQuery>>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const periodOptions = [
    { value: "", label: "Escolha a competência" },
    ...months.map((value) => ({ value, label: monthLabel(value) })),
  ];
  const classOptions = [
    { value: "", label: "Todas" },
    ...classes.map((value) => ({ value, label: value })),
  ];
  const layerOptions = layers.map((layer) => ({
    value: layer.value,
    label: layer.label,
  }));
  const selectedLayer =
    layers.find((option) => option.value === searchValues.camada)?.label ??
    "Camada inválida";
  const summary = [
    {
      label: "Competência inicial",
      value: monthLabel(searchValues.competencia_inicio ?? ""),
    },
    {
      label: "Competência final",
      value: monthLabel(searchValues.competencia_fim ?? ""),
    },
    {
      label: "Classe",
      value: !searchValues.classe
        ? "Todas as classes"
        : classes.includes(searchValues.classe)
          ? searchValues.classe
          : "Classe inválida",
    },
    { label: "Camada", value: selectedLayer },
  ];
  const current = (source: Partial<MapQuery>) => ({
    competencia_inicio:
      source.competencia_inicio ?? months.at(-2) ?? months[0] ?? "",
    competencia_fim: source.competencia_fim ?? months.at(-1) ?? "",
    classe: source.classe ?? "",
    municipio: source.municipio ?? "",
    camada: source.camada ?? "revenue",
  });
  const draftQuery = current(draft);
  const canApply =
    months.includes(draftQuery.competencia_inicio) &&
    months.includes(draftQuery.competencia_fim) &&
    draftQuery.competencia_inicio <= draftQuery.competencia_fim &&
    layers.some(({ value }) => value === draftQuery.camada) &&
    (!draftQuery.classe || classes.includes(draftQuery.classe));
  const defaultQuery: MapQuery = {
    competencia_inicio: months.at(-2) ?? months[0] ?? "",
    competencia_fim: months.at(-1) ?? "",
    classe: "",
    municipio: "",
    camada: "revenue",
  };
  const canReset = Object.keys(defaultQuery).some(
    (key) =>
      draftQuery[key as keyof MapQuery] !== defaultQuery[key as keyof MapQuery],
  );

  function apply(value: Partial<MapQuery>) {
    const next = current(value);
    onApply({ ...next, camada: next.camada as MapLayer });
    setOpen(false);
  }

  return (
    <section
      aria-label="Filtros do mapa"
      className="mt-2 flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
    >
      <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-4">
        {summary.map((item) => (
          <div key={item.label} className="min-w-0">
            <dt className="text-xs text-muted">{item.label}</dt>
            <dd className="mt-1 truncate font-medium text-content">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
      <Button
        ref={triggerRef}
        variant="control"
        className="w-full lg:w-auto"
        leftIcon={
          <SlidersHorizontal className="size-4 text-muted" aria-hidden="true" />
        }
        onClick={() => {
          setDraft(current(searchValues));
          setOpen(true);
        }}
      >
        Ajustar filtros
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha o período, a classe e os indicadores para atualizar o mapa."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form
          aria-label="Filtros do mapa"
          className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            apply(draft);
          }}
        >
          <FilterSelect
            label="Competência inicial"
            value={draft.competencia_inicio ?? ""}
            options={[
              ...preserveInvalid(
                draft.competencia_inicio ?? "",
                periodOptions,
                "Competência inválida",
              ),
              ...periodOptions,
            ]}
            onChange={(value) =>
              setDraft((previous) => ({
                ...previous,
                competencia_inicio: value,
              }))
            }
          />
          <FilterSelect
            label="Competência final"
            value={draft.competencia_fim ?? ""}
            options={[
              ...preserveInvalid(
                draft.competencia_fim ?? "",
                periodOptions,
                "Competência inválida",
              ),
              ...periodOptions,
            ]}
            onChange={(value) =>
              setDraft((previous) => ({ ...previous, competencia_fim: value }))
            }
          />
          <FilterSelect
            label="Classe"
            value={draft.classe ?? ""}
            options={[
              ...preserveInvalid(
                draft.classe ?? "",
                classOptions,
                "Classe inválida",
              ),
              ...classOptions,
            ]}
            onChange={(value) =>
              setDraft((previous) => ({ ...previous, classe: value }))
            }
          />
          <FilterSelect
            label="Camada"
            value={draft.camada ?? "revenue"}
            options={[
              ...preserveInvalid(
                draft.camada ?? "revenue",
                layerOptions,
                "Camada inválida",
              ),
              ...layerOptions,
            ]}
            onChange={(value) =>
              setDraft((previous) => ({
                ...previous,
                camada: value as MapLayer,
              }))
            }
          />
          <div className="flex flex-col-reverse justify-between gap-3 border-t border-divider pt-4 sm:col-span-2 sm:flex-row sm:items-center">
            {canReset ? (
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
                onClick={() => setDraft(defaultQuery)}
              >
                Limpar filtros
              </Button>
            ) : (
              <span />
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary" disabled={!canApply}>
                Aplicar filtros
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </section>
  );
}
