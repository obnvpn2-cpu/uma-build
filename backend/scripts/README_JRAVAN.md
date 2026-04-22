# JRA-VAN DataLab EveryDB2 セットアップ手順

UmaBuildバックエンドで実データを使用するための、EveryDB2セットアップ手順です。

## 前提条件

- JRA-VAN DataLab会員であること
- Windows 8.1 / 10 / 11
- .NET Framework 4.8
- VC++ 再頒布可能パッケージ

## 1. JVLINKインストール

1. https://jra-van.jp/dlb/ から **JVLINK** をダウンロード・インストール
2. DataLab会員IDでログイン

## 2. EveryDB2インストール

1. https://jra-van.jp/dlb/sft/lib/everydb.html からダウンロード
2. `setup.exe` を実行（VC++ランタイムも自動インストールされます）

## 3. SQLite接続設定

1. EveryDB2を起動
2. データベースの種類で **「SQLite」** を選択
3. ファイルパスに `jravan.db` のフルパスを入力
   ```
   C:\Users\<ユーザー名>\デスクトップ\repo\uma-build\backend\data\jravan.db
   ```
4. **「接続確認(K)」** をクリック → 「接続に成功しました」を確認
5. **「テーブル作成」** をクリック → テーブルが自動生成されます

## 4. 更新データ種別の設定

「更新設定(D)」を開き、以下のデータ種別をチェック：

| データ種別 | テーブル | 用途 |
|---|---|---|
| **RA** (レース詳細) | `N_RACE` | レース基本情報 |
| **SE** (馬毎レース情報) | `N_UMA_RACE` | 出走馬の成績 |
| **UM** (競走馬マスタ) | `N_UMA` | 血統情報 |

「セットアップデータ」を選択（初回は過去データを一括取得します）。

## 5. データ蓄積実行

1. **「更新処理(R)」** → **「取得の開始(O)」**
2. セットアップデータの取得が始まります（初回は数十分〜数時間かかる場合があります）
3. 完了後、`jravan.db` に N_RACE, N_UMA_RACE, N_UMA テーブルが蓄積されます

## 6. 後処理スクリプト実行

EveryDB2が出力したSQLiteデータを、UmaBuildバックエンドが読める形式に変換します。

```bash
cd uma-build/backend
python scripts/postprocess_everydb2.py
```

このスクリプトが行う処理：
- `RaceKey` カラムの合成（複合キーから単一キーへ）
- `RaceDate` カラムの合成（時系列ソート用）
- 血統情報の結合（N_UMA → N_UMA_RACE）
- インデックス作成
- `feature_table_cache.parquet` の生成（5年出力 + 履歴バッファ5年ロード）

> **本番デプロイ時の注意**: `backend/data/feature_table_cache.parquet` は **git commit 必須**。
> 本番 (Render) は DB を持たないため、キャッシュが無いと POST /learn が 503 を返す。
> `.gitignore` でホワイトリスト済み (`!data/feature_table_cache.parquet`)。

## 7. 動作確認

```bash
# レコード数を確認
sqlite3 data/jravan.db "SELECT COUNT(*) FROM N_RACE;"

# バックエンド起動
python main.py

# ログに "Building feature table from DB" が表示されることを確認
```

## 8. 定期更新

レースデータを最新に保つには：

1. EveryDB2で **「更新処理(R)」** → **「取得の開始(O)」** を実行
2. 後処理スクリプトを再実行：
   ```bash
   python scripts/postprocess_everydb2.py
   ```

## 9. 未来予測 (Pro限定) を有効にする運用

未来予測機能は `N_RACE` / `N_UMA_RACE` に **今週分の未開催レース (出馬表)** が入っていることを前提にしています。JRA-VAN の「**今週データ種別 B**」(JVOpen=2) を毎週取り込んでください。

### 毎週の運用フロー (目安)

| 曜日 / 時刻 | 操作 | 内容 |
|---|---|---|
| 木 20:00 以降 | EveryDB2「更新処理」 | 出走馬名表時点のレース情報が届く |
| 金 午前中まで | EveryDB2 を再実行 | 出馬表 (枠番確定) が届く |
| 金〜土 | `bash scripts/weekly_etl.sh` | RaceKey / RaceDate / 調教集約 を付与 (Git Bash / WSL 前提) |
| 土 15:00 以降 | EveryDB2 再実行 | レース確定 → `KakuteiJyuni` が埋まり未来予測対象から自動除外 |

### 更新データ種別の設定

「更新設定(D)」で以下もチェック:

| データ種別 | JVOpen | 用途 |
|---|---|---|
| **B.今週データ** | 2 | 今週土日分の N_RACE / N_UMA_RACE (出馬表) |
| **RCVN** (レース情報補てん) | — | 出走予定馬の過去走マスタを補充 |

※ 「A.通常データ」(=1) のみだと確定済みレースしか入ってこず、未来予測は動きません。

### 動作モード切替

`FUTURE_PREDICTION_MODE` 環境変数で挙動を変えられます:

| 値 | 挙動 |
|---|---|
| `real` (既定) | `N_RACE` から今週の未確定レースを引いて推論。無ければ `[]` を返し warning ログ |
| `demo` | 合成データで推論。テスト・開発用 |
| `auto` | 実データがあれば `real`、無ければ `demo` にフォールバック |

### 確認コマンド

```bash
cd backend
# 今週の未確定レース件数
sqlite3 data/jravan.db "SELECT COUNT(*) FROM N_RACE WHERE RaceDate >= date('now') AND RaceDate <= date('now', '+7 days')"

# 特徴量カバレッジのログを詳細に出す
FUTURE_PREDICTION_DEBUG=1 python -c \
  "from services.future_prediction import generate_future_predictions; \
   print(generate_future_predictions('<model.pkl>', [], 'data/jravan.db')['meta'])"
```

## トラブルシューティング

### jravan.db が見つからない
→ EveryDB2のファイルパス設定を確認してください。`data/` ディレクトリ内に出力されている必要があります。

### テーブルが空
→ EveryDB2の「更新処理」でセットアップデータの取得が完了しているか確認してください。

### 後処理スクリプトでエラー
→ `N_RACE`, `N_UMA_RACE` テーブルが存在し、データが入っているか確認してください：
```bash
sqlite3 data/jravan.db ".tables"
sqlite3 data/jravan.db "SELECT COUNT(*) FROM N_RACE;"
sqlite3 data/jravan.db "SELECT COUNT(*) FROM N_UMA_RACE;"
```
