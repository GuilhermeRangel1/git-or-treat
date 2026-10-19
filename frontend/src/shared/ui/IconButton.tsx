import type { ButtonHTMLAttributes } from "react";

export default function IconButton({
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={`inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-control bg-surface text-muted hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${className}`}
      {...props}
    />
  );
}
