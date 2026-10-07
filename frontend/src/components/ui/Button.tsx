import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "accent" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-paper hover:bg-ink/85 border border-ink",
  accent: "bg-cyan text-ink hover:bg-cyan-300 border border-cyan",
  secondary: "bg-paper text-ink border border-ink hover:bg-surface",
  ghost: "bg-transparent text-ink border border-transparent hover:bg-surface",
  danger: "bg-red-700 text-white border border-red-700 hover:bg-red-800",
};
const SIZES: Record<Size, string> = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2.5 text-sm" };

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean };

export function Button({ variant = "primary", size = "md", loading, disabled, className = "", children, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
    >
      {loading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />}
      {children}
    </button>
  );
}
