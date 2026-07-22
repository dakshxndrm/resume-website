export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-btn bg-neutral/15 ${className}`} aria-hidden />;
}
