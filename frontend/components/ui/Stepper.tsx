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
                    ? "linear-gradient(135deg, #FFF373 0%, #F5E932 50%, #E0D020 100%)"
                    : isComplete
                    ? "rgba(245,233,50,0.15)"
                    : "rgba(255,255,255,0.04)",
                  color: isActive
                    ? "#0A0A0F"
                    : isComplete
                    ? "#F5E932"
                    : "#6E6E78",
                  border: isActive
                    ? "1px solid rgba(245,233,50,0.6)"
                    : isComplete
                    ? "1px solid rgba(245,233,50,0.4)"
                    : "1px solid rgba(255,255,255,0.1)",
                  boxShadow: isActive
                    ? "0 0 24px rgba(245,233,50,0.55), inset 0 1px 0 rgba(255,255,255,0.4)"
                    : "none",
                  backdropFilter: !isActive ? "blur(10px)" : undefined,
                  WebkitBackdropFilter: !isActive ? "blur(10px)" : undefined,
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
                          ? "rgba(245,233,50,0.5)"
                          : "rgba(255,255,255,0.1)",
                      boxShadow:
                        step < currentStep
                          ? "0 0 8px rgba(245,233,50,0.3)"
                          : "none",
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
