import { useId, useRef, useState, type FormEvent } from "react";
import type { UCPeriod } from "./contract";
import { formatUCCompetence } from "./uc360-format";

const inputClass =
  "min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const validCompetence = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/;

type ValidationError = { message: string; start: boolean; end: boolean };

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
    start: appliedStart || period.start,
    end: appliedEnd || period.end,
  });
  const [validation, setValidation] = useState<ValidationError | null>(null);
  const startId = useId();
  const endId = useId();
  const validationId = useId();
  const startInputRef = useRef<HTMLInputElement>(null);
  const endInputRef = useRef<HTMLInputElement>(null);
  const start =
    draft.applied === applied ? draft.start : appliedStart || period.start;
  const end = draft.applied === applied ? draft.end : appliedEnd || period.end;

  function submit(event: FormEvent) {
    event.preventDefault();
    const startValid = validCompetence.test(start);
    const endValid = validCompetence.test(end);
    const inverted = startValid && endValid && start > end;
    if (!startValid || !endValid || inverted) {
      setValidation({
        message:
          "Informe competências válidas e mantenha o início antes do fim.",
        start: !startValid || inverted,
        end: !endValid || inverted,
      });
      if (!startValid || inverted) startInputRef.current?.focus();
      else endInputRef.current?.focus();
      return;
    }
    setValidation(null);
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
            ref={startInputRef}
            id={startId}
            className={inputClass}
            aria-label="Competência inicial"
            aria-invalid={validation?.start || undefined}
            aria-describedby={validation?.start ? validationId : undefined}
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
            ref={endInputRef}
            id={endId}
            className={inputClass}
            aria-label="Competência final"
            aria-invalid={validation?.end || undefined}
            aria-describedby={validation?.end ? validationId : undefined}
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
        <span
          id={validationId}
          className="w-full text-sm text-danger"
          role="alert"
        >
          {validation.message}
        </span>
      )}
    </form>
  );
}
