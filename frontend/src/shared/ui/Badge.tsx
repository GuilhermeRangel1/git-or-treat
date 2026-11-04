import type { HTMLAttributes, ReactNode } from "react";

export type BadgeVariant =
  "neutral" | "goiaba" | "pistache" | "warning" | "info" | "outline";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
}

export default function Badge({
  variant = "neutral",
  className = "",
  children,
  ...props
}: BadgeProps) {
  const variantStyles: Record<BadgeVariant, string> = {
    neutral:
      "bg-[var(--bg-surface-hover)] text-muted border border-[var(--line-subtle)]",
    goiaba:
      "bg-[var(--accent-goiaba-subtle)] text-[var(--accent-goiaba)] border border-[var(--accent-goiaba)]/20",
    pistache:
      "bg-[var(--accent-pistache-subtle)] text-[var(--accent-pistache)] border border-[var(--accent-pistache)]/25",
    warning:
      "bg-[var(--status-warning)]/10 text-[var(--status-warning)] border border-[var(--status-warning)]/20",
    info: "bg-[var(--status-info)]/10 text-[var(--status-info)] border border-[var(--status-info)]/20",
    outline: "bg-transparent text-muted border border-border",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono tracking-tight transition-colors ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
