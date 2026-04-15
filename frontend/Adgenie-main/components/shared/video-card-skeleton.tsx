export function VideoCardSkeleton() {
  return (
    <div className="overflow-hidden border border-[var(--border)] bg-[var(--surface)]">
      <div className="aspect-video animate-pulse bg-[var(--secondary)]/65" />
      <div className="space-y-3 p-4">
        <div className="h-4 w-2/3 animate-pulse bg-[var(--secondary)]/80" />
        <div className="h-3 w-1/2 animate-pulse bg-[var(--secondary)]/80" />
      </div>
    </div>
  );
}
