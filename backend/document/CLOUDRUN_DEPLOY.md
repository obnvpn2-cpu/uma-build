# Cloud Run デプロイ手順

`backend/` を **Google Cloud Run** (asia-northeast1) に載せるためのワン
タイム・セットアップと、それ以降の自動デプロイ運用。リソース構成と
予算アラートは `CLOUDRUN_BUDGET.md` 参照。

> 一度きりの手作業 (§1〜§5) が完了すれば、以降は `main` への push で
> 自動デプロイされる。

---

## §1. GCP プロジェクトと API 有効化

```bash
# 既に "My First Project" を作っているなら、見やすい名前にリネーム
gcloud projects update <PROJECT_ID> --name "uma-build"

# 必要 API 有効化
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  --project <PROJECT_ID>
```

---

## §2. Secret Manager にシークレット投入

```bash
PROJECT_ID=<your-project-id>

# Supabase
echo -n "<SUPABASE_JWT_SECRET>" \
  | gcloud secrets create SUPABASE_JWT_SECRET --data-file=- --project $PROJECT_ID
echo -n "<SUPABASE_SERVICE_ROLE_KEY>" \
  | gcloud secrets create SUPABASE_SERVICE_ROLE_KEY --data-file=- --project $PROJECT_ID

# Stripe
echo -n "<STRIPE_SECRET_KEY>" \
  | gcloud secrets create STRIPE_SECRET_KEY --data-file=- --project $PROJECT_ID
echo -n "<STRIPE_WEBHOOK_SECRET>" \
  | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=- --project $PROJECT_ID
echo -n "<STRIPE_PRICE_MONTHLY>" \
  | gcloud secrets create STRIPE_PRICE_MONTHLY --data-file=- --project $PROJECT_ID
echo -n "<STRIPE_PRICE_YEARLY>" \
  | gcloud secrets create STRIPE_PRICE_YEARLY --data-file=- --project $PROJECT_ID
```

> `SUPABASE_URL` と `ALLOWED_ORIGINS` は Secret ではなく **平文 env** で
> OK (URL なので秘匿性低い)。`deploy-cloudrun.yml` の
> `--set-env-vars` で渡している。

---

## §3. デプロイ用サービスアカウント + Workload Identity Federation

GitHub Actions から鍵なしで認証するための WIF をセットアップ。

### サービスアカウント作成

```bash
SA_NAME=cloudrun-deployer
SA_EMAIL=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts create $SA_NAME \
  --display-name="Cloud Run deployer for GitHub Actions" \
  --project $PROJECT_ID

# Cloud Run デプロイに必要な最小権限
for role in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/cloudbuild.builds.editor \
  roles/storage.admin \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" --role=$role
done
```

### Workload Identity Pool & Provider

```bash
POOL=github-pool
PROVIDER=github-provider
REPO=obnvpn2-cpu/uma-build  # ← 自分の GitHub リポジトリに置き換え

gcloud iam workload-identity-pools create $POOL \
  --project=$PROJECT_ID --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc $PROVIDER \
  --project=$PROJECT_ID --location=global \
  --workload-identity-pool=$POOL \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="attribute.repository == '$REPO'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# このリポジトリからのみ SA を impersonate できるよう紐付け
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --project=$PROJECT_ID \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$REPO"

# GitHub Secret に貼る provider 名
echo "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"
```

---

## §4. GitHub Secrets / Vars 設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を登録:

| Name | Value | 種別 |
|---|---|---|
| `GCP_PROJECT_ID` | `<your-project-id>` | Secret |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | §3 で出力した `projects/.../providers/github-provider` | Secret |
| `GCP_SERVICE_ACCOUNT` | `cloudrun-deployer@<project>.iam.gserviceaccount.com` | Secret |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | Secret |
| `ALLOWED_ORIGINS` | `https://uma-build.app,https://www.uma-build.app` (Vercel ドメイン) | Secret |

---

## §5. 初回デプロイと健全性チェック

```bash
# ローカルからの一発確認 (お試し)
gcloud run deploy uma-build-api \
  --source backend \
  --region asia-northeast1 \
  --memory 4Gi --cpu 2 --timeout 600 \
  --concurrency 1 --max-instances 5 --min-instances 0 \
  --no-cpu-throttling \
  --allow-unauthenticated \
  --set-env-vars "ENV=production,FUTURE_PREDICTION_MODE=real" \
  --project $PROJECT_ID
```

成功したら出力された URL を控えて:

```bash
# Health check
curl https://uma-build-api-XXXXX-an.a.run.app/api/health
# → {"status":"ok"}

# Features endpoint (キャッシュなしでも返るはず)
curl https://uma-build-api-XXXXX-an.a.run.app/api/features | head -c 200
```

---

## §6. Vercel フロント側の更新

Vercel ダッシュボード → uma-build → Settings → Environment Variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://uma-build-api-XXXXX-an.a.run.app` (Cloud Run の発行 URL) |

> 反映には Vercel 側でデプロイ再トリガーが必要 (`Redeploy` 押下)。

---

## §7. カスタムドメイン (任意)

`api.uma-build.app` で叩きたい場合:

```bash
gcloud run domain-mappings create \
  --service uma-build-api \
  --domain api.uma-build.app \
  --region asia-northeast1 \
  --project $PROJECT_ID
```

DNS に出力された CNAME / A レコードを設定。SSL は GCP が自動取得。

> ただし、**Cloud Run のドメインマッピングは GA リージョン (US/EU)
> でしかサポートされていない場合あり**。asia-northeast1 でエラーが
> 出たら、当面は発行 URL 直打ちで運用 → 後で Cloud Load Balancer
> 経由に切り替え。

---

## §8. 自動デプロイ運用

`.github/workflows/deploy-cloudrun.yml` が、`main` へ `backend/**`
の変更が push されたら自動で Cloud Run に反映する。

- 失敗時は GitHub Actions の **Deploy backend to Cloud Run** ジョブの
  ログを確認
- 直前リビジョンに戻す: `gcloud run services update-traffic uma-build-api --to-revisions <rev>=100`
- リビジョン一覧: `gcloud run revisions list --service uma-build-api --region asia-northeast1`

---

## §9. よくあるエラー

| 症状 | 原因 | 対策 |
|---|---|---|
| `PERMISSION_DENIED: secrets/...` | `secretmanager.secretAccessor` が SA に付いていない | §3 のロール再付与 |
| `Container failed to start. Failed to start and then listen on the port` | uvicorn が `$PORT` で listen していない | Dockerfile の `CMD` を確認 |
| `Memory limit exceeded` | 学習中に 4 GiB を超えた | `CLOUDRUN_BUDGET.md` の見直し、もしくは一時的に `--memory 8Gi` |
| `503 特徴量キャッシュが未生成` | parquet が image に入っていない | `.dockerignore` で `data/` を除外していないか確認 |
| WIF auth が `invalid_grant` | provider の attribute-condition に repo 名がマッチしていない | §3 の `attribute.repository` を再確認 |
