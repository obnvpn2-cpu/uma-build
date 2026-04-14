"""Feature catalog for UmaBuild.

Defines 10 categories of features that users can select via the UI.
Each feature maps to computed columns in the feature_table.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature Catalog - 8 categories
# ---------------------------------------------------------------------------

FEATURE_CATALOG: List[Dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # 1. レース条件 (Race Condition)
    # -----------------------------------------------------------------------
    {
        "id": "race_condition",
        "name": "レース条件",
        "description": "距離・馬場・コース・グレード・枠順など",
        "icon": "🏁",
        "features": [
            {"id": "distance", "label": "距離", "description": "レースの距離（m）", "default_on": True},
            {"id": "surface", "label": "馬場種別", "description": "芝 / ダート", "default_on": True},
            {"id": "track_condition", "label": "馬場状態", "description": "良・稍重・重・不良", "default_on": True},
            {"id": "grade", "label": "グレード", "description": "G1/G2/G3/OP/条件戦", "default_on": False},
            {"id": "race_class", "label": "クラス", "description": "レースのクラス区分", "default_on": False},
            {"id": "field_size", "label": "出走頭数", "description": "そのレースの出走頭数", "default_on": True},
            {"id": "waku", "label": "枠番", "description": "枠番（1〜8）", "default_on": True},
            {"id": "umaban", "label": "馬番", "description": "馬番", "default_on": True},
            {"id": "course_id", "label": "競馬場", "description": "中山・東京・阪神・京都 等", "default_on": False},
            {"id": "sex", "label": "性別", "description": "牡・牝・セン", "default_on": False},
            {"id": "age", "label": "馬齢", "description": "出走時の馬齢", "default_on": True},
            {"id": "weight_carried", "label": "斤量", "description": "負担重量（kg）", "default_on": True},
        ],
    },
    # -----------------------------------------------------------------------
    # 2. 馬の実績 (Horse Form)
    # -----------------------------------------------------------------------
    {
        "id": "horse_form",
        "name": "馬の実績",
        "description": "勝率・連対率・近走成績などの馬の過去実績",
        "icon": "🐴",
        "features": [
            {"id": "horse_n_starts", "label": "出走数", "description": "過去の総出走回数", "default_on": True},
            {"id": "horse_n_wins", "label": "勝利数", "description": "過去の総勝利数", "default_on": False},
            {"id": "horse_win_rate", "label": "勝率", "description": "過去全レースの勝率", "default_on": True},
            {"id": "horse_in3_rate", "label": "複勝率", "description": "3着以内率", "default_on": True},
            {"id": "horse_avg_finish", "label": "平均着順", "description": "過去レースの平均着順", "default_on": True},
            {"id": "horse_dist_win_rate", "label": "同距離勝率", "description": "同距離カテゴリでの勝率", "default_on": True},
            {"id": "horse_dist_in3_rate", "label": "同距離複勝率", "description": "同距離カテゴリでの複勝率", "default_on": False},
            {"id": "horse_surface_win_rate", "label": "同馬場勝率", "description": "同じ馬場種別での勝率", "default_on": True},
            {"id": "horse_surface_in3_rate", "label": "同馬場複勝率", "description": "同じ馬場種別での複勝率", "default_on": False},
            {"id": "horse_course_win_rate", "label": "同コース勝率", "description": "同じ競馬場での勝率", "default_on": False},
            {"id": "horse_recent3_avg", "label": "近3走平均着順", "description": "直近3走の平均着順", "default_on": True},
            {"id": "horse_recent5_avg", "label": "近5走平均着順", "description": "直近5走の平均着順", "default_on": False},
            {"id": "horse_recent3_win_rate", "label": "近3走勝率", "description": "直近3走の勝率", "default_on": False},
            {"id": "horse_days_since_last", "label": "休養日数", "description": "前走からの日数", "default_on": True},
            {"id": "horse_last_finish", "label": "前走着順", "description": "前走の着順", "default_on": True},
        ],
    },
    # -----------------------------------------------------------------------
    # 3. 体重 (Weight)
    # -----------------------------------------------------------------------
    {
        "id": "weight",
        "name": "体重",
        "description": "馬体重・増減・トレンド",
        "icon": "⚖️",
        "features": [
            {"id": "body_weight", "label": "馬体重", "description": "当日の馬体重（kg）", "default_on": True},
            {"id": "weight_diff", "label": "体重増減", "description": "前走からの体重変化（kg）", "default_on": True},
            {"id": "horse_avg_weight", "label": "平均体重", "description": "過去レースの平均馬体重", "default_on": False},
            {"id": "weight_dev_from_avg", "label": "平均体重偏差", "description": "平均体重からの乖離", "default_on": False},
            {"id": "weight_trend_3", "label": "体重トレンド(3走)", "description": "直近3走の体重変化傾向", "default_on": False},
            {"id": "abs_weight_diff", "label": "体重変化絶対値", "description": "体重増減の絶対値", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 4. ペース・位置取り (Pace & Position)
    # -----------------------------------------------------------------------
    {
        "id": "pace_position",
        "name": "ペース・位置取り",
        "description": "コーナー通過順位・上がり3F・位置取り変化・脚質",
        "icon": "📊",
        "features": [
            {"id": "horse_avg_corner3", "label": "平均3角位置", "description": "過去レースの平均3コーナー通過順位", "default_on": False},
            {"id": "horse_avg_corner4", "label": "平均4角位置", "description": "過去レースの平均4コーナー通過順位", "default_on": True},
            {"id": "horse_avg_last3f", "label": "平均上がり3F", "description": "過去レースの平均上がり3Fタイム", "default_on": True},
            {"id": "horse_best_last3f", "label": "ベスト上がり3F", "description": "過去最高の上がり3Fタイム", "default_on": False},
            {"id": "horse_avg_position_change", "label": "平均位置変化", "description": "3角→ゴールの平均順位変動", "default_on": False},
            {"id": "horse_running_style", "label": "脚質", "description": "逃げ/先行/差し/追込の脚質分類", "default_on": True},
            {"id": "horse_last3f_rank_avg", "label": "上がり3F順位平均", "description": "上がり3Fの平均レース内順位", "default_on": False},
            {"id": "horse_recent3_last3f", "label": "近3走上がり3F平均", "description": "直近3走の上がり3F平均", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 5. クラス・賞金 (Class & Prize)
    # -----------------------------------------------------------------------
    {
        "id": "class_prize",
        "name": "クラス・賞金",
        "description": "獲得賞金・クラス変遷・重賞実績",
        "icon": "🏆",
        "features": [
            {"id": "horse_total_prize", "label": "総賞金", "description": "過去の獲得賞金合計", "default_on": True},
            {"id": "horse_avg_prize", "label": "平均賞金", "description": "1走あたりの平均獲得賞金", "default_on": False},
            {"id": "horse_max_grade", "label": "最高グレード", "description": "出走した最高グレードのレース", "default_on": False},
            {"id": "horse_grade_n_starts", "label": "重賞出走数", "description": "重賞レースへの出走回数", "default_on": False},
            {"id": "horse_grade_win_rate", "label": "重賞勝率", "description": "重賞レースでの勝率", "default_on": False},
            {"id": "horse_class_change", "label": "クラス変化", "description": "前走からのクラス変動（昇級/降級/同級）", "default_on": True},
            {"id": "horse_prize_rank_in_field", "label": "賞金順位", "description": "出走メンバー内での賞金順位", "default_on": False},
            {"id": "horse_earnings_per_start", "label": "出走あたり賞金効率", "description": "出走回数あたりの賞金効率", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 6. 騎手 (Jockey)
    # -----------------------------------------------------------------------
    {
        "id": "jockey",
        "name": "騎手",
        "description": "騎手の勝率・距離適性・馬との相性",
        "icon": "🏇",
        "features": [
            {"id": "jockey_win_rate", "label": "騎手勝率", "description": "騎手の過去勝率", "default_on": True},
            {"id": "jockey_in3_rate", "label": "騎手複勝率", "description": "騎手の過去複勝率", "default_on": False},
            {"id": "jockey_dist_win_rate", "label": "騎手同距離勝率", "description": "同距離カテゴリでの騎手勝率", "default_on": False},
            {"id": "jockey_surface_win_rate", "label": "騎手同馬場勝率", "description": "同馬場種別での騎手勝率", "default_on": False},
            {"id": "jockey_recent20_win_rate", "label": "騎手近20走勝率", "description": "騎手の直近20騎乗の勝率", "default_on": True},
            {"id": "jockey_course_win_rate", "label": "騎手同コース勝率", "description": "同じ競馬場での騎手勝率", "default_on": False},
            {"id": "jockey_horse_combo_n", "label": "騎手馬コンビ回数", "description": "同じ馬との騎乗回数", "default_on": False},
            {"id": "jockey_horse_combo_win_rate", "label": "騎手馬コンビ勝率", "description": "同じ馬とのコンビ勝率", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 7. 調教師 (Trainer)
    # -----------------------------------------------------------------------
    {
        "id": "trainer",
        "name": "調教師",
        "description": "調教師の勝率・距離適性・馬との相性",
        "icon": "👨‍🏫",
        "features": [
            {"id": "trainer_win_rate", "label": "調教師勝率", "description": "調教師の過去勝率", "default_on": True},
            {"id": "trainer_in3_rate", "label": "調教師複勝率", "description": "調教師の過去複勝率", "default_on": False},
            {"id": "trainer_dist_win_rate", "label": "調教師同距離勝率", "description": "同距離カテゴリでの調教師勝率", "default_on": False},
            {"id": "trainer_surface_win_rate", "label": "調教師同馬場勝率", "description": "同馬場種別での調教師勝率", "default_on": False},
            {"id": "trainer_recent20_win_rate", "label": "調教師近20走勝率", "description": "調教師の直近20管理馬の勝率", "default_on": True},
            {"id": "trainer_course_win_rate", "label": "調教師同コース勝率", "description": "同じ競馬場での調教師勝率", "default_on": False},
            {"id": "trainer_horse_combo_n", "label": "調教師馬コンビ回数", "description": "同じ馬の管理回数", "default_on": False},
            {"id": "trainer_horse_combo_win_rate", "label": "調教師馬コンビ勝率", "description": "同じ馬の管理勝率", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 8. 調教 (Training)
    # -----------------------------------------------------------------------
    {
        "id": "training",
        "name": "調教",
        "description": "坂路・ウッドチップ調教の直近タイム・加速率・頻度",
        "icon": "🏋️",
        "features": [
            {"id": "train_days_since_last", "label": "調教間隔", "description": "最終調教からレースまでの日数", "default_on": True},
            {"id": "train_last_hanro_time", "label": "坂路タイム", "description": "直近の坂路4Fタイム", "default_on": False},
            {"id": "train_last_hanro_finish", "label": "坂路ラスト1F", "description": "直近の坂路ラスト1Fタイム", "default_on": True},
            {"id": "train_hanro_accel", "label": "坂路加速率", "description": "ラスト1F÷平均1F。1.0未満=終い加速", "default_on": True},
            {"id": "train_best_hanro_time_30d", "label": "坂路30日ベスト", "description": "レース前30日間の坂路最速タイム", "default_on": False},
            {"id": "train_wood_avg_pace", "label": "ウッド平均ペース", "description": "直近ウッドの1Fあたり平均ペース", "default_on": False},
            {"id": "train_total_count_30d", "label": "調教30日回数", "description": "レース前30日間の調教合計回数", "default_on": True},
            {"id": "train_hanro_ratio", "label": "坂路割合", "description": "坂路回数÷合計回数（調教スタイル）", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 9. オッズ・人気 (Odds & Popularity)
    # -----------------------------------------------------------------------
    {
        "id": "odds_popularity",
        "name": "オッズ・人気",
        "description": "単勝オッズ・人気順位・複勝オッズ（発走前の市場評価）",
        "icon": "📈",
        "features": [
            {"id": "win_odds", "label": "単勝オッズ", "description": "単勝オッズ（確定）", "default_on": False},
            {"id": "popularity", "label": "人気順位", "description": "単勝人気順位（1=1番人気）", "default_on": False},
            {"id": "fuku_odds_low", "label": "複勝オッズ下限", "description": "複勝オッズの下限値", "default_on": False},
            {"id": "fuku_odds_high", "label": "複勝オッズ上限", "description": "複勝オッズの上限値", "default_on": False},
            {"id": "fuku_odds_range", "label": "複勝オッズ幅", "description": "3着以内の不確実性指標（上限-下限）", "default_on": False},
        ],
    },
    # -----------------------------------------------------------------------
    # 10. 血統 (Pedigree)
    # -----------------------------------------------------------------------
    {
        "id": "pedigree",
        "name": "血統",
        "description": "父系統・母父系統・血統ハッシュ",
        "icon": "🧬",
        "features": [
            {"id": "sire_group", "label": "父系統", "description": "父の系統グループ（サンデーサイレンス系等）", "default_on": True},
            {"id": "damsire_group", "label": "母父系統", "description": "母父の系統グループ", "default_on": True},
            {"id": "sire_id", "label": "父ID", "description": "父馬のID（カテゴリ特徴量）", "default_on": False},
            {"id": "damsire_id", "label": "母父ID", "description": "母父のID（カテゴリ特徴量）", "default_on": False},
            {"id": "pedigree_hash", "label": "血統ハッシュ", "description": "父×母父の組み合わせハッシュ", "default_on": False},
        ],
    },
]


# ---------------------------------------------------------------------------
# Feature ID -> Column Name Mapping
#
# This maps each UI feature ID to the actual column name(s) in the
# feature_table. Most features map 1:1 but some may expand to multiple
# columns (e.g., one-hot encoded categoricals).
# ---------------------------------------------------------------------------

_FEATURE_ID_TO_COLUMNS: Dict[str, List[str]] = {
    # Race condition
    "distance": ["distance"],
    "surface": ["surface"],
    "track_condition": ["track_condition"],
    "grade": ["grade"],
    "race_class": ["race_class"],
    "field_size": ["field_size"],
    "waku": ["waku"],
    "umaban": ["umaban"],
    "course_id": ["course_id"],
    "sex": ["sex"],
    "age": ["age"],
    "weight_carried": ["weight_carried"],
    # Horse form
    "horse_n_starts": ["horse_n_starts"],
    "horse_n_wins": ["horse_n_wins"],
    "horse_win_rate": ["horse_win_rate"],
    "horse_in3_rate": ["horse_in3_rate"],
    "horse_avg_finish": ["horse_avg_finish"],
    "horse_dist_win_rate": ["horse_dist_win_rate"],
    "horse_dist_in3_rate": ["horse_dist_in3_rate"],
    "horse_surface_win_rate": ["horse_surface_win_rate"],
    "horse_surface_in3_rate": ["horse_surface_in3_rate"],
    "horse_course_win_rate": ["horse_course_win_rate"],
    "horse_recent3_avg": ["horse_recent3_avg"],
    "horse_recent5_avg": ["horse_recent5_avg"],
    "horse_recent3_win_rate": ["horse_recent3_win_rate"],
    "horse_days_since_last": ["horse_days_since_last"],
    "horse_last_finish": ["horse_last_finish"],
    # Weight
    "body_weight": ["body_weight"],
    "weight_diff": ["weight_diff"],
    "horse_avg_weight": ["horse_avg_weight"],
    "weight_dev_from_avg": ["weight_dev_from_avg"],
    "weight_trend_3": ["weight_trend_3"],
    "abs_weight_diff": ["abs_weight_diff"],
    # Pace & position
    "horse_avg_corner3": ["horse_avg_corner3"],
    "horse_avg_corner4": ["horse_avg_corner4"],
    "horse_avg_last3f": ["horse_avg_last3f"],
    "horse_best_last3f": ["horse_best_last3f"],
    "horse_avg_position_change": ["horse_avg_position_change"],
    "horse_running_style": ["horse_running_style"],
    "horse_last3f_rank_avg": ["horse_last3f_rank_avg"],
    "horse_recent3_last3f": ["horse_recent3_last3f"],
    # Class & prize
    "horse_total_prize": ["horse_total_prize"],
    "horse_avg_prize": ["horse_avg_prize"],
    "horse_max_grade": ["horse_max_grade"],
    "horse_grade_n_starts": ["horse_grade_n_starts"],
    "horse_grade_win_rate": ["horse_grade_win_rate"],
    "horse_class_change": ["horse_class_change"],
    "horse_prize_rank_in_field": ["horse_prize_rank_in_field"],
    "horse_earnings_per_start": ["horse_earnings_per_start"],
    # Jockey
    "jockey_win_rate": ["jockey_win_rate"],
    "jockey_in3_rate": ["jockey_in3_rate"],
    "jockey_dist_win_rate": ["jockey_dist_win_rate"],
    "jockey_surface_win_rate": ["jockey_surface_win_rate"],
    "jockey_recent20_win_rate": ["jockey_recent20_win_rate"],
    "jockey_course_win_rate": ["jockey_course_win_rate"],
    "jockey_horse_combo_n": ["jockey_horse_combo_n"],
    "jockey_horse_combo_win_rate": ["jockey_horse_combo_win_rate"],
    # Trainer
    "trainer_win_rate": ["trainer_win_rate"],
    "trainer_in3_rate": ["trainer_in3_rate"],
    "trainer_dist_win_rate": ["trainer_dist_win_rate"],
    "trainer_surface_win_rate": ["trainer_surface_win_rate"],
    "trainer_recent20_win_rate": ["trainer_recent20_win_rate"],
    "trainer_course_win_rate": ["trainer_course_win_rate"],
    "trainer_horse_combo_n": ["trainer_horse_combo_n"],
    "trainer_horse_combo_win_rate": ["trainer_horse_combo_win_rate"],
    # Training
    "train_days_since_last": ["train_days_since_last"],
    "train_last_hanro_time": ["train_last_hanro_time"],
    "train_last_hanro_finish": ["train_last_hanro_finish"],
    "train_hanro_accel": ["train_hanro_accel"],
    "train_best_hanro_time_30d": ["train_best_hanro_time_30d"],
    "train_wood_avg_pace": ["train_wood_avg_pace"],
    "train_total_count_30d": ["train_total_count_30d"],
    "train_hanro_ratio": ["train_hanro_ratio"],
    # Odds & popularity
    "win_odds": ["win_odds"],
    "popularity": ["popularity"],
    "fuku_odds_low": ["fuku_odds_low"],
    "fuku_odds_high": ["fuku_odds_high"],
    "fuku_odds_range": ["fuku_odds_range"],
    # Pedigree
    "sire_group": ["sire_group"],
    "damsire_group": ["damsire_group"],
    "sire_id": ["sire_id"],
    "damsire_id": ["damsire_id"],
    "pedigree_hash": ["pedigree_hash"],
}


def get_catalog() -> List[Dict[str, Any]]:
    """Return the full feature catalog for the frontend."""
    return FEATURE_CATALOG


def get_feature_columns(selected_feature_ids: List[str]) -> List[str]:
    """Map UI feature IDs to actual DB / feature_table column names.

    Args:
        selected_feature_ids: List of feature IDs selected by the user.

    Returns:
        De-duplicated list of column names in the feature_table.
    """
    columns: List[str] = []
    seen: set = set()
    for fid in selected_feature_ids:
        col_list = _FEATURE_ID_TO_COLUMNS.get(fid)
        if col_list is None:
            logger.warning("Unknown feature ID: %s – skipping", fid)
            continue
        for col in col_list:
            if col not in seen:
                columns.append(col)
                seen.add(col)
    return columns


def get_all_feature_ids() -> List[str]:
    """Return a flat list of all feature IDs across all categories."""
    ids: List[str] = []
    for cat in FEATURE_CATALOG:
        for feat in cat["features"]:
            ids.append(feat["id"])
    return ids


def get_default_feature_ids() -> List[str]:
    """Return feature IDs that are enabled by default."""
    ids: List[str] = []
    for cat in FEATURE_CATALOG:
        for feat in cat["features"]:
            if feat.get("default_on", False):
                ids.append(feat["id"])
    return ids
