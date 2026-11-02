import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-linear-to-r from-brand-500 to-indigo-500 text-white shadow-lg shadow-brand-600/25 hover:from-brand-400 hover:to-indigo-400",
  secondary:
    "border border-ink-600 bg-ink-800 text-ink-100 hover:border-ink-500 hover:bg-ink-700",
  ghost: "text-ink-200 hover:bg-ink-800 hover:text-white",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

// Also used on links, so a link can look like a button.
export function buttonClasses(
  variant: Variant = "primary",
  size: Size = "md",
  extra = "",
): string {
  return [
    "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400",
    "disabled:cursor-not-allowed disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
    extra,
  ].join(" ");
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
};

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  disabled,
  children,
  ...rest
}: Props) {
  return (
    <button
      className={buttonClasses(variant, size, className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}