import { useId } from "react";
import { ChevronDown } from "lucide-react";

export default function FilterSelect({
  label,
  value,
  options,
  error,
  ariaLabel,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  error?: string;
  ariaLabel?: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const helpId = `${id}-error`;
  const control =
    "min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
  return (
    <label
      htmlFor={id}
      className="grid gap-1.5 text-sm font-medium text-content"
    >
      {label}
      <span className="relative">
        <select
          id={id}
          aria-label={ariaLabel ?? label}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? helpId : undefined}
          className={`${control} ${error ? "border-danger" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
      </span>
      {error ? (
        <span id={helpId} className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </label>
  );
}
