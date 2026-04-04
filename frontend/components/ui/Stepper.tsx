"use client";

import type { Step } from "@/lib/types";

interface StepperProps {
  currentStep: Step;
  onStepClick: (step: Step) => void;
}

const STEPS = [
  { step: 1 as Step, label: "特徴量を選ぶ" },
  { step: 2 as Step, label: "学習する" },
  { step: 3 as Step, label: "結果を見る" },
];

export function Stepper({ currentStep, onStepClick }: StepperProps) {
  return (
    <div className="w-full max-w-lg mx-auto py-4">
      {/* Circles + connectors row */}
      <div className="flex items-center">
        {STEPS.map(({ step }, i) => {
          const isActive = step === currentStep;
          const isComplete = step < currentStep;
          return (
            <div key={step} className="flex items-center flex-1 last:flex-none">
              <button
                onClick={() => onStepClick(step)}
                className="relative w-9 h-9 rounded-full flex items-center justify-center text-sm font-mono font-bold transition-all shrink-0 cursor-pointer"
                style={{
                  background: isActive
                    ? "#58A6FF"
                    : isComplete
                    ? "rgba(88,166,255,0.15)"
                    : "#1C2128",
                  color: isActive
                    ? "#0D1117"
                    : isComplete
                    ? "#58A6FF"
                    : "#7D8590",
                  border: isActive
                    ? "none"
                    : isComplete
                    ? "1px solid rgba(88,166,255,0.4)"
                    : "1px solid #30363D",
                  boxShadow: isActive
                    ? "0 0 12px rgba(88,166,255,0.35)"
                    : "none",
                }}
              >
                {isComplete ? "\u2713" : step}
              </button>
              {i < STEPS.length - 1 && (
                <div className="flex-1 h-0.5 mx-3">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      background:
                        step < currentStep
                          ? "rgba(88,166,255,0.4)"
                          : "#30363D",
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {/* Labels row */}
      <div className="flex mt-2">
        {STEPS.map(({ step, label }) => {
          const isActive = step === currentStep;
          const isComplete = step < currentStep;
          return (
            <div
              key={step}
              className="flex-1 last:flex-none"
              style={{ minWidth: step === STEPS.length ? "auto" : undefined }}
            >
              <button
                onClick={() => onStepClick(step)}
                className={`text-xs transition cursor-pointer ${
                  isActive
                    ? "text-accent font-semibold"
                    : isComplete
                    ? "text-text-secondary"
                    : "text-text-muted"
                }`}
              >
                {label}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
