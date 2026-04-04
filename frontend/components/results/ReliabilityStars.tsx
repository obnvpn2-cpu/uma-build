"use client";

interface ReliabilityStarsProps {
  stars: number;
  maxStars?: number;
}

export function ReliabilityStars({ stars, maxStars = 5 }: ReliabilityStarsProps) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: maxStars }, (_, i) => (
        <span
          key={i}
          className={`text-lg ${i < stars ? "star-filled" : "star-empty"}`}
        >
          ★
        </span>
      ))}
      <span className="ml-1 text-xs text-text-muted font-mono">
        ({stars}/{maxStars})
      </span>
    </div>
  );
}
