# cron-job.org 設定手順

## 目的

Render Free tier は **15分間アクセスがないとスリープ**し、次回アクセス時のコールドスタートに 50 秒以上かかる。cron-job.org で 5 分ごとに `/api/health` を叩き続けることで、Render を常時 warm 状態に保つ。

これにより、学習ボタン (`/api/learn`) 実行時のコールドスタート待ちを解消する。
特徴量カタログ (`/api/features`) は別途 Vercel Edge でキャッシュ化済みなので、`/lab` ロードは cron-job.org が動いていなくても即座に応答する (二段構え)。

---

## なぜ UptimeRobot ではなく cron-job.org なのか

UptimeRobot 無料枠は検証したが **Render Free では機能しない**:

- 無料枠は HTTP Method が **HEAD 固定**（GET/POST は有料プランのみ）
- Render Free の proxy は HEAD リクエストを正しく処理できず **502 Bad Gateway を返し続ける**
- 3拠点（Ashburn / Dallas / N. Virginia）から確認しても同じ結果

一方 cron-job.org は無料枠で以下が使える:
- **GET/POST/HEAD/PUT/DELETE** メソッド選択可
- **カスタムヘッダ**（User-Agent など）設定可
- **最短 1 分間隔**（本プロジェクトは 5 分で十分）
- タイムアウト 30 秒固定（有料で延長可）

---

## セットアップ手順 (所要 5 分)

### 1. アカウント作成
1. https://cron-job.org にアクセス
2. 「Sign up」からアカウント作成（クレカ不要）
3. メール認証を済ませてログイン

### 2. ジョブ追加
1. ダッシュボードで **「CREATE CRONJOB」** をクリック
2. 以下の設定で作成:

    | 項目 | 値 |
    |---|---|
    | Title | `UmaBuild Render Warm` |
    | URL | `https://uma-build.onrender.com/api/health` |
    | Schedule | `Every 5 minutes` |
    | Time zone | `Asia/Tokyo` |
    | Request method | `GET` |
    | Treat 3xx as success | `ON` |
    | Save responses in job history | `ON`（デバッグしやすくするため推奨）|
    | Enabled | `ON` |

3. **Advanced → Headers** セクションで User-Agent を追加:
    ```
    User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
    ```

4. 「CREATE」をクリック

### 3. テスト実行
1. ジョブ一覧 → 作成したジョブの **Edit** → **TEST RUN** ボタン
2. 「IP が X-Forwarded-For で転送されます」ダイアログ → **START TEST RUN**
3. **200 OK** が返ることを確認

### 4. 動作確認
- ジョブ詳細画面 → **History** タブで 5 分間隔に `200 Success` が並ぶことを確認
- Render ダッシュボード → Logs で 5 分間隔に `GET /api/health` アクセスが記録されていることを確認

---

## 注意事項

### Render Free の月 750 時間制限
- 1 ヶ月の総時間は約 720〜744 時間 (= 24 時間 × 30〜31 日)
- Render Free の無料枠は月 **750 時間**まで
- 24/7 稼働させるとほぼ上限ギリギリで、月末に停止する可能性がある
- **マネタイズ前は当面これで運用**。もし月末停止が観測されたら以下を検討:
  - cron-job.org の interval を 10 分に伸ばす（ただし Render スリープ閾値 15 分を避けるため効果薄）
  - Render Starter ($7/月) に移行して完全に常時稼働化
  - Render の代わりに常時稼働できる別の無料 PaaS へ移行

### `/api/health` エンドポイント
- `backend/main.py:39` に `@app.get("/api/health")` として定義済み
- `{"status":"ok"}` を返すだけのシンプルなエンドポイント
- DB 接続チェックなどを含めると重くなるので、health は軽量に保つ

### アラート通知
- cron-job.org はジョブ失敗時にメール通知可能
- Settings → Notifications で通知の有無・閾値を調整できる

---

## フェイルセーフ構成まとめ

```
[ユーザー] --------> [/lab]
                      │
                      └─> fetchFeatures()
                            │
                            └─> [Vercel Edge Route /api/features]
                                  │
                                  ├─(キャッシュHIT)──> 即時応答 ✅
                                  │
                                  └─(ミス時のみ)────> [Render /api/features]
                                                          ↑
                                                          │
                                                 (cron-job.org が
                                                  5分毎に /api/health
                                                  を叩いてwarm維持)
```

- **一次防衛線**: Vercel Edge Cache (特徴量カタログ)
- **二次防衛線**: cron-job.org による Render の warm 維持
- **三次防衛線**: `ColdStartLoader` による段階的メッセージ表示 (最終フォールバック)

---

## 検証履歴 (2026-04-11)

- cron-job.org ジョブ `UmaBuild Render Warm` 稼働開始
- 11:15〜11:45 の 30 分間で 7 回連続 **200 OK** を確認
- 応答時間: 439ms〜1.41s（warm 維持成功）
- 削除済み: UptimeRobot モニター（HEAD/502 問題により不採用）
