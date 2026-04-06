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
- `feature_table_cache.csv` の生成

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
