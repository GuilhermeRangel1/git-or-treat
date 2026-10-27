import { useState, type FormEvent } from "react";
import type { UCPeriod } from "./contract";
import { formatUCCompetence } from "./uc360-format";

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
      aria-label="Período da consulta"
      className="grid gap-3 rounded-xl border border-control bg-surface p-4 sm:p-5"
    >
      <div>
        <h2 className="font-heading text-base font-semibold text-content">
          Período consultado
        </h2>
        <p className="mt-1 text-xs text-muted">
          Escolha as competências para atualizar indicadores e históricos.
        </p>
      </div>
      <fieldset
        role="group"
        aria-label="Selecionar período"
        className="flex min-w-0 flex-wrap items-end gap-3"
      >
        <legend className="sr-only">Selecionar período</legend>
        <label className="grid gap-1 text-xs font-medium text-muted">
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
        <label className="grid gap-1 text-xs font-medium text-muted">
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
          className="min-h-11 rounded-lg bg-content px-4 text-sm font-medium text-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="submit"
        >
          Aplicar período
        </button>
      </fieldset>
      <p className="w-fit rounded-md bg-canvas px-3 py-2 text-sm text-content">
        <span className="font-medium">Período aplicado:</span>{" "}
        {formatUCCompetence(period.start)} a {formatUCCompetence(period.end)}
      </p>
      {validation && (
        <span className="w-full text-sm text-danger" role="alert">
          {validation}
        </span>
      )}
    </form>
  );
}
