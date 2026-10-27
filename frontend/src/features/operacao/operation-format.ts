import type { OperationPeriod } from "./contract";

const MONTHS = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

export function formatNumber(value: number, maximumFractionDigits = 3): string {
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits,
  }).format(value);
}

export function formatMonth(value: string): string {
  const [year, month] = value.split("-");
  return `${MONTHS[Number(month) - 1] ?? month}/${year}`;
}

export function formatPeriod(period: OperationPeriod): string {
  return `${formatMonth(period.start)} – ${formatMonth(period.end)}`;
}

export function monthsInPeriod(period: OperationPeriod): string[] {
  const [startYear, startMonth] = period.start.split("-").map(Number);
  const [endYear, endMonth] = period.end.split("-").map(Number);
  const start = startYear * 12 + startMonth - 1;
  const end = endYear * 12 + endMonth - 1;
  return Array.from({ length: end - start + 1 }, (_, index) => {
    const monthIndex = start + index;
    const year = Math.floor(monthIndex / 12);
    const month = (monthIndex % 12) + 1;
    return `${year}-${String(month).padStart(2, "0")}`;
  });
}

export function formatUpdatedAt(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(value));
}
