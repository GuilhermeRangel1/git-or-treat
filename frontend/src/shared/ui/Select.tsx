import { type SelectHTMLAttributes, useId } from "react";
import { ChevronDown } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps extends Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "size"
> {
  label?: string;
  options: SelectOption[];
  helperText?: string;
  error?: string;
}

export default function Select({
  label,
  options,
  helperText,
  error,
  id: customId,
  className = "",
  disabled,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const id = customId || generatedId;

  return (
    <div className="flex min-w-0 flex-col gap-1.5 w-full">
      {label && (
        <label
          htmlFor={id}
          className="text-xs font-medium text-muted uppercase tracking-wider font-mono"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={id}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={error || helperText ? `${id}-help` : undefined}
          className={`min-w-0 max-w-full w-full h-11 appearance-none rounded-lg border bg-surface px-3.5 pr-10 text-sm text-content transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${
            error
              ? "border-[var(--status-danger)] focus-visible:outline-[var(--status-danger)]"
              : "border-control hover:border-content"
          } ${className}`}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 size-4 text-muted" />
      </div>
      {(error || helperText) && (
        <span
          id={`${id}-help`}
          className={`text-xs ${
            error ? "text-[var(--status-danger)]" : "text-muted"
          }`}
        >
          {error || helperText}
        </span>
      )}
    </div>
  );
}
