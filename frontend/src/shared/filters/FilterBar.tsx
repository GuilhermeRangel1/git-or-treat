import { Filter, RotateCcw } from "lucide-react";
import {
  CLASSES_DISPONIVEIS,
  COMPETENCIAS_DISPONIVEIS,
  MUNICIPIOS_DISPONIVEIS,
} from "../analytics/syntheticData";
import type { ComparisonType, PanoramaFilters } from "../analytics/types";
import Badge from "../ui/Badge";
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

export default function FilterBar({
  filters,
  onFilterChange,
  onReset,
  hasActiveFilters,
  errors = {},
}: FilterBarProps) {
  return (
    <section
      aria-label="Filtros do Panorama"
      className="rounded-xl border border-border bg-surface p-3 sm:p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Filter className="size-4 text-brand" />
          <h2 className="text-sm font-semibold text-content uppercase tracking-wider font-mono">
            Filtros & Recortes
          </h2>

          {hasActiveFilters && (
            <span className="hidden sm:inline">
              <Badge variant="goiaba">Filtros personalizados</Badge>
            </span>
          )}
        </div>

        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            leftIcon={<RotateCcw className="size-3.5" />}
          >
            Limpar filtros
          </Button>
        )}
      </div>

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

      <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-muted font-mono">
        <span>
          {Object.keys(errors).length > 0
            ? "Recorte informado:"
            : "Recorte aplicado:"}
        </span>
        <span className="font-semibold text-content">{filters.periodo}</span>
        <span>•</span>
        <span>
          {filters.comparacao === "anterior"
            ? "vs. Mês anterior"
            : filters.comparacao === "ano_anterior"
              ? "vs. Ano anterior"
              : filters.comparacao === "nenhuma"
                ? "Sem comparação"
                : "Comparação inválida"}
        </span>
        <span>•</span>
        <span>
          {MUNICIPIOS_DISPONIVEIS.find((m) => m.value === filters.municipio)
            ?.label || filters.municipio}
        </span>
        <span>•</span>
        <span>
          {CLASSES_DISPONIVEIS.find((c) => c.value === filters.classe)?.label ||
            filters.classe}
        </span>
      </div>
    </section>
  );
}
