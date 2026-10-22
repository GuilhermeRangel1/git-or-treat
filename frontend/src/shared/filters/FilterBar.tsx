import { useId, useRef, useState } from "react";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import {
  CLASSES_DISPONIVEIS,
  COMPETENCIAS_DISPONIVEIS,
  MUNICIPIOS_DISPONIVEIS,
} from "../analytics/syntheticData";
import type { ComparisonType, PanoramaFilters } from "../analytics/types";
import Button from "../ui/Button";
import Select from "../ui/Select";

interface FilterBarProps {
  filters: PanoramaFilters;
  onFilterChange: <K extends keyof PanoramaFilters>(
    key: K,
    value: PanoramaFilters[K],
  ) => void;
  onReset: () => void;
  hasActiveFilters: boolean;
  errors?: Partial<Record<keyof PanoramaFilters, string>>;
}

const COMPARACAO_OPTIONS = [
  { value: "anterior", label: "Mês anterior (m-1)" },
  { value: "ano_anterior", label: "Ano anterior (m-12)" },
  { value: "nenhuma", label: "Sem comparação" },
];

function periodLabel(period: string) {
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(period))
    return "Competência inválida";
  const [year, month] = period.split("-");
  const months = [
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
  return `${months[Number(month) - 1]}/${year}`;
}

function comparisonLabel(filters: PanoramaFilters) {
  if (filters.comparacao === "nenhuma") return "Sem comparação";
  if (!["anterior", "ano_anterior"].includes(filters.comparacao))
    return "Comparação inválida";
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(filters.periodo))
    return "Competência inválida";
  const [year, month] = filters.periodo.split("-").map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, 1);
  if (filters.comparacao === "anterior")
    date.setUTCMonth(date.getUTCMonth() - 1);
  else date.setUTCFullYear(year - 1);
  return periodLabel(
    `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`,
  );
}

export default function FilterBar({
  filters,
  onFilterChange,
  onReset,
  hasActiveFilters,
  errors = {},
}: FilterBarProps) {
  const [expanded, setExpanded] = useState(Object.keys(errors).length > 0);
  const panelId = useId();
  const toggleRef = useRef<HTMLDivElement>(null);
  const summary = [
    {
      label: "Competência",
      value: errors.periodo
        ? "Competência inválida"
        : periodLabel(filters.periodo),
    },
    {
      label: "Comparar com",
      value: errors.comparacao
        ? "Comparação inválida"
        : comparisonLabel(filters),
    },
    {
      label: "Território",
      value:
        MUNICIPIOS_DISPONIVEIS.find((item) => item.value === filters.municipio)
          ?.label ||
        filters.municipio ||
        "Município inválido",
    },
    {
      label: "Classe",
      value:
        CLASSES_DISPONIVEIS.find((item) => item.value === filters.classe)
          ?.label ||
        filters.classe ||
        "Classe inválida",
    },
  ];

  return (
    <section
      aria-label="Filtros do Panorama"
      className="rounded-2xl bg-surface px-4 py-5 sm:px-5 lg:py-6"
    >
      <div
        ref={toggleRef}
        className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-6"
      >
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4 lg:gap-x-6">
          {summary.map((item) => (
            <div key={item.label} className="min-w-0">
              <dt className="text-xs text-muted sm:text-sm">{item.label}</dt>
              <dd className="mt-1 break-words text-sm font-medium text-content sm:text-base">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
        <Button
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((value) => !value)}
          className="w-full sm:w-auto lg:ml-3"
          leftIcon={
            <SlidersHorizontal
              className="size-4 text-muted"
              aria-hidden="true"
            />
          }
        >
          {expanded ? "Fechar ajustes" : "Ajustar filtros"}
        </Button>
      </div>
      <div
        id={panelId}
        hidden={!expanded}
        role="region"
        aria-label="Ajustar recorte do Panorama"
        className="mt-5 border-t border-divider pt-4"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setExpanded(false);
            toggleRef.current?.querySelector("button")?.focus();
          }
        }}
      >
        <p className="text-xs text-muted">
          As alterações são aplicadas automaticamente aos indicadores e à série.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Select
            label="Período"
            aria-label="Período (Competência)"
            value={filters.periodo}
            error={errors.periodo}
            options={[
              ...(!COMPETENCIAS_DISPONIVEIS.some(
                (c) => c.value === filters.periodo,
              )
                ? [
                    {
                      value: filters.periodo,
                      label: filters.periodo || "Valor vazio",
                    },
                  ]
                : []),
              ...COMPETENCIAS_DISPONIVEIS.map((c) => ({
                value: c.value,
                label: c.label,
              })),
            ]}
            onChange={(e) => onFilterChange("periodo", e.target.value)}
          />

          <Select
            label="Comparação"
            value={filters.comparacao}
            error={errors.comparacao}
            options={[
              ...(!COMPARACAO_OPTIONS.some(
                (item) => item.value === filters.comparacao,
              )
                ? [{ value: filters.comparacao, label: "Comparação inválida" }]
                : []),
              ...COMPARACAO_OPTIONS,
            ]}
            onChange={(e) =>
              onFilterChange("comparacao", e.target.value as ComparisonType)
            }
          />

          <Select
            label="Município"
            value={filters.municipio}
            error={errors.municipio}
            options={[
              ...(!MUNICIPIOS_DISPONIVEIS.some(
                (item) => item.value === filters.municipio,
              )
                ? [{ value: filters.municipio, label: "Município inválido" }]
                : []),
              ...MUNICIPIOS_DISPONIVEIS,
            ]}
            onChange={(e) => onFilterChange("municipio", e.target.value)}
          />

          <Select
            label="Classe de Consumo"
            value={filters.classe}
            error={errors.classe}
            options={[
              ...(!CLASSES_DISPONIVEIS.some(
                (item) => item.value === filters.classe,
              )
                ? [{ value: filters.classe, label: "Classe inválida" }]
                : []),
              ...CLASSES_DISPONIVEIS,
            ]}
            onChange={(e) => onFilterChange("classe", e.target.value)}
          />
        </div>

        {hasActiveFilters && (
          <div className="mt-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
            >
              Limpar filtros
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
