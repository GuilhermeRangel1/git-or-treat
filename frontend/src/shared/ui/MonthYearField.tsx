import type { Ref } from "react";

const months = [
  ["01", "Janeiro"],
  ["02", "Fevereiro"],
  ["03", "Março"],
  ["04", "Abril"],
  ["05", "Maio"],
  ["06", "Junho"],
  ["07", "Julho"],
  ["08", "Agosto"],
  ["09", "Setembro"],
  ["10", "Outubro"],
  ["11", "Novembro"],
  ["12", "Dezembro"],
] as const;

const controlClass =
  "min-h-11 w-full min-w-0 rounded-lg border border-control bg-canvas px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

type MonthYearFieldProps = {
  label: string;
  monthLabel: string;
  yearLabel: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  describedBy?: string;
  yearRef?: Ref<HTMLInputElement>;
};

export default function MonthYearField({
  label,
  monthLabel,
  yearLabel,
  value,
  onChange,
  invalid = false,
  describedBy,
  yearRef,
}: MonthYearFieldProps) {
  const [year = "", month = ""] = value.split("-", 2);
  const selectedMonth = month || "01";

  function changeMonth(nextMonth: string) {
    onChange(`${year}-${nextMonth}`);
  }

  function changeYear(nextYear: string) {
    onChange(
      `${nextYear.replace(/\D/g, "").slice(0, 4)}-${selectedMonth}`,
    );
  }

  return (
    <fieldset className="grid min-w-0 gap-1.5 text-sm font-medium text-content">
      <legend>{label}</legend>
      <div className="grid min-w-0 grid-cols-[minmax(9rem,1fr)_minmax(5.5rem,0.7fr)] gap-2">
        <select
          aria-label={monthLabel}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className={controlClass}
          value={selectedMonth}
          onChange={(event) => changeMonth(event.target.value)}
        >
          {months.map(([monthValue, monthName]) => (
            <option key={monthValue} value={monthValue}>
              {monthName}
            </option>
          ))}
        </select>
        <input
          ref={yearRef}
          aria-label={yearLabel}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          className={controlClass}
          type="text"
          inputMode="numeric"
          maxLength={4}
          placeholder="Ano"
          value={year}
          autoComplete="off"
          onChange={(event) => changeYear(event.target.value)}
        />
      </div>
    </fieldset>
  );
}
