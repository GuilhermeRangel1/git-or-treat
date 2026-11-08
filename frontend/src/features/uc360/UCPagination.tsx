type Props = {
  page: number;
  totalPages: number;
  label: string;
  onPageChange: (page: number) => void;
};

export default function UCPagination({
  page,
  totalPages,
  label,
  onPageChange,
}: Props) {
  const pages = [...new Set([1, totalPages, page - 1, page, page + 1])]
    .filter((number) => number >= 1 && number <= totalPages)
    .sort((a, b) => a - b);

  return (
    <nav aria-label={label} className="flex flex-wrap items-center gap-2">
      {pages.map((number, index) => (
        <span key={number} className="flex items-center gap-2">
          {index > 0 && number - pages[index - 1] > 1 && (
            <span aria-hidden="true" className="text-muted">
              …
            </span>
          )}
          <button
            type="button"
            aria-label={`Página ${number}`}
            aria-current={number === page ? "page" : undefined}
            onClick={() => onPageChange(number)}
            className={`inline-flex size-11 items-center justify-center rounded-lg border text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${number === page ? "border-brand bg-brand text-[var(--accent-goiaba-text)]" : "border-control bg-surface text-content hover:bg-surface-hover"}`}
          >
            {number}
          </button>
        </span>
      ))}
    </nav>
  );
}
