import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "@/shared/ui/Button";
import { pageWindow } from "./ranking-pagination";

export default function NumberedPagination({
  page,
  pageCount,
  onPageChange,
}: {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      <Button
        variant="icon"
        size="icon"
        aria-label="Página anterior"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <ChevronLeft aria-hidden="true" className="size-4" />
      </Button>
      {pageWindow(page, pageCount).map((item, index) =>
        item === "ellipsis" ? (
          <span
            key={`gap-${index}`}
            aria-hidden="true"
            className="px-1 text-muted"
          >
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            aria-label={`Página ${item}`}
            aria-current={item === page ? "page" : undefined}
            className={`size-10 cursor-pointer rounded-lg border text-sm tabular-nums transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              item === page
                ? "border-brand bg-brand/10 font-semibold text-brand"
                : "border-border text-content hover:bg-surface-hover"
            }`}
            onClick={() => onPageChange(item)}
          >
            {item}
          </button>
        ),
      )}
      <Button
        variant="icon"
        size="icon"
        aria-label="Próxima página"
        disabled={page >= pageCount}
        onClick={() => onPageChange(page + 1)}
      >
        <ChevronRight aria-hidden="true" className="size-4" />
      </Button>
    </div>
  );
}
