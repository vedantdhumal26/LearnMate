export function SkeletonCard() {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="skeleton h-5 w-2/3" />
          <div className="skeleton h-4 w-full" />
          <div className="skeleton h-4 w-4/5" />
        </div>
        <div className="skeleton h-10 w-10 rounded-lg shrink-0" />
      </div>
      <div className="mt-5 flex items-center gap-4">
        <div className="skeleton h-4 w-20" />
        <div className="skeleton h-4 w-20" />
        <div className="skeleton h-4 w-24" />
      </div>
    </div>
  );
}

export function SkeletonCardGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
