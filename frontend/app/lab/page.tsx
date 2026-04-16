"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import type { Step } from "@/lib/types";
import { Stepper } from "@/components/ui/Stepper";
import { FeatureSelector } from "@/components/features/FeatureSelector";
import { PresetSelector } from "@/components/features/PresetSelector";
import { QuickLearnButton } from "@/components/learning/QuickLearnButton";
import { LearningProgress } from "@/components/learning/LearningProgress";
import { RemainingAttempts } from "@/components/learning/RemainingAttempts";
import { BacktestSummary } from "@/components/results/BacktestSummary";
import { YearlyROIChart } from "@/components/results/YearlyROIChart";
import { ConditionBreakdown } from "@/components/results/ConditionBreakdown";
import { FeatureImportanceChart } from "@/components/results/FeatureImportanceChart";
import { LockPopup } from "@/components/paywall/LockPopup";
import { ProLockSection } from "@/components/paywall/ProLockSection";
import { DemoNoticeBanner } from "@/components/ui/DemoNoticeBanner";
import { Toast } from "@/components/ui/Toast";
import { ColdStartLoader } from "@/components/ui/ColdStartLoader";
import { useFeatureSelection } from "@/hooks/useFeatureSelection";
import { useLearning } from "@/hooks/useLearning";
import { useAttempts } from "@/hooks/useAttempts";
import { sendEvent } from "@/lib/gtm";

/** Reads ?upgraded=true from URL and shows a toast, then strips the param */
function UpgradeChecker({ onUpgraded }: { onUpgraded: () => void }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  useEffect(() => {
    if (searchParams.get("upgraded") === "true") {
      onUpgraded();
      router.replace("/lab", { scroll: false });
    }
  }, [searchParams, onUpgraded, router]);
  return null;
}

