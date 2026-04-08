export function SkeletonCard() {
  return (
    <div className="bg-card rounded-lg p-4 border-l-4 border-l-primary/30 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className="h-5 w-24 bg-muted rounded skeleton-pulse" />
          <div className="h-4 w-12 bg-muted rounded skeleton-pulse" />
        </div>
        <div className="w-7 h-7 rounded-full bg-muted skeleton-pulse" />
      </div>

      <div className="space-y-2 mb-3">
        <div className="h-4 w-full bg-muted rounded skeleton-pulse" />
        <div className="h-4 w-5/6 bg-muted rounded skeleton-pulse" />
        <div className="h-4 w-4/6 bg-muted rounded skeleton-pulse" />
      </div>

      <div className="flex items-center gap-2">
        <div className="w-16 h-1.5 bg-muted rounded skeleton-pulse" />
        <div className="h-3 w-16 bg-muted rounded skeleton-pulse" />
      </div>
    </div>
  );
}
