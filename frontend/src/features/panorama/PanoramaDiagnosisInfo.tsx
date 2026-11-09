import { useId, useState } from "react";
import { Info } from "lucide-react";

/** O elemento pai precisa de `relative`: o texto abre logo abaixo dele. */
export default function PanoramaDiagnosisInfo({
  label,
  children,
}: {
  label: string;
  children: string;
}) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  return (
    <>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? contentId : undefined}
        onClick={() => setOpen((current) => !current)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
        className="inline-grid size-8 place-items-center rounded-full text-muted hover:bg-surface-hover hover:text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <Info aria-hidden="true" className="size-4" />
      </button>
      {open ? (
        <div
          id={contentId}
          className="absolute left-0 top-full z-10 w-full max-w-md rounded-lg border border-border bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-content shadow-md"
        >
          {children}
        </div>
      ) : null}
    </>
  );
}
