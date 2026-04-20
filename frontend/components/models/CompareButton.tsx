"use client";

interface CompareButtonProps {
  selectedCount: number;
  onClick: () => void;
  isLoading?: boolean;
}

export function CompareButton({ selectedCount, onClick, isLoading }: CompareButtonProps) {
  const disabled = selectedCount < 2 || isLoading;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 pointer-events-none">
      <div className="max-w-4xl mx-auto px-4 pb-4">
        <div className="glass-strong p-3 flex items-center justify-between pointer-events-auto">
          <span className="text-sm text-text-secondary hidden sm:inline pl-2">
            <span className="text-accent font-mono font-bold text-glow-yellow">
              {selectedCount}
            </span>{" "}
            個のモデルを選択中
          </span>
          <button
            onClick={onClick}
            disabled={disabled}
            className="btn-primary px-6 py-2.5 rounded-lg sm:ml-auto text-sm w-full sm:w-auto"
          >
            {isLoading
              ? "比較中..."
              : selectedCount < 2
              ? "2個以上選択してください"
              : `${selectedCount}個のモデルを比較`}
          </button>
        </div>
      </div>
    </div>
  );
}
