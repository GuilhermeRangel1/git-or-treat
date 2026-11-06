import { useId, useRef, useState, type FormEvent } from "react";
import { SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import MonthYearField from "@/shared/ui/MonthYearField";
import type { UCPeriod } from "./contract";
import { formatUCCompetence } from "./uc360-format";

const validCompetence = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/;

type ValidationError = { message: string; start: boolean; end: boolean };

type Props = {
  appliedStart: string;
  appliedEnd: string;
  period: UCPeriod;
  onApply: (start: string, end: string) => void;
};

export default function UC360PeriodForm(props: Props) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <section
        aria-label="Período consultado"
        className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-surface p-4 sm:p-5"
      >
        <div className="flex flex-wrap gap-x-16 gap-y-3">
          <div>
            <p className="text-sm text-muted">Início</p>
            <p className="font-medium text-content">
              {formatUCCompetence(props.period.start)}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted">Fim</p>
            <p className="font-medium text-content">
              {formatUCCompetence(props.period.end)}
            </p>
          </div>
        </div>
        <Button
          ref={triggerRef}
          variant="control"
          onClick={() => setOpen(true)}
          leftIcon={<SlidersHorizontal size={16} aria-hidden="true" />}
        >
          Ajustar filtros
        </Button>
      </section>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha o período para consultar a unidade."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        {open && (
          <PeriodFields
            {...props}
            onApply={(start, end) => {
              props.onApply(start, end);
              setOpen(false);
            }}
          />
        )}
      </Modal>
    </>
  );
}

function PeriodFields({ appliedStart, appliedEnd, period, onApply }: Props) {
  const applied = `${appliedStart}/${appliedEnd}`;
  const [draft, setDraft] = useState({
    applied,
    start: appliedStart || period.start,
    end: appliedEnd || period.end,
  });
  const [validation, setValidation] = useState<ValidationError | null>(null);
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-base font-semibold text-content">
            Período consultado
          </h2>
          <p className="mt-1 text-xs text-muted">
            Escolha o período para atualizar o consumo, os valores e os
            históricos.
          </p>
        </div>
        <p className="w-fit rounded-md bg-canvas px-3 py-2 text-sm text-content">
          <span className="font-medium">Período aplicado:</span>{" "}
          {formatUCCompetence(period.start)} a {formatUCCompetence(period.end)}
        </p>
      </div>
      <fieldset
        role="group"
        aria-label="Selecionar período"
        className="flex min-w-0 flex-wrap items-end justify-between gap-3"
      >
        <legend className="sr-only">Selecionar período</legend>
        <MonthYearField
          label="Início"
          monthLabel="Mês inicial"
          yearLabel="Ano inicial"
          value={start}
          yearRef={startInputRef}
          invalid={validation?.start}
          describedBy={validation?.start ? validationId : undefined}
          onChange={(value) => setDraft({ applied, start: value, end })}
        />
        <MonthYearField
          label="Fim"
          monthLabel="Mês final"
          yearLabel="Ano final"
          value={end}
          yearRef={endInputRef}
          invalid={validation?.end}
          describedBy={validation?.end ? validationId : undefined}
          onChange={(value) => setDraft({ applied, start, end: value })}
        />
        <button
          className="min-h-11 rounded-lg bg-content px-4 text-sm font-medium text-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="submit"
        >
          Aplicar período
        </button>
      </fieldset>
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
