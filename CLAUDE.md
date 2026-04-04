# CLAUDE.md - UmaBuild

## Overview
ノーコード競馬予想AIビルダー。特徴量を選んでクリックするだけでLightGBMモデルを学習・バックテストできる。

## Project Structure
- `frontend/` - Next.js 14 (App Router) + TypeScript + Tailwind CSS + Recharts + TanStack Query + Framer Motion
- `backend/` - FastAPI + Python 3.11+ + LightGBM + pandas

## Development

### Frontend
```bash
cd frontend
npm run dev  # http://localhost:3000
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py  # http://localhost:8000
```

## Design
- Dark theme (surface: #0D1117, accent: #58A6FF)
- Fonts: Shippori Mincho (headings), DM Mono (numbers), Noto Sans JP (body)
- Paywall: CSS blur + backend dummy data

## Data Source
JRA-VAN DataLab (EveryDB2) → SQLite → feature_table
DEMO_MODE auto-enables when jravan.db is not present.

## Key APIs
- `GET /api/features` - Feature catalog (8 categories)
- `POST /api/learn` - Train model & return results
- `GET /api/results/{model_id}` - Cached results
