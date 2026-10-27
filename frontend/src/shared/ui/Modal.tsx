import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type RefObject,
} from "react";
import { X } from "lucide-react";
import Button from "./Button";

type ModalSize = "xs" | "sm" | "md" | "lg";
type ModalHeader = "inline" | "sticky";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement | null>;
  title: string;
  description?: string;
  closeLabel: string;
  size: ModalSize;
  header: ModalHeader;
  children: ReactNode;
  className?: string;
};

const modalStyles: Record<ModalSize, string> = {
  xs: "fixed inset-0 m-auto max-h-[90dvh] w-[min(35rem,calc(100vw-2rem))] min-w-0 overflow-y-auto rounded-2xl border border-border bg-[var(--bg-elevated)] p-0 text-content shadow-2xl backdrop:bg-black/50",
  sm: "fixed inset-0 m-auto max-h-[90dvh] w-[min(40rem,calc(100vw-2rem))] min-w-0 overflow-y-auto rounded-2xl border border-border bg-[var(--bg-elevated)] p-0 text-content shadow-2xl backdrop:bg-black/50",
  md: "fixed inset-0 m-auto max-h-[90vh] w-[min(720px,calc(100vw-2rem))] min-w-0 overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-content shadow-2xl backdrop:bg-black/50",
  lg: "m-auto max-h-[min(90dvh,56rem)] w-[min(48rem,calc(100%-2rem))] overflow-y-auto rounded-xl border border-border bg-surface p-0 text-content shadow-xl backdrop:bg-black/50",
};

export default function Modal({
  open,
  onClose,
  triggerRef,
  title,
  description,
  closeLabel,
  size,
  header,
  children,
  className,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const wasOpenRef = useRef(false);
  const ignoreCloseEventRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open) {
      if (!dialog.open) {
        if (typeof dialog.showModal === "function") dialog.showModal();
        else dialog.setAttribute("open", "");
      }
      wasOpenRef.current = true;
      return;
    }

    if (dialog.open) {
      if (typeof dialog.close === "function") {
        ignoreCloseEventRef.current = true;
        dialog.close();
      } else {
        dialog.removeAttribute("open");
      }
    }
    if (wasOpenRef.current) {
      triggerRef.current?.focus();
      wasOpenRef.current = false;
    }
  }, [open, triggerRef]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      className={modalStyles[size]}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onKeyDown={(event) => {
        if (
          event.key === "Escape" &&
          typeof dialogRef.current?.showModal !== "function"
        ) {
          event.preventDefault();
          onClose();
        }
      }}
      onClose={() => {
        if (ignoreCloseEventRef.current) {
          ignoreCloseEventRef.current = false;
          return;
        }
        if (open) onClose();
      }}
    >
      {open ? (
        header === "inline" ? (
          <section className={className ?? "grid gap-4 p-5 sm:p-6"}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id={titleId} className="font-heading text-xl font-semibold">
                  {title}
                </h2>
                {description ? (
                  <p id={descriptionId} className="mt-1 text-sm text-muted">
                    {description}
                  </p>
                ) : null}
              </div>
              <Button
                type="button"
                variant="icon"
                size="icon"
                className={
                  size === "sm" || size === "xs" ? "size-11" : undefined
                }
                aria-label={closeLabel}
                onClick={onClose}
              >
                <X size={18} aria-hidden="true" />
              </Button>
            </div>
            {children}
          </section>
        ) : (
          <>
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-border bg-surface px-5 py-4">
              <h2 id={titleId} className="font-heading text-xl font-semibold">
                {title}
              </h2>
              <Button
                type="button"
                variant="icon"
                size="md"
                aria-label={closeLabel}
                onClick={onClose}
              >
                <X size={18} aria-hidden="true" />
              </Button>
            </div>
            {children}
          </>
        )
      ) : null}
    </dialog>
  );
}
