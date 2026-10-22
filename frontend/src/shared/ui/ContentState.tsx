import type { ReactNode } from "react";
import {
  AlertCircle,
  AlertTriangle,
  FileQuestion,
  RefreshCw,
} from "lucide-react";
import Button from "./Button";

export type ContentStateType = "loading" | "empty" | "error" | "partial";

interface ContentStateProps {
  type: ContentStateType;
  title?: string;
  description?: string;
  onRetry?: () => void;
  onResetFilters?: () => void;
  children?: ReactNode;
}

export default function ContentState({
  type,
  title,
  description,
  onRetry,
  onResetFilters,
  children,
}: ContentStateProps) {
  if (type === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="w-full space-y-4 py-8 animate-pulse"
      >
        <span className="sr-only">Carregando indicadores...</span>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div
              key={i}
              className="h-40 rounded-xl border border-border bg-surface p-5 space-y-3"
            >
              <div className="h-4 w-28 bg-[var(--line)] rounded" />
              <div className="h-8 w-36 bg-[var(--line)] rounded" />
              <div className="h-4 w-20 bg-[var(--line-subtle)] rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === "empty") {
    return (
      <div
        role="alert"
        className="my-6 flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/50 p-8 sm:p-12 text-center"
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-[var(--bg-surface-hover)] text-muted mb-4">
          <FileQuestion className="size-6 text-muted" />
        </div>
        <h3 className="font-heading text-lg font-semibold text-content">
          {title || "Nenhum dado encontrado para este recorte"}
        </h3>
        <p className="mt-1.5 max-w-md text-sm text-muted">
          {description ||
            "Não foram registradas leituras ou faturamentos para os filtros de competência, município e classe selecionados. Verifique os critérios aplicados."}
        </p>
        {onResetFilters && (
          <div className="mt-5">
            <Button variant="secondary" onClick={onResetFilters}>
              Restaurar filtros padrão
            </Button>
          </div>
        )}
        {children}
      </div>
    );
  }

  if (type === "error") {
    return (
      <div
        role="alert"
        className="my-6 flex flex-col items-center justify-center rounded-2xl border border-[var(--status-danger)]/30 bg-[var(--status-danger)]/5 p-8 text-center"
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-[var(--status-danger)]/10 text-[var(--status-danger)] mb-4">
          <AlertCircle className="size-6" />
        </div>
        <h3 className="font-heading text-lg font-semibold text-content">
          {title || "Falha ao carregar os indicadores"}
        </h3>
        <p className="mt-1.5 max-w-md text-sm text-muted">
          {description ||
            "Ocorreu uma instabilidade na consulta analítica. Seus filtros foram mantidos para nova tentativa."}
        </p>
        {onResetFilters && (
          <div className="mt-5">
            <Button variant="secondary" onClick={onResetFilters}>
              Restaurar filtros padrão
            </Button>
          </div>
        )}
        {onRetry && (
          <div className="mt-5">
            <Button
              variant="secondary"
              onClick={onRetry}
              leftIcon={<RefreshCw className="size-4" />}
            >
              Tentar novamente
            </Button>
          </div>
        )}
      </div>
    );
  }

  if (type === "partial") {
    return (
      <div
        role="region"
        aria-label="Aviso de período incompleto"
        className="mb-4 flex items-start gap-3 rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning)]/10 p-4 text-sm text-content"
      >
        <AlertTriangle className="size-5 shrink-0 text-[var(--status-warning)] mt-0.5" />
        <div className="flex-1">
          <strong className="font-semibold block text-[var(--status-warning)]">
            {title || "Período incompleto · Competência preliminar em aberto"}
          </strong>
          <span className="text-muted text-xs sm:text-sm">
            {description ||
              "Os números exibidos representam medições e faturamentos parciais até o momento. Indicadores consolidados dependem do fechamento do ciclo regulatório."}
          </span>
        </div>
        {children}
      </div>
    );
  }

  return null;
}
