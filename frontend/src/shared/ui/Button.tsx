import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "ghost"
  | "control"
  | "accent"
  | "icon"
  | "neutral"
  | "danger";
export type ButtonSize = "sm" | "md" | "lg" | "icon" | "wide";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingLabel?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  ref?: Ref<HTMLButtonElement>;
  children: ReactNode;
}

export default function Button({
  variant = "secondary",
  size = "md",
  isLoading = false,
  loadingLabel = "Processando...",
  leftIcon,
  rightIcon,
  className = "",
  disabled,
  ref,
  children,
  ...props
}: ButtonProps) {
  const sizeStyles: Record<ButtonSize, string> = {
    sm: "h-9 px-3 text-xs gap-1.5 rounded-md",
    md: "h-11 px-4 text-sm gap-2 rounded-lg",
    lg: "h-12 px-6 text-base gap-2.5 rounded-lg",
    icon: "size-10 p-0 rounded-lg",
    wide: "h-11 px-5 text-sm gap-2 rounded-lg",
  };

  const variantStyles: Record<ButtonVariant, string> = {
    primary:
      "bg-brand text-[var(--accent-goiaba-text)] hover:bg-[var(--accent-goiaba-hover)] active:opacity-95 shadow-sm border border-transparent font-medium",
    secondary:
      "bg-surface text-content hover:bg-surface-hover border border-control shadow-sm font-medium",
    outline:
      "bg-transparent text-content hover:bg-surface-hover border border-border font-medium",
    ghost:
      "bg-transparent text-muted hover:text-content hover:bg-surface-hover font-normal",
    control:
      "bg-canvas text-content hover:bg-surface-hover border border-control font-semibold",
    accent:
      "bg-brand text-[var(--accent-goiaba-text)] hover:opacity-90 border border-transparent font-semibold",
    icon: "border border-control bg-surface text-content hover:bg-surface-hover",
    neutral:
      "bg-[var(--action-neutral-bg)] text-[var(--action-neutral-text)] hover:opacity-90 border border-transparent font-medium",
    danger:
      "bg-[var(--action-danger-bg)] text-[var(--action-danger-text)] hover:opacity-90 border border-transparent font-medium",
  };

  const isActuallyDisabled = disabled || isLoading;

  return (
    <button
      ref={ref}
      type="button"
      disabled={isActuallyDisabled}
      className={`inline-flex shrink-0 cursor-pointer items-center justify-center transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 select-none ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <Loader2 className="size-4 animate-spin shrink-0 text-current" />
          <span>{loadingLabel}</span>
        </>
      ) : (
        <>
          {leftIcon && <span className="shrink-0">{leftIcon}</span>}
          <span>{children}</span>
          {rightIcon && <span className="shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  );
}
