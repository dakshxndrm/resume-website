import type { HTMLAttributes } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-card border border-neutral/15 bg-white p-6 shadow-sm transition-shadow duration-200 hover:shadow-md ${className}`}
      {...rest}
    />
  );
}
