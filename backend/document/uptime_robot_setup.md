# UptimeRobot 設定手順

## 目的

Render Free tier は **15分間アクセスがないとスリープ**し、次回アクセス時のコールドスタートに 50 秒以上かかる。UptimeRobot で 5 分ごとに `/api/health` を叩き続けることで、Render を常時 warm 状態に保つ。

これにより、学習ボタン (`/api/learn`) 実行時のコールドスタート待ちを解消する。
特徴量カタログ (`/api/features`) は別途 Vercel Edge でキャッシュ化済みなので、`/lab` ロードは UptimeRobot が動いていなくても即座に応答する (二段構え)。

---

## セットアップ手順 (所要 5 分)

### 1. アカウント作成
1. https://uptimerobot.com にアクセス
2. 「Register for FREE」からアカウント作成（クレカ不要）
3. メール認証を済ませてログイン

### 2. モニター追加
1. ダッシュボードで **「+ New monitor」** をクリック
2. 以下の設定で作成:

    | 項目 | 値 |
    |---|---|
    | Monitor Type | `HTTP(s)` |
    | Friendly Name | `UmaBuild API Health` |
    | URL (or IP) | `https://uma-build.onrender.com/api/health` |
    | Monitoring Interval | `5 minutes` (無料枠最短) |
    | Monitor Timeout | `30 seconds` |
    | HTTP Method | `GET` |

3. 「Create Monitor」をクリック

### 3. 動作確認
- 数分後にダッシュボードで status が **Up** (緑) になっていることを確認
- Render ダッシュボード → Logs で 5 分間隔に `/api/health` へのアクセスがあることを確認

---

## 注意事項

### Render Free の月 750 時間制限
- 1 ヶ月の総時間は約 720〜744 時間 (= 24 時間 × 30〜31 日)
- Render Free の無料枠は月 **750 時間**まで
- 24/7 稼働させるとほぼ上限ギリギリで、月末に停止する可能性がある
- **マネタイズ前は当面これで運用**。もし月末停止が観測されたら以下を検討:
  - UptimeRobot の interval を 10 分に伸ばす (ただし Render スリープ > 15 分を避けるため結局効果薄)
  - Render Starter ($7/月) に移行
  - Render の代わりに常時稼働できる別の無料 PaaS へ移行

### `/api/health` エンドポイント
- `backend/main.py` または `backend/routers/` に定義されていることを確認
- 200 OK を返すだけのシンプルなエンドポイントで OK
- DB 接続チェックなどを含めると重くなるので、health は軽量に保つ

### アラート通知
- UptimeRobot 無料枠でメール通知が使える
- Down が継続した場合にメールが届くよう設定しておくと安心

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
                                                 (UptimeRobot が
                                                  5分毎に /api/health
                                                  を叩いてwarm維持)
```

- **一次防衛線**: Vercel Edge Cache (特徴量カタログ)
- **二次防衛線**: UptimeRobot による Render の warm 維持
- **三次防衛線**: `ColdStartLoader` による段階的メッセージ表示 (最終フォールバック)
