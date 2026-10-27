export type RevenueStatus = "available" | "empty" | "partial" | "unavailable";

export type RevenueFilters = {
  municipio: string | null;
  bairro: string | null;
  classe: string | null;
  alimentador: string | null;
};

export type RevenueSnapshot = {
  competencia: string;
  billed_amount: number | null;
  billed_energy_kwh: number | null;
  observed_price_brl_per_kwh: number | null;
  billed_uc_count: number | null;
  status: RevenueStatus;
  limitations: string[];
};

export type RevenueComparison = {
  initial: RevenueSnapshot;
  final: RevenueSnapshot;
  billed_amount_change_brl: number | null;
  billed_energy_change_kwh: number | null;
  measured_energy_change_kwh: number | null;
  billed_amount_change_percent: number | null;
};

export type RevenueQuality = {
  small_base_threshold_uc: number;
  small_base: boolean;
  percent_change_eligible: boolean;
  limitations: string[];
};

export type RevenueMetricCoverage = {
  status: RevenueStatus;
  covered_months: string[];
  missing_months: string[];
  limitations: string[];
};

export type RevenueEnvelope = {
  data: {
    currency_unit: "BRL";
    energy_unit: "kWh";
    total_billed_amount: number | null;
    total_paid_amount: number | null;
    total_measured_energy_kwh: number | null;
    total_billed_energy_kwh: number | null;
    observed_price_brl_per_kwh: number | null;
    series: Array<{
      competencia: string;
      billed_amount: number | null;
      paid_amount: number | null;
      measured_energy_kwh: number | null;
      billed_energy_kwh: number | null;
    }>;
    comparison: RevenueComparison;
    price_volume: {
      method: "endpoint_price_volume";
      reference_version: "dev03-v1" | "gold-csv-v1";
      price_effect_brl: number | null;
      volume_effect_brl: number | null;
      interaction_effect_brl: number | null;
      rounding_adjustment_brl: number | null;
      status: RevenueStatus;
      limitations: string[];
    };
    coverage: {
      requested_months: string[];
      billed_amount: RevenueMetricCoverage;
      billed_energy_kwh: RevenueMetricCoverage;
      paid_amount: RevenueMetricCoverage;
      measured_energy_kwh: RevenueMetricCoverage;
    };
    quality: RevenueQuality;
    breakdown: {
      dimension: "municipio" | "bairro" | "classe";
      items: Array<{
        key: string;
        label: string;
        filters: RevenueFilters;
        comparison: RevenueComparison;
        quality: RevenueQuality;
      }>;
      reconciliation: {
        status: RevenueStatus;
        initial_known_sum_brl: number | null;
        final_known_sum_brl: number | null;
        comparable_change_sum_brl: number | null;
        non_comparable_group_count: number;
        unattributed_change_brl: number | null;
        residual_brl: number | null;
        limitations: string[];
      };
    };
    filter_options: {
      municipios: string[];
      bairros: Array<{ municipio: string; bairro: string }>;
      classes: string[];
    };
  };
  metadata: {
    contract_version: "1.1.0";
    status: RevenueStatus;
    period: { start: string; end: string; granularity: "month" };
    filters: RevenueFilters;
    source: {
      kind: string;
      version: string;
      is_demo: boolean;
      updated_at: string;
    };
    limitations: string[];
  };
};

export class RevenueContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RevenueContractError";
  }
}

function object(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new RevenueContractError(`${path} deve ser um objeto.`);
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, path: string): string {
  if (typeof value !== "string") {
    throw new RevenueContractError(`${path} deve ser texto.`);
  }
  return value;
}

function month(value: unknown, path: string): string {
  const parsed = string(value, path);
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(parsed)) {
    throw new RevenueContractError(`${path} deve conter mês e ano válidos.`);
  }
  return parsed;
}

function number(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new RevenueContractError(`${path} deve ser um número finito.`);
  }
  return value;
}

function nullableNumber(value: unknown, path: string): number | null {
  return value === null ? null : number(value, path);
}

function strings(value: unknown, path: string): string[] {
  if (!Array.isArray(value)) {
    throw new RevenueContractError(`${path} deve ser uma lista de textos.`);
  }
  return value.map((item, index) => string(item, `${path}[${index}]`));
}

