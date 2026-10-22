import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingLabel?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
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
  children,
  ...props
}: ButtonProps) {
  const sizeStyles: Record<ButtonSize, string> = {
    sm: "h-9 px-3 text-xs gap-1.5 rounded-md",
    md: "h-11 px-4 text-sm gap-2 rounded-lg",
    lg: "h-12 px-6 text-base gap-2.5 rounded-lg",
  };

  const variantStyles: Record<ButtonVariant, string> = {
    primary:
      "bg-brand text-white hover:bg-[var(--accent-goiaba-hover)] active:opacity-95 shadow-sm border border-transparent font-medium",
    secondary:
      "bg-surface text-content hover:bg-surface-hover border border-control shadow-sm font-medium",
    outline:
      "bg-transparent text-content hover:bg-surface-hover border border-border font-medium",
    ghost:
      "bg-transparent text-muted hover:text-content hover:bg-surface-hover font-normal",
  };

  const isActuallyDisabled = disabled || isLoading;

  return (
    <button
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
