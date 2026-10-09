import { Skeleton } from "./ui";

export function PageSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading page…</span>
      <Skeleton className="h-7 w-64" />
      <Skeleton className="mt-2 h-4 w-96 max-w-full" />
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="mt-6 h-64 w-full" />
    </div>
  );
}
