export type OperationMetric = "dec" | "fec";
export type OperationUrlQuery = {
  start: string;
  end: string;
  feederId: string | null;
  municipality: string | null;
  detailFeederId: string | null;
  metric: OperationMetric;
  rankingPage: number;
  page: number;
  pageSize: number;
};
export type ParsedOperationParams = {
  query: OperationUrlQuery | null;
  errors: string[];
};
export type OperationFiltersInput = {
  start: string;
  end: string;
  feederId?: string | null;
  municipality?: string | null;
};

const DEFAULT_START = "2025-01";
const DEFAULT_END = "2025-02";
const DEFAULT_PAGE_SIZE = 20;
const MAX_MONTHS = 120;
const MAX_PAGE = 1_000_000;
const MONTH_PATTERN = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/;
const PARAMS = [
  "periodo",
  "competencia_inicio",
  "competencia_fim",
  "alimentador",
  "municipio",
  "feeder_id",
  "metric",
  "ranking_page",
  "page",
  "page_size",
];

function isMonth(value: string): boolean {
  return MONTH_PATTERN.test(value);
}
function monthDistance(start: string, end: string): number {
  return (
    (Number(end.slice(0, 4)) - Number(start.slice(0, 4))) * 12 +
    Number(end.slice(5)) -
    Number(start.slice(5)) +
    1
  );
}
function parsePositiveInt(
  value: string | null,
  fallback: number,
  maximum: number,
): number | null {
  if (value === null) return fallback;
  if (!/^[1-9]\d*$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed <= maximum ? parsed : null;
}
function readUnique(
  params: URLSearchParams,
  key: string,
  errors: string[],
): string | null {
  const values = params.getAll(key);
  if (values.length > 1) errors.push(`Parâmetro ${key} duplicado.`);
  return values[0] ?? null;
}
function feeder(
  value: string | null,
  label: string,
  errors: string[],
): string | null {
  if (value === null) return null;
  const normalized = value.trim();
  if (!normalized || Array.from(normalized).length > 100) {
    errors.push(`${label} deve conter de 1 a 100 caracteres.`);
    return null;
  }
  return normalized;
}

/** Valida todos os parâmetros antes de habilitar qualquer consulta remota. */
export function parseOperationParams(
  params: URLSearchParams,
): ParsedOperationParams {
  const errors: string[] = [];
  for (const key of new Set(params.keys())) {
    if (!PARAMS.includes(key))
      errors.push(`Parâmetro ${key} não é suportado nesta tela.`);
  }
  const raw = Object.fromEntries(
    PARAMS.map((key) => [key, readUnique(params, key, errors)]),
  );
  const periodAlias = raw.periodo;
  let startRaw = raw.competencia_inicio;
  let endRaw = raw.competencia_fim;
  if (periodAlias !== null && (startRaw !== null || endRaw !== null))
    errors.push("Não combine o período único com o intervalo de meses.");
  if (periodAlias !== null) startRaw = endRaw = periodAlias;
  if ((startRaw === null) !== (endRaw === null))
    errors.push("Informe início e fim do período.");
  const start = startRaw === null ? DEFAULT_START : startRaw;
  const end = endRaw === null ? DEFAULT_END : endRaw;
  if (!isMonth(start) || !isMonth(end))
    errors.push("Mês inválido. Escolha um mês e ano válidos.");
  if (isMonth(start) && isMonth(end)) {
    if (start > end)
      errors.push("O início do período deve ser anterior ao fim.");
    else if (monthDistance(start, end) > MAX_MONTHS)
      errors.push("O período permite no máximo 120 meses.");
  }

  const feederId = feeder(raw.alimentador, "O filtro de alimentador", errors);
  const municipality = feeder(raw.municipio, "O filtro de município", errors);
  const detailFeederId = feeder(
    raw.feeder_id,
    "O alimentador do detalhe",
    errors,
  );
  const metric = raw.metric === null ? "dec" : raw.metric;
  if (metric !== "dec" && metric !== "fec")
    errors.push("Métrica inválida. Use dec ou fec.");
  const page = parsePositiveInt(raw.page, 1, MAX_PAGE);
  const rankingPage = parsePositiveInt(raw.ranking_page, 1, MAX_PAGE);
  const pageSize = parsePositiveInt(raw.page_size, DEFAULT_PAGE_SIZE, 100);
  if (page === null)
    errors.push("Página inválida; use inteiro entre 1 e 1.000.000.");
  if (pageSize === null)
    errors.push("Tamanho da página inválido; use inteiro entre 1 e 100.");

  if (
    errors.length > 0 ||
    (metric !== "dec" && metric !== "fec") ||
    page === null ||
    rankingPage === null ||
    pageSize === null
  )
    return { query: null, errors };
  return {
    query: {
      start,
      end,
      feederId,
      municipality,
      detailFeederId,
      metric,
      rankingPage,
      page,
      pageSize,
    },
    errors,
  };
}

/** Atualiza filtros aplicados e volta ao primeiro recorte da lista. */
export function applyOperationFilters(
  current: URLSearchParams,
  filters: OperationFiltersInput,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.delete("periodo");
  next.set("competencia_inicio", filters.start);
  next.set("competencia_fim", filters.end);
  if (filters.feederId?.trim())
    next.set("alimentador", filters.feederId.trim());
  else next.delete("alimentador");
  if (filters.municipality?.trim())
    next.set("municipio", filters.municipality.trim());
  else next.delete("municipio");
  next.delete("feeder_id");
  next.delete("page");
  next.delete("ranking_page");
  return next;
}

export function changeOperationMetric(
  current: URLSearchParams,
  metric: OperationMetric,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("metric", metric);
  next.delete("feeder_id");
  next.delete("page");
  next.delete("ranking_page");
  return next;
}

/** Abre um alimentador conservando o intervalo, filtro e ordenação que originaram a seleção. */
export function openOperationDetail(
  current: URLSearchParams,
  feederId: string,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("feeder_id", feederId);
  next.delete("page");
  next.set("page_size", String(DEFAULT_PAGE_SIZE));
  return next;
}

export function returnToOperationRanking(
  current: URLSearchParams,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.delete("feeder_id");
  next.delete("page");
  next.delete("page_size");
  return next;
}

export function paginateOperationDetail(
  current: URLSearchParams,
  page: number,
): URLSearchParams {
  const next = new URLSearchParams(current);
  if (page <= 1) next.delete("page");
  else next.set("page", String(page));
  return next;
}

/** Pagina somente a lista Gold já ordenada globalmente pela API. */
export function paginateOperationRanking(
  current: URLSearchParams,
  page: number,
): URLSearchParams {
  const next = new URLSearchParams(current);
  if (page <= 1) next.delete("ranking_page");
  else next.set("ranking_page", String(page));
  return next;
}
