import { useState, type FormEvent } from "react";
import type { UCPeriod } from "./contract";

const inputClass =
  "min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

type Props = {
  appliedStart: string;
  appliedEnd: string;
  period: UCPeriod;
  onApply: (start: string, end: string) => void;
};

export default function UC360PeriodForm({
  appliedStart,
  appliedEnd,
  period,
  onApply,
}: Props) {
  const applied = `${appliedStart}/${appliedEnd}`;
  const [draft, setDraft] = useState({
    applied,
    start: appliedStart || "2025-01",
    end: appliedEnd || "2025-02",
  });
  const [validation, setValidation] = useState("");
  const start =
    draft.applied === applied ? draft.start : appliedStart || "2025-01";
  const end = draft.applied === applied ? draft.end : appliedEnd || "2025-02";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(start) ||
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(end) ||
      start > end
    ) {
      setValidation(
        "Informe competências válidas e mantenha o início antes do fim.",
      );
      return;
    }
    setValidation("");
    onApply(start, end);
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-3 rounded-xl bg-surface p-4"
    >
      <label className="grid gap-1 text-xs text-muted">
        Início
        <input
          className={inputClass}
          aria-label="Competência inicial"
          type="month"
          value={start}
          onChange={(event) =>
            setDraft({ applied, start: event.target.value, end })
          }
        />
      </label>
      <label className="grid gap-1 text-xs text-muted">
        Fim
        <input
          className={inputClass}
          aria-label="Competência final"
          type="month"
          value={end}
          onChange={(event) =>
            setDraft({ applied, start, end: event.target.value })
          }
        />
      </label>
      <button
        className="min-h-11 rounded-lg border border-control px-4 text-sm text-content focus-visible:outline-2 focus-visible:outline-brand"
        type="submit"
      >
        Aplicar período
      </button>
      <span className="text-xs text-muted">
        Período: {period.start} a {period.end}
      </span>
      {validation && (
        <span className="w-full text-sm text-danger" role="alert">
          {validation}
        </span>
      )}
    </form>
  );
}
