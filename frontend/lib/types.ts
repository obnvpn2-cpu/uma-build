// Feature types
export interface Feature {
  id: string;
  label: string;
  description: string;
  default_on: boolean;
}

export interface FeatureCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  features: Feature[];
}

// API request/response
export interface LearnRequest {
  selected_features: string[];
  session_id?: string;
}

export interface LearnSummary {
  roi: number | null;
  hit_rate: number | null;
  n_bets: number | null;
  n_races: number | null;
  reliability_stars: number | null;
  total_return?: number | null;
  total_bet?: number | null;
  profit?: number | null;
  n_hits?: number | null;
  is_blurred?: boolean;
}

export interface BreakdownItem {
  surface?: string;
  track_condition?: string;
  year?: number;
  distance_category?: string;
  n_bets: number;
  n_hits: number;
  hit_rate: number;
  roi: number | null;
  profit: number | null;
  is_blurred: boolean;
}

export interface FeatureImportanceItem {
  feature: string;
  importance: number | null;
  rank: number;
  is_blurred: boolean;
}

export interface CalibrationItem {
  bin: string;
  predicted_avg: number;
  actual_avg: number | null;
  count: number;
  is_blurred: boolean;
}

export interface LockedFeature {
  id: string;
  name: string;
  description: string;
}

export interface LearnResponse {
  model_id: string | null;
  is_pro: boolean;
  summary: LearnSummary | null;
  feature_importance: FeatureImportanceItem[] | null;
  condition_breakdown: BreakdownItem[] | null;
  yearly_breakdown: BreakdownItem[] | null;
  distance_breakdown: BreakdownItem[] | null;
  calibration: CalibrationItem[] | null;
  meta: Record<string, unknown> | null;
  locked_features: LockedFeature[] | null;
  train_metrics?: Record<string, unknown> | null;
  error?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: "training" | "completed" | "failed";
  result: LearnResponse | null;
  error: string | null;
}

export interface LimitsResponse {
  max_attempts: number;
  used_attempts: number;
  remaining_attempts: number;
  is_pro: boolean;
}

// UI State
export type Step = 1 | 2 | 3;

export interface ModelState {
  modelId: string | null;
  results: LearnResponse | null;
  isLoading: boolean;
  error: string | null;
}
