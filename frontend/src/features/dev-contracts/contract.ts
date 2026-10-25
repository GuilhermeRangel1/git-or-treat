export type DataStatus = "available" | "empty" | "partial" | "unavailable";

export type KpiMetric = {
  id: string;
  label: string;
  value: number | null;
  unit: string;
  status: DataStatus;
  limitations: string[];
};

export type KpisEnvelope = {
  data: { metrics: KpiMetric[] };
  metadata: {
    contract_version: string;
    status: DataStatus;
    period: { start: string; end: string; granularity: string };
    filters: {
      municipio: string | null;
      bairro: string | null;
      classe: string | null;
      alimentador: string | null;
    };
    source: {
      kind: string;
      version: string;
      is_demo: boolean;
      updated_at: string;
    };
    limitations: string[];
  };
};

export class ContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractError";
  }
}

const statuses = new Set<DataStatus>([
  "available",
  "empty",
  "partial",
  "unavailable",
]);

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ContractError(`${path} deve ser um objeto.`);
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, path: string): string {
  if (typeof value !== "string")
    throw new ContractError(`${path} deve ser texto.`);
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return string(value, path);
}

function limitations(value: unknown, path: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new ContractError(`${path} deve ser uma lista de textos.`);
  }
  return value;
}

function status(value: unknown, path: string): DataStatus {
  if (typeof value !== "string" || !statuses.has(value as DataStatus)) {
    throw new ContractError(`${path} tem um estado inválido.`);
  }
  return value as DataStatus;
}

function month(value: unknown, path: string): string {
  const result = string(value, path);
  const match = /^(\d{4})-(\d{2})$/.exec(result);
  if (!match || Number(match[2]) < 1 || Number(match[2]) > 12) {
    throw new ContractError(`${path} deve usar YYYY-MM.`);
  }
  return result;
}

export function decodeKpisEnvelope(input: unknown): KpisEnvelope {
  const root = record(input, "resposta");
  const data = record(root.data, "data");
  const metadata = record(root.metadata, "metadata");
  if (!Array.isArray(data.metrics)) {
    throw new ContractError("data.metrics deve ser uma lista.");
  }

  const metricIds = new Set<string>();
  const metrics = data.metrics.map((item, index): KpiMetric => {
    const path = `data.metrics[${index}]`;
    const metric = record(item, path);
    const id = string(metric.id, `${path}.id`);
    if (metricIds.has(id)) throw new ContractError(`${path}.id duplicado.`);
    metricIds.add(id);
    const metricStatus = status(metric.status, `${path}.status`);
    const value = metric.value;
    if (
      value !== null &&
      (typeof value !== "number" || !Number.isFinite(value))
    ) {
      throw new ContractError(
        `${path}.value deve ser um número finito ou null.`,
      );
    }
    if (metricStatus === "available" && value === null) {
      throw new ContractError(
        `${path}.value deve existir quando status é available.`,
      );
    }
    if (
      (metricStatus === "empty" || metricStatus === "unavailable") &&
      value !== null
    ) {
      throw new ContractError(
        `${path}.value deve ser null quando status é ${metricStatus}.`,
      );
    }
    return {
      id,
      label: string(metric.label, `${path}.label`),
      value,
      unit: string(metric.unit, `${path}.unit`),
      status: metricStatus,
      limitations: limitations(metric.limitations, `${path}.limitations`),
    };
  });

  const period = record(metadata.period, "metadata.period");
  const start = month(period.start, "metadata.period.start");
  const end = month(period.end, "metadata.period.end");
  if (start > end)
    throw new ContractError("metadata.period.start deve ser anterior ao fim.");
  const filters = record(metadata.filters, "metadata.filters");
  const source = record(metadata.source, "metadata.source");
  if (metadata.contract_version !== "1.0.0") {
    throw new ContractError("metadata.contract_version deve ser 1.0.0.");
  }
  if (period.granularity !== "month") {
    throw new ContractError("metadata.period.granularity deve ser month.");
  }
  if (source.kind !== "synthetic" || source.is_demo !== true) {
    throw new ContractError(
      "metadata.source deve identificar a demonstração sintética.",
    );
  }
  const updatedAt = string(source.updated_at, "metadata.source.updated_at");
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      updatedAt,
    ) ||
    !Number.isFinite(Date.parse(updatedAt))
  ) {
    throw new ContractError(
      "metadata.source.updated_at deve ser uma data ISO válida.",
    );
  }

  return {
    data: { metrics },
    metadata: {
      contract_version: "1.0.0",
      status: status(metadata.status, "metadata.status"),
      period: {
        start,
        end,
        granularity: "month",
      },
      filters: {
        municipio: nullableString(
          filters.municipio,
          "metadata.filters.municipio",
        ),
        bairro: nullableString(filters.bairro, "metadata.filters.bairro"),
        classe: nullableString(filters.classe, "metadata.filters.classe"),
        alimentador: nullableString(
          filters.alimentador,
          "metadata.filters.alimentador",
        ),
      },
      source: {
        kind: "synthetic",
        version: string(source.version, "metadata.source.version"),
        is_demo: true,
        updated_at: updatedAt,
      },
      limitations: limitations(metadata.limitations, "metadata.limitations"),
    },
  };
}
