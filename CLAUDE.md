# CLAUDE.md - UmaBuild

## Overview
ノーコード競馬予想AIビルダー。特徴量を選んでクリックするだけでLightGBMモデルを学習・バックテストできる。

## Project Structure
- `frontend/` - Next.js 14 (App Router) + TypeScript + Tailwind CSS + Recharts + TanStack Query + Framer Motion
- `backend/` - FastAPI + Python 3.11+ + LightGBM + pandas
- `backend/routers/` - API route handlers (features, learn, results, stripe)
- `backend/middleware/auth.py` - Supabase JWT auth + subscription check
- `backend/services/` - Business logic (trainer, paywall, feature_catalog)
- `backend/schema/` - Supabase SQL migrations

## Commands

### Dev servers
```bash
cd frontend && npm run dev          # http://localhost:3000
cd backend && python main.py        # http://localhost:8000
```

### Test
```bash
cd backend && python -m pytest -v                # All tests
cd backend && python -m pytest tests/unit/       # Unit only
cd backend && python -m pytest tests/integration/ # Integration only
cd backend && python -m pytest -m "not slow"     # Skip slow
```

### Lint
```bash
cd backend && python -m ruff check .             # Python lint
cd backend && python -m ruff check --fix .       # Auto-fix
cd frontend && npx next lint                     # ESLint
cd frontend && npx tsc --noEmit                  # Type check
```

### Build
```bash
cd frontend && npx next build       # Production build
```

## Auth & Billing (Phase 2)
- **Auth**: Supabase Auth (Email + Google OAuth) → JWT → `backend/middleware/auth.py`
- **Billing**: Stripe Checkout Sessions (月額¥1,480 / 年額¥9,800, 7日間無料トライアル)
- **Subscription check**: JWT decode → Supabase `subscriptions` table → `is_pro` flag
- **Paywall**: Free users see masked preview data; Pro users see full results
- **Rate limit**: Free 5/day, Pro 50/day

## Key APIs
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/features` | optional | Feature catalog (10 categories, 81 features) |
| GET | `/api/features/presets` | optional | 4 preset templates |
| POST | `/api/learn` | optional | Train model (async, returns job_id) |
| GET | `/api/learn/status/{job_id}` | optional | Poll training status |
| GET | `/api/learn/limits` | optional | Daily attempt limits |
| GET | `/api/results/{model_id}` | optional | Results (masked if free) |
| POST | `/api/stripe/checkout` | required | Create Stripe checkout session |
| POST | `/api/stripe/portal` | required | Create Stripe customer portal |
| POST | `/api/stripe/webhook` | — | Stripe webhook (signature verified) |
| GET | `/api/health` | — | Health check |

## Design System
- Dark theme: surface `#0D1117`, accent `#58A6FF`
- Fonts: Shippori Mincho (headings), DM Mono (numbers), Noto Sans JP (body)
- Paywall UI: CSS blur overlay + lock popups + ProBadge

## Code Conventions
- Backend: ruff (line-length=120, py311, select E/F/W/I)
- Frontend: ESLint next/core-web-vitals + next/typescript
- API responses: snake_case JSON
- FastAPI dependencies: `get_optional_user()` / `get_required_user()` for auth

## Subagents
コンテキスト汚染を防ぎトークンを節約するため、以下のサブエージェントを自律的に活用すること:
- **code-investigator** — コード調査・依存分析・影響範囲調査。変更前の事前調査に使う
- **test-runner** — コード変更後のテスト・lint・ビルド実行。実装完了時に自動で使う
- **pr-reviewer** — PR レビュー。セキュリティ・バグ・ロジックの問題を報告
- **frontend-builder** — フロントエンド実装。デザインシステム内蔵で色・フォント等を自動適用

## Environment Variables
See `backend/.env.example` and `frontend/.env.example` for required vars.
Key: `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
