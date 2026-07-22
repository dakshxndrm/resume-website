import type { HTMLAttributes } from "react";

export function Section({ className = "", alt = false, ...rest }: HTMLAttributes<HTMLElement> & { alt?: boolean }) {
  return <section className={`${alt ? "bg-surface" : ""} py-16 md:py-24 ${className}`} {...rest} />;
}

export function Container({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`mx-auto w-full max-w-container px-6 ${className}`} {...rest} />;
}
