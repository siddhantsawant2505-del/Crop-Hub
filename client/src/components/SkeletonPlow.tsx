export function SkeletonPlow({ className = "" }: { className?: string }) {
  return <div className={`skeleton-plow ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="card-planted p-5 space-y-3">
      <SkeletonPlow className="h-4 w-1/3" />
      <SkeletonPlow className="h-8 w-2/3" />
      <SkeletonPlow className="h-4 w-full" />
      <SkeletonPlow className="h-4 w-4/5" />
    </div>
  );
}
