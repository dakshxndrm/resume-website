"use client";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const styles: Record<Variant, string> = {
  primary:
    "bg-primary text-white hover:-translate-y-px hover:shadow-md active:translate-y-0 disabled:bg-neutral/40",
  ghost:
    "border border-neutral/30 text-secondary hover:border-primary hover:text-primary disabled:text-neutral/50",
  danger: "bg-error text-white hover:-translate-y-px hover:shadow-md disabled:bg-neutral/40",
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", loading, className = "", children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`focus-ring inline-flex items-center justify-center gap-2 rounded-btn px-5 py-2.5 text-sm font-semibold transition-all duration-150 ease-out disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
);
Button.displayName = "Button";
