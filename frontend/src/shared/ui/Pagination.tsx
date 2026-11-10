type Props = {
  page: number;
  totalPages: number;
  label: string;
  onPageChange: (page: number) => void;
  pageSize: number;
  onPageSizeChange: (size: number) => void;
};

export default function Pagination({
  page,
  totalPages,
  label,
  onPageChange,
  pageSize,
  onPageSizeChange,
}: Props) {
  const pages = [...new Set([1, totalPages, page - 1, page, page + 1])]
    .filter((number) => number >= 1 && number <= totalPages)
    .sort((a, b) => a - b);
  const sizes = [...new Set([5, 10, 20, 50, pageSize])].sort((a, b) => a - b);
  return (
    <nav
      aria-label={label}
      className="flex flex-wrap items-center justify-between gap-3"
    >
      <div className="flex flex-wrap items-center gap-2">
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
      </div>
      <label className="ml-auto flex items-center gap-2 text-sm">
        <span>Por página</span>
        <select
          aria-label="Por página"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          className="min-h-11 w-20 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-brand"
        >
          {sizes.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
    </nav>
  );
}
