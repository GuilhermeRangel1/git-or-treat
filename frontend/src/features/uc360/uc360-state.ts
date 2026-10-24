export const UC_HISTORY_SECTIONS = [
  "consumption",
  "invoices",
  "meters",
  "distributed_generation",
  "interruptions",
  "calls",
] as const;
export type UCHistorySection = (typeof UC_HISTORY_SECTIONS)[number];
export type UC360SearchState = {
  q: string;
  uc: string;
  start: string;
  end: string;
  section: UCHistorySection | "";
  searchPage: number;
  historyPage: number;
  invalid: string[];
};
function page(value: string | null) {
  if (value === null) return 1;
  if (!/^[1-9]\d*$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}
function month(value: string | null) {
  return value === null
    ? ""
    : /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value)
      ? value
      : null;
}
export function parseUC360SearchParams(
  params: URLSearchParams,
): UC360SearchState {
  const invalid: string[] = [];
  const one = (key: string) => {
    const values = params.getAll(key);
    if (values.length > 1) invalid.push(`Parâmetro ${key} duplicado.`);
    return values[0] ?? null;
  };
  const startRaw = one("start"),
    endRaw = one("end"),
    qRaw = one("q"),
    ucRaw = one("uc"),
    sectionRaw = one("section");
  const start = month(startRaw),
    end = month(endRaw),
    searchPage = page(one("search_page")),
    historyPage = page(one("history_page"));
  if (start === null || end === null)
    invalid.push("Competência inválida. Use AAAA-MM.");
  if ((startRaw === null) !== (endRaw === null))
    invalid.push("Informe início e fim do período.");
  if (start && end && start > end)
    invalid.push("O início do período deve ser anterior ao fim.");
  if (qRaw !== null && (!qRaw.trim() || qRaw.trim().length > 100))
    invalid.push("Busca inválida: informe de 1 a 100 caracteres.");
  if (searchPage === null || historyPage === null)
    invalid.push("Página inválida.");
  if (
    sectionRaw &&
    !UC_HISTORY_SECTIONS.includes(sectionRaw as UCHistorySection)
  )
    invalid.push("Seção de histórico inválida.");
  return {
    q: qRaw?.trim() ?? "",
    uc: ucRaw?.trim() ?? "",
    start: start ?? "",
    end: end ?? "",
    section:
      UC_HISTORY_SECTIONS.find((section) => section === sectionRaw) ?? "",
    searchPage: searchPage ?? 1,
    historyPage: historyPage ?? 1,
    invalid,
  };
}
export function applyUCSearch(current: URLSearchParams, query: string) {
  const next = new URLSearchParams(current);
  const normalized = query.trim();
  if (normalized) next.set("q", normalized);
  else next.delete("q");
  next.delete("uc");
  next.delete("section");
  next.delete("history_page");
  next.delete("search_page");
  return next;
}
export function selectUC(current: URLSearchParams, uc: string) {
  const next = new URLSearchParams(current);
  next.set("uc", uc);
  next.delete("q");
  next.delete("search_page");
  next.delete("section");
  next.delete("history_page");
  return next;
}
export function applyUCPeriod(
  current: URLSearchParams,
  start: string,
  end: string,
) {
  const next = new URLSearchParams(current);
  next.set("start", start);
  next.set("end", end);
  next.delete("history_page");
  return next;
}
export function selectUCHistory(
  current: URLSearchParams,
  section: UCHistorySection,
) {
  const next = new URLSearchParams(current);
  next.set("section", section);
  next.delete("history_page");
  return next;
}