export default function LabPage() {
  const [step, setStep] = useState<Step>(1);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);

  const handleUpgraded = useCallback(() => {
    setToast({ message: "Proプランへのアップグレードが完了しました！", type: "success" });
  }, []);

  // Pro status comes from results (server-determined)
  const isPro = false; // Overridden per-result by results.is_pro from backend

  const {
    categories,
    selectedIds,
    isLoading: featuresLoading,
    error: featuresError,
    toggleFeature,
    toggleAll,
    resetDefaults,
    setSelectedIds,
  } = useFeatureSelection();

  const { isLoading: learningLoading, results, error, startLearning } = useLearning();
  const { used, max, remaining, refresh } = useAttempts(isPro);

  // Track actual Pro status from backend results
  const resultIsPro = results?.is_pro ?? false;

  useEffect(() => {
    sendEvent("lab_start");
  }, []);

  const handleLearn = useCallback(async () => {
    if (selectedIds.size < 2) {
      setToast({ message: "2つ以上の特徴量を選択してください", type: "error" });
      return;
    }
    if (remaining <= 0) {
      setToast({ message: "本日の学習回数の上限に達しました", type: "error" });
      return;
    }

    sendEvent("learn_submit", { feature_count: selectedIds.size });
    const result = await startLearning(Array.from(selectedIds));
    refresh();
    if (result.ok) {
      sendEvent("learn_complete", { feature_count: selectedIds.size });
      setStep(3);
    }
  }, [selectedIds, remaining, startLearning, refresh]);

  const handleStepClick = useCallback(
    (newStep: Step) => {
      // Only allow going forward to step 3 if results exist
      if (newStep === 3 && !results) return;
      const prevStep = step;
      setStep(newStep);
      sendEvent("step_transition", {
        from: prevStep,
        to: newStep,
        direction: newStep > prevStep ? "forward" : "backward",
      });
    },
    [results, step]
  );

  const handlePresetApply = useCallback(
    (featureIds: string[]) => {
      setSelectedIds(new Set(featureIds));
      setToast({ message: "プリセットを適用しました", type: "info" });
    },
    [setSelectedIds]
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <Suspense>
        <UpgradeChecker onUpgraded={handleUpgraded} />
      </Suspense>

      {/* Header */}
      <div className="text-center space-y-1">
        <h1 className="font-mincho text-2xl font-bold text-glow-yellow text-accent">
          AI Lab
        </h1>
        <p className="text-sm text-text-secondary">
          特徴量を選んでAIを学習させましょう
        </p>
      </div>

      {/* Stepper */}
      <Stepper currentStep={step} onStepClick={handleStepClick} />

      {/* Content */}
      <AnimatePresence mode="wait">
        {/* Step 1: Feature Selection */}
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
          >
            {featuresLoading ? (
              <ColdStartLoader count={4} />
            ) : featuresError ? (
              <div className="glass-strong p-6 text-center space-y-4">
                <div className="text-3xl">⚠️</div>
                <h3 className="font-mincho text-lg font-bold">
                  特徴量カタログを取得できませんでした
                </h3>
                <p className="text-sm text-text-secondary">
                  {featuresError instanceof Error
                    ? featuresError.message
                    : "サーバーに接続できません。"}
                </p>
                <button
                  onClick={() => window.location.reload()}
                  className="btn-primary px-5 py-2 rounded-lg text-sm cursor-pointer"
                >
                  再読み込み
                </button>
              </div>
            ) : (
              <>
                {/* Preset templates */}
                <div className="mb-4">
                  <PresetSelector onApply={handlePresetApply} />
                </div>

                <FeatureSelector
                  categories={categories}
                  selectedIds={selectedIds}
                  onToggleFeature={(id) => {
                    toggleFeature(id);
                    sendEvent("feature_select", {
                      feature_id: id,
                      action: selectedIds.has(id) ? "deselect" : "select",
                    });
                  }}
                  onToggleAll={toggleAll}
                  onResetDefaults={resetDefaults}
                />
                {/* Spacer for sticky button */}
                <div className="h-20" />

                {/* Sticky bottom CTA */}
                <div className="fixed bottom-0 left-0 right-0 z-40 pointer-events-none">
                  <div className="max-w-4xl mx-auto px-4 pb-4">
                    <div className="glass-strong p-3 flex items-center justify-between pointer-events-auto">
                      <span className="text-sm text-text-secondary hidden sm:inline pl-2">
                        <span className="text-accent font-mono font-bold text-glow-yellow">
                          {selectedIds.size}
                        </span>{" "}
                        個の特徴量を選択中
                      </span>
                      <button
                        onClick={() => {
                          setStep(2);
                          sendEvent("step_transition", {
                            from: 1,
                            to: 2,
                            direction: "forward",
                          });
                        }}
                        disabled={selectedIds.size < 2}
                        className="btn-primary px-6 py-2.5 rounded-lg sm:ml-auto text-sm w-full sm:w-auto"
                      >
                        次へ: 学習設定 →
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </motion.div>
        )}

        {/* Step 2: Learning */}
        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            {/* Summary of selected features */}
            <div className="glass p-4 space-y-3">
              <h3 className="text-sm font-semibold">学習設定</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-text-muted text-xs">選択した特徴量</p>
                  <p
                    className="font-mono text-accent text-lg"
                    style={{
                      filter: "drop-shadow(0 0 10px rgba(245,233,50,0.5))",
                    }}
                  >
                    {selectedIds.size}個
                  </p>
                </div>
                <div>
                  <p className="text-text-muted text-xs">学習データ期間</p>
                  <p className="font-mono text-text-primary text-lg">2年分</p>
                </div>
                <div>
                  <p className="text-text-muted text-xs">プラン</p>
                  <p className="text-text-primary text-lg">Free</p>
                </div>
              </div>
              <button
                onClick={() => setStep(1)}
                className="text-xs text-text-secondary hover:text-accent transition cursor-pointer"
              >
                ← 特徴量を変更する
              </button>
            </div>

            {/* Remaining attempts */}
            <div className="flex justify-center">
              <RemainingAttempts used={used} max={max} isPro={isPro} />
            </div>

            {/* Learn button */}
            <QuickLearnButton
              selectedCount={selectedIds.size}
              isLoading={learningLoading}
              disabled={selectedIds.size < 2 || remaining <= 0}
              remainingAttempts={remaining}
              onClick={handleLearn}
            />

            {/* Progress */}
            <LearningProgress isLoading={learningLoading} />

            {/* Error */}
            {error && (
              <div className="glass-sm p-3 text-sm text-danger border-danger/40">
                {error}
              </div>
            )}
          </motion.div>
        )}

        {/* Step 3: Results */}
        {step === 3 && !results && (
          <motion.div
            key="step3-fallback"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div className="glass-strong p-8 text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <h3 className="font-mincho text-lg font-bold">
                結果を取得できませんでした
              </h3>
              <p className="text-sm text-text-secondary">
                {error ?? "もう一度お試しください"}
              </p>
              <div className="flex justify-center gap-3 pt-2">
                <button
                  onClick={() => setStep(2)}
                  className="btn-primary px-5 py-2 rounded-lg text-sm cursor-pointer"
                >
                  もう一度学習
                </button>
                <button
                  onClick={() => setStep(1)}
                  className="glass-sm px-5 py-2 text-sm text-text-secondary hover:text-accent transition cursor-pointer"
                >
                  特徴量を選び直す
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {step === 3 && results && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {/* DEMO notice banner */}
            <DemoNoticeBanner />

            {/* Summary */}
            {results.summary && <BacktestSummary summary={results.summary} />}

            {/* Charts grid — locked/preview sections based on is_pro */}
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Yearly ROI: show if data exists (preview for Free, full for Pro) */}
              {results.yearly_breakdown && results.yearly_breakdown.length > 0 ? (
                <YearlyROIChart
                  data={results.yearly_breakdown}
                  isBlurred={!resultIsPro}
                />
              ) : (
                <ProLockSection title="年別ROI推移" />
              )}

              {/* Feature importance: show if data exists (preview for Free, full for Pro) */}
              {results.feature_importance &&
              results.feature_importance.length > 0 ? (
                <FeatureImportanceChart
                  data={results.feature_importance}
                  isBlurred={!resultIsPro}
                  categories={categories}
                />
              ) : (
                <ProLockSection title="特徴量重要度 Top10" />
              )}
            </div>

            {/* Condition breakdown: show if data exists (preview for Free, full for Pro) */}
            {results.condition_breakdown &&
            results.condition_breakdown.length > 0 ? (
              <ConditionBreakdown
                data={results.condition_breakdown}
                isBlurred={!resultIsPro}
              />
            ) : (
              <ProLockSection title="馬場条件別パフォーマンス" />
            )}

            {/* Distance breakdown: show if data exists, otherwise lock */}
            {results.distance_breakdown &&
            results.distance_breakdown.length > 0 ? (
              <div className="glass p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">距離別パフォーマンス</h3>
                  {!resultIsPro && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/40">
                      Pro で詳細表示
                    </span>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-text-muted text-xs">
                        <th className="text-left py-2 pr-4">距離</th>
                        <th className="text-right py-2 px-2">購入数</th>
                        <th className="text-right py-2 px-2">的中率</th>
                        <th className="text-right py-2 px-2">回収率</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.distance_breakdown.map((item, i) => (
                        <tr key={i} className="border-b border-white/5">
                          <td className="py-2 pr-4 text-text-primary">
                            {item.distance_category}
                          </td>
                          <td className="text-right py-2 px-2 font-mono text-text-secondary">
                            {item.n_bets}
                          </td>
                          <td
                            className={`text-right py-2 px-2 font-mono ${
                              item.is_blurred ? "blur-overlay" : "text-text-secondary"
                            }`}
                          >
                            {item.hit_rate?.toFixed(1)}%
                          </td>
                          <td
                            className={`text-right py-2 px-2 font-mono ${
                              item.is_blurred ? "blur-overlay" : ""
                            } ${
                              !item.is_blurred && item.roi !== null
                                ? item.roi >= 100
                                  ? "text-success"
                                  : "text-danger"
                                : "text-text-muted"
                            }`}
                          >
                            {item.is_blurred
                              ? "---%"
                              : item.roi !== null
                              ? `${item.roi.toFixed(1)}%`
                              : "---"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <ProLockSection title="距離別パフォーマンス" />
            )}

            {/* Locked features */}
            {results.locked_features && results.locked_features.length > 0 && (
              <LockPopup lockedFeatures={results.locked_features} />
            )}

            {/* Action buttons */}
            <div className="flex justify-center gap-3 pt-2">
              <button
                onClick={() => setStep(1)}
                className="glass-sm px-4 py-2 text-sm text-text-secondary hover:text-accent transition cursor-pointer"
              >
                特徴量を変更して再学習
              </button>
              <button
                onClick={() => setStep(2)}
                className="btn-primary px-4 py-2 rounded-lg text-sm cursor-pointer"
              >
                もう一度学習
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
