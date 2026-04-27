# Cloud Run リソース試算 & 予算アラート設計

UmaBuild バックエンドを **Google Cloud Run** に載せるにあたり、無料枠を
超えないリソース構成と、超える前に通知を受け取る仕組みを決める。

> 参照値はすべて **2026 年 4 月時点 / 東京リージョン (asia-northeast1)** の
> [Cloud Run 公式料金ページ](https://cloud.google.com/run/pricing) に基づく。
> 数値が変わったら見直すこと。

---

## 1. ジョブの実測前提

| 項目 | 値 | 出典 |
|---|---|---|
| 学習ジョブ 1 件あたりの所要時間 | 30〜60 秒 | f929122 後のキャッシュヒット時実測 |
| 1 件あたりピーク RAM | ~3 GB | LightGBM + pandas + parquet ロード |
| 1 件あたり CPU 使用率 | 4 vCPU 飽和 (LightGBM `n_jobs=-1`) | trainer.py |
| 同時実行ジョブ | 1 / インスタンス | 重い学習を並列させない |
| アイドル時 RAM | ~400 MB | FastAPI + warm parquet キャッシュ |

学習ジョブは **CPU bound + メモリ 3 GB**。これに合わせて Cloud Run の
インスタンス構成を選ぶ。

---

## 2. Cloud Run 無料枠 (永続)

| 項目 | 月次無料枠 | 備考 |
|---|---|---|
| リクエスト数 | 2,000,000 | POST /learn, GET /learn/status, GET /features など |
| vCPU 秒 | 360,000 (= 100 hour) | リクエスト処理中の vCPU 時間 |
| メモリ秒 | 180,000 GiB-s (= 50 GiB-hour) | リクエスト処理中の RAM 時間 |
| ネットワーク (egress) | 1 GB | 北米向け。アジア内は別計算 |

**重要な注意**: 無料枠は **billable container time** にのみ適用される。
- `min-instances=0` + デフォルト設定 → アイドル時 0 課金、リクエスト処理時のみ課金
- `min-instances=1` 以上 → アイドル時間も課金対象（無料枠を秒単位で食う）
- `cpu-always-allocated` → リクエスト外でも CPU 課金（バックグラウンドジョブ向け）

UmaBuild のジョブは **学習リクエスト中に動く** ので `cpu-always-allocated`
は **不要**。POST /learn が 60 秒で 202 を返した後、Thread が走り続ける間も
リクエストは完了扱いになるが、Cloud Run は HTTP コネクションが閉じてから
**コンテナを最大 timeout 秒間 alive に保つ** ため、`--timeout 600`
(10 分) で十分。

---

## 3. 構成候補 × 月間ジョブ数の試算

### 前提
- 1 ジョブ = 60 秒 (worst case)
- リクエスト 1 件 = ジョブ 1 件として概算
- アジア東京リージョン (`asia-northeast1`)

### 各 vCPU/RAM 構成での無料枠ぎりぎりの月間ジョブ数

| 構成 | 1 ジョブ vCPU 秒 | 1 ジョブ メモリ GiB 秒 | vCPU 枯渇 | メモリ枯渇 | **ボトルネック / 上限** |
|---|---:|---:|---:|---:|---|
| **4 vCPU / 8 GiB** | 240 | 480 | 1,500 | 375 | メモリ 375 件/月 |
| **4 vCPU / 16 GiB** | 240 | 960 | 1,500 | 187 | メモリ 187 件/月 |
| **4 vCPU / 32 GiB** | 240 | 1,920 | 1,500 | 93 | メモリ 93 件/月 |
| **2 vCPU / 8 GiB** | 120 | 480 | 3,000 | 375 | メモリ 375 件/月 |
| **2 vCPU / 4 GiB** | 120 | 240 | 3,000 | 750 | **メモリ 750 件/月** |
| **2 vCPU / 3 GiB** | 120 | 180 | 3,000 | 1,000 | **メモリ 1,000 件/月** |
| **1 vCPU / 4 GiB** | 60 | 240 | 6,000 | 750 | メモリ 750 件/月 |
| **1 vCPU / 2 GiB** | 60 | 120 | 6,000 | 1,500 | **vCPU 6,000 件 / メモリ 1,500 件** |

### 考察
- **32 GiB 構成は無料枠と相性が悪い**: メモリ秒の単価が高すぎて月 100 件足らず。実質課金前提
- **メモリ 3 GiB が最大値**: 学習ピーク 3 GB を 1 GB バッファ込みで 4 GiB に抑えれば、月 750 件
- **2 vCPU だと学習時間が伸びる懸念**: LightGBM はコア数線形ではない (~1.6x @ 4→2)。60s が 90〜100s 程度に伸びる
- **推奨: `--memory 4Gi --cpu 2`**: ピーク RAM 3 GB に 1 GB バッファ、メモリ秒消費を抑制、vCPU は 2 でも十分

### 推奨構成

```bash
gcloud run deploy uma-build-api \
  --source . \
  --region asia-northeast1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 1 \
  --max-instances 5 \
  --min-instances 0 \
  --no-cpu-throttling \   # CPU は常に 2 vCPU 確保 (--no-cpu-throttling は学習中の必須)
  --allow-unauthenticated
```

**月間ジョブ数の目安**:
- DAU 50 × 1 ジョブ/日 = **1,500 件/月** → 無料枠超過 (メモリ 750 件)
- DAU 25 × 1 ジョブ/日 = **750 件/月** → 無料枠ぎりぎり
- DAU 20 × 1 ジョブ/日 = **600 件/月** → 余裕

**結論**: **MVP では DAU 20〜25 までは無料枠内**。それを超えたら段階的に
- (a) 学習をキャッシュ化 (同じ feature_set の重複学習を弾く)
- (b) Pro 限定で重い学習に絞る
- (c) Cloud Run Jobs に切り出して billing を別系統にする

---

## 4. 予算アラート設定

### ステップ 1: GCP 予算作成 (ダッシュボード)

1. Console → Billing → Budgets & alerts → CREATE BUDGET
2. **Name**: `uma-build-monthly`
3. **Scope**:
   - Project: `My First Project` (or rename to `uma-build`)
   - Services: All (Cloud Run + その他もまとめて監視)
4. **Amount**:
   - Budget type: Specified amount
   - Target amount: **¥3,000 / 月** (有料に踏み出す前の閾値)
5. **Threshold rules** (3 段階):
   - 50% → メール通知のみ
   - 90% → メール + Pub/Sub
   - 100% → メール + Pub/Sub + 強制シャットダウン (後述)
6. **Pub/Sub topic**: `budget-alerts` を作って結びつけ

### ステップ 2: Pub/Sub → Cloud Functions → Slack/LINE 通知

無料枠 (Pub/Sub 月 10 GB / Cloud Functions 月 200 万実行) で済む。

```
Budget alert
  ↓ Pub/Sub topic: budget-alerts
    ↓ Cloud Functions (Python, gen2)
      ↓ HTTP POST to Slack Webhook URL (or LINE Notify)
```

**Cloud Functions コード**:

```python
# functions/budget_alert/main.py
import base64, json, os, urllib.request

SLACK_WEBHOOK = os.environ["SLACK_WEBHOOK_URL"]

def handle(event, context):
    raw = base64.b64decode(event["data"]).decode()
    msg = json.loads(raw)
    cost = msg.get("costAmount", 0)
    budget = msg.get("budgetAmount", 1)
    pct = int(cost / budget * 100)
    if pct < 50:
        return  # ノイズ抑制
    body = {
        "text": f":warning: GCP 予算 {pct}% 到達: ¥{int(cost):,} / ¥{int(budget):,}"
    }
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=5)
```

> LINE Notify は 2026 年 3 月で終了済み。LINE 通知が必要なら
> Messaging API + LINE Bot 経由になる。**Slack を推奨**。

### ステップ 3: 100% 到達時の強制シャットダウン (任意)

最悪のケースで暴走を防ぐため、100% トリガーで Cloud Run のサービスを
止めるオプション。Slack で確認できなくなるリスクと引き換え:

```python
# 上の handle 関数に追記 (pct >= 100 のとき)
if pct >= 100:
    from googleapiclient.discovery import build
    run = build("run", "v1")
    run.namespaces().services().delete(
        name="namespaces/{PROJECT}/services/uma-build-api"
    ).execute()
```

> **MVP ではここまでやらない**。90% アラート → 手動でトラフィック制限する
> 運用で十分。実装するのは月間 ¥30,000 以上の予算を切ったタイミング。

### ステップ 4: 課金が発生したら見るダッシュボード

- Cloud Run → Service detail → **Metrics** タブ
  - "Container CPU utilization"
  - "Container memory utilization"
  - "Request count" / "Request latency"
- Billing → Reports
  - SKU 別: `Network Egress` / `Memory Allocation Time` / `CPU Allocation Time`

---

## 5. アクションアイテム (次 PR)

- [ ] **Dockerfile** を `backend/Dockerfile` に作成 (Python 3.12 + uvicorn + parquet キャッシュ含む)
- [ ] **GitHub Actions** ワークフローで `gcloud run deploy --source` を回す
- [ ] **Secret Manager** に `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET` / `STRIPE_SECRET_KEY` などを格納
- [ ] **予算 ¥3,000** を作成 + Pub/Sub topic + Cloud Functions + Slack Webhook
- [ ] **初回デプロイ** で `--no-traffic` リビジョンを作って、health check 後に切り替え
- [ ] **DNS**: Vercel の API ドメイン (`api.uma-build.app` など) を Cloud Run の固定 URL に CNAME

---

## 6. 切り戻し計画

Cloud Run で問題が出たら **Render Free に戻す**。手順:

1. Vercel の `NEXT_PUBLIC_API_URL` を Render の URL に戻す
2. Cloud Run のサービスは **削除せず traffic=0** にしておく (履歴保全)
3. Render は OOM 既知だが、UI が落ちるよりはマシ

---

## 7. 仮定・既知の不確実性

- 学習ジョブの所要時間 60 秒は **キャッシュヒット時の値**。`feature_table_cache.parquet` が壊れてビルドし直しになると 6 分超になる。preflight 503 で防御済みだが、cache が再生成されるまで全 POST /learn が落ちる
- LightGBM のスレッド数は OS の CPU 数を見ているため、Cloud Run の `--cpu 2` 設定だと必ず 2 vCPU 飽和になる。3 vCPU 以上は割り当てても加速しない
- Tokyo region の単価は北米より約 18% 高い。コスト試算は **東京基準**
- 無料枠は **billing account 単位**。同じアカウントで他プロジェクトが Cloud Run を使うと食い合う (現時点では他プロジェクトなし)
