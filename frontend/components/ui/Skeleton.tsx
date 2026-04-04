"use client";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div className={`animate-pulse bg-surface-overlay rounded ${className}`} />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-xl p-4 space-y-3">
      <Skeleton className="h-5 w-32" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  );
}