function status(value: unknown, path: string): RevenueStatus {
  if (
    value !== "available" &&
    value !== "empty" &&
    value !== "partial" &&
    value !== "unavailable"
  ) {
    throw new RevenueContractError(`${path} contém estado inválido.`);
  }
  return value;
}

function filters(value: unknown, path: string): RevenueFilters {
  const input = object(value, path);
  const nullableFilter = (key: keyof RevenueFilters) => {
    const entry = input[key];
    if (entry === null) return null;
    const parsed = string(entry, `${path}.${key}`);
    if (!parsed) {
      throw new RevenueContractError(`${path}.${key} não pode ser vazio.`);
    }
    return parsed;
  };
  return {
    municipio: nullableFilter("municipio"),
    bairro: nullableFilter("bairro"),
    classe: nullableFilter("classe"),
    alimentador: nullableFilter("alimentador"),
  };
}

function quality(value: unknown, path: string): RevenueQuality {
  const input = object(value, path);
  const threshold = number(
    input.small_base_threshold_uc,
    `${path}.small_base_threshold_uc`,
  );
  if (!Number.isInteger(threshold) || threshold < 0) {
    throw new RevenueContractError(
      `${path}.small_base_threshold_uc deve ser inteiro não negativo.`,
    );
  }
  if (typeof input.small_base !== "boolean") {
    throw new RevenueContractError(`${path}.small_base deve ser booleano.`);
  }
  if (typeof input.percent_change_eligible !== "boolean") {
    throw new RevenueContractError(
      `${path}.percent_change_eligible deve ser booleano.`,
    );
  }
  return {
    small_base_threshold_uc: threshold,
    small_base: input.small_base,
    percent_change_eligible: input.percent_change_eligible,
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}

function snapshot(value: unknown, path: string): RevenueSnapshot {
  const input = object(value, path);
  const count = nullableNumber(
    input.billed_uc_count,
    `${path}.billed_uc_count`,
  );
  if (count !== null && (!Number.isInteger(count) || count < 0)) {
    throw new RevenueContractError(
      `${path}.billed_uc_count deve ser inteiro não negativo ou null.`,
    );
  }
  return {
    competencia: month(input.competencia, `${path}.competencia`),
    billed_amount: nullableNumber(input.billed_amount, `${path}.billed_amount`),
    billed_energy_kwh: nullableNumber(
      input.billed_energy_kwh,
      `${path}.billed_energy_kwh`,
    ),
    observed_price_brl_per_kwh: nullableNumber(
      input.observed_price_brl_per_kwh,
      `${path}.observed_price_brl_per_kwh`,
    ),
    billed_uc_count: count,
    status: status(input.status, `${path}.status`),
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}

function comparison(value: unknown, path: string): RevenueComparison {
  const input = object(value, path);
  return {
    initial: snapshot(input.initial, `${path}.initial`),
    final: snapshot(input.final, `${path}.final`),
    billed_amount_change_brl: nullableNumber(
      input.billed_amount_change_brl,
      `${path}.billed_amount_change_brl`,
    ),
    billed_energy_change_kwh: nullableNumber(
      input.billed_energy_change_kwh,
      `${path}.billed_energy_change_kwh`,
    ),
    measured_energy_change_kwh: nullableNumber(
      input.measured_energy_change_kwh,
      `${path}.measured_energy_change_kwh`,
    ),
    billed_amount_change_percent: nullableNumber(
      input.billed_amount_change_percent,
      `${path}.billed_amount_change_percent`,
    ),
  };
}

function metricCoverage(value: unknown, path: string): RevenueMetricCoverage {
  const input = object(value, path);
  return {
    status: status(input.status, `${path}.status`),
    covered_months: strings(input.covered_months, `${path}.covered_months`).map(
      (item, index) => month(item, `${path}.covered_months[${index}]`),
    ),
    missing_months: strings(input.missing_months, `${path}.missing_months`).map(
      (item, index) => month(item, `${path}.missing_months[${index}]`),
    ),
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}

export function decodeRevenueEnvelope(input: unknown): RevenueEnvelope {
  const root = object(input, "resposta");
  const data = object(root.data, "data");
  const metadata = object(root.metadata, "metadata");
  if (metadata.contract_version !== "1.1.0") {
    throw new RevenueContractError("metadata.contract_version deve ser 1.1.0.");
  }

  const period = object(metadata.period, "metadata.period");
  const start = month(period.start, "metadata.period.start");
  const end = month(period.end, "metadata.period.end");
  if (start > end || period.granularity !== "month") {
    throw new RevenueContractError("metadata.period inválido.");
  }

  const source = object(metadata.source, "metadata.source");
  if (typeof source.is_demo !== "boolean") {
    throw new RevenueContractError(
      "metadata.source.is_demo deve ser booleano.",
    );
  }
  const updatedAt = string(source.updated_at, "metadata.source.updated_at");
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      updatedAt,
    ) ||
    !Number.isFinite(Date.parse(updatedAt))
  ) {
    throw new RevenueContractError(
      "metadata.source.updated_at deve ser uma data ISO válida.",
    );
  }

  if (data.currency_unit !== "BRL" || data.energy_unit !== "kWh") {
    throw new RevenueContractError("Unidades de Receita incompatíveis.");
  }

  if (!Array.isArray(data.series)) {
    throw new RevenueContractError("data.series deve ser uma lista.");
  }
  const series = data.series.map((item, index) => {
    const path = `data.series[${index}]`;
    const row = object(item, path);
    return {
      competencia: month(row.competencia, `${path}.competencia`),
      billed_amount: nullableNumber(row.billed_amount, `${path}.billed_amount`),
      paid_amount: nullableNumber(row.paid_amount, `${path}.paid_amount`),
      measured_energy_kwh: nullableNumber(
        row.measured_energy_kwh,
        `${path}.measured_energy_kwh`,
      ),
      billed_energy_kwh: nullableNumber(
        row.billed_energy_kwh,
        `${path}.billed_energy_kwh`,
      ),
    };
  });
  if (
    series.some(
      (item, index) =>
        index > 0 && series[index - 1].competencia >= item.competencia,
    )
  ) {
    throw new RevenueContractError(
      "data.series deve estar em ordem cronológica sem duplicatas.",
    );
  }

  const priceVolume = object(data.price_volume, "data.price_volume");
  if (
    priceVolume.method !== "endpoint_price_volume" ||
    !["dev03-v1", "gold-csv-v1"].includes(String(priceVolume.reference_version))
  ) {
    throw new RevenueContractError(
      "data.price_volume contém método ou versão inválida.",
    );
  }

  const coverage = object(data.coverage, "data.coverage");
  const breakdown = object(data.breakdown, "data.breakdown");
  const dimension = breakdown.dimension;
  if (
    dimension !== "municipio" &&
    dimension !== "bairro" &&
    dimension !== "classe"
  ) {
    throw new RevenueContractError("data.breakdown.dimension inválida.");
  }
  if (!Array.isArray(breakdown.items)) {
    throw new RevenueContractError("data.breakdown.items deve ser uma lista.");
  }
  const items = breakdown.items.map((item, index) => {
    const path = `data.breakdown.items[${index}]`;
    const row = object(item, path);
    return {
      key: string(row.key, `${path}.key`),
      label: string(row.label, `${path}.label`),
      filters: filters(row.filters, `${path}.filters`),
      comparison: comparison(row.comparison, `${path}.comparison`),
      quality: quality(row.quality, `${path}.quality`),
    };
  });
  const reconciliation = object(
    breakdown.reconciliation,
    "data.breakdown.reconciliation",
  );
  const nonComparableCount = number(
    reconciliation.non_comparable_group_count,
    "data.breakdown.reconciliation.non_comparable_group_count",
  );
  if (!Number.isInteger(nonComparableCount) || nonComparableCount < 0) {
    throw new RevenueContractError(
      "data.breakdown.reconciliation.non_comparable_group_count deve ser inteiro não negativo.",
    );
  }
  const filterOptions = object(data.filter_options, "data.filter_options");
  if (!Array.isArray(filterOptions.bairros)) {
    throw new RevenueContractError(
      "data.filter_options.bairros deve ser uma lista.",
    );
  }
  const bairros = filterOptions.bairros.map((item, index) => {
    const path = `data.filter_options.bairros[${index}]`;
    const bairro = object(item, path);
    return {
      municipio: string(bairro.municipio, `${path}.municipio`),
      bairro: string(bairro.bairro, `${path}.bairro`),
    };
  });

  return {
    data: {
      currency_unit: "BRL",
      energy_unit: "kWh",
      total_billed_amount: nullableNumber(
        data.total_billed_amount,
        "data.total_billed_amount",
      ),
      total_paid_amount: nullableNumber(
        data.total_paid_amount,
        "data.total_paid_amount",
      ),
      total_measured_energy_kwh: nullableNumber(
        data.total_measured_energy_kwh,
        "data.total_measured_energy_kwh",
      ),
      total_billed_energy_kwh: nullableNumber(
        data.total_billed_energy_kwh,
        "data.total_billed_energy_kwh",
      ),
      observed_price_brl_per_kwh: nullableNumber(
        data.observed_price_brl_per_kwh,
        "data.observed_price_brl_per_kwh",
      ),
      series,
      comparison: comparison(data.comparison, "data.comparison"),
      price_volume: {
        method: "endpoint_price_volume",
        reference_version: priceVolume.reference_version as
          "dev03-v1" | "gold-csv-v1",
        price_effect_brl: nullableNumber(
          priceVolume.price_effect_brl,
          "data.price_volume.price_effect_brl",
        ),
        volume_effect_brl: nullableNumber(
          priceVolume.volume_effect_brl,
          "data.price_volume.volume_effect_brl",
        ),
        interaction_effect_brl: nullableNumber(
          priceVolume.interaction_effect_brl,
          "data.price_volume.interaction_effect_brl",
        ),
        rounding_adjustment_brl: nullableNumber(
          priceVolume.rounding_adjustment_brl,
          "data.price_volume.rounding_adjustment_brl",
        ),
        status: status(priceVolume.status, "data.price_volume.status"),
        limitations: strings(
          priceVolume.limitations,
          "data.price_volume.limitations",
        ),
      },
      coverage: {
        requested_months: strings(
          coverage.requested_months,
          "data.coverage.requested_months",
        ).map((item, index) =>
          month(item, `data.coverage.requested_months[${index}]`),
        ),
        billed_amount: metricCoverage(
          coverage.billed_amount,
          "data.coverage.billed_amount",
        ),
        billed_energy_kwh: metricCoverage(
          coverage.billed_energy_kwh,
          "data.coverage.billed_energy_kwh",
        ),
        paid_amount: metricCoverage(
          coverage.paid_amount,
          "data.coverage.paid_amount",
        ),
        measured_energy_kwh: metricCoverage(
          coverage.measured_energy_kwh,
          "data.coverage.measured_energy_kwh",
        ),
      },
      quality: quality(data.quality, "data.quality"),
      breakdown: {
        dimension,
        items,
        reconciliation: {
          status: status(
            reconciliation.status,
            "data.breakdown.reconciliation.status",
          ),
          initial_known_sum_brl: nullableNumber(
            reconciliation.initial_known_sum_brl,
            "data.breakdown.reconciliation.initial_known_sum_brl",
          ),
          final_known_sum_brl: nullableNumber(
            reconciliation.final_known_sum_brl,
            "data.breakdown.reconciliation.final_known_sum_brl",
          ),
          comparable_change_sum_brl: nullableNumber(
            reconciliation.comparable_change_sum_brl,
            "data.breakdown.reconciliation.comparable_change_sum_brl",
          ),
          non_comparable_group_count: nonComparableCount,
          unattributed_change_brl: nullableNumber(
            reconciliation.unattributed_change_brl,
            "data.breakdown.reconciliation.unattributed_change_brl",
          ),
          residual_brl: nullableNumber(
            reconciliation.residual_brl,
            "data.breakdown.reconciliation.residual_brl",
          ),
          limitations: strings(
            reconciliation.limitations,
            "data.breakdown.reconciliation.limitations",
          ),
        },
      },
      filter_options: {
        municipios: strings(
          filterOptions.municipios,
          "data.filter_options.municipios",
        ),
        bairros,
        classes: strings(filterOptions.classes, "data.filter_options.classes"),
      },
    },
    metadata: {
      contract_version: "1.1.0",
      status: status(metadata.status, "metadata.status"),
      period: { start, end, granularity: "month" },
      filters: filters(metadata.filters, "metadata.filters"),
      source: {
        kind: string(source.kind, "metadata.source.kind"),
        version: string(source.version, "metadata.source.version"),
        is_demo: source.is_demo,
        updated_at: updatedAt,
      },
      limitations: strings(metadata.limitations, "metadata.limitations"),
    },
  };
}
