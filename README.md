# 波動鑑定士・天導 — YouTube コメント自動返信ツール

YouTubeチャンネルの未返信コメントを自動取得し、占い師キャラ「波動鑑定士・天導（テンドウ）」として Claude AI が返信文を生成・投稿するツールです。

---

## 必要なもの

- Python 3.10 以上
- Google Cloud プロジェクト（YouTube Data API v3 が有効なもの）
- Anthropic API キー

---

## ローカルでの実行

### 1. Google Cloud の設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセスしてプロジェクトを作成
2. **APIとサービス → ライブラリ** から **YouTube Data API v3** を有効化
3. **APIとサービス → 認証情報** で **OAuthクライアントID** を作成
   - アプリケーションの種類: **デスクトップアプリ**
4. 作成した認証情報の **クライアントID** と **クライアントシークレット** をメモしておく
5. **APIとサービス → OAuth同意画面** でテストユーザーに自分のGoogleアカウントを追加

### 2. Anthropic API キーの取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. API キーを発行してメモしておく

### 3. チャンネルIDの確認

YouTubeのチャンネルページを開き、**詳細情報** タブで `UC` から始まるIDを確認できます。

### 4. セットアップ

```bash
git clone <このリポジトリのURL>
cd YouTube-

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# .env を編集して各値を入力
```

### 5. 実行

```bash
python main.py
```

初回はブラウザが開いてGoogle認証を求められます。許可すると `token.json` が保存され、次回以降は自動ログインになります。

---

## Cloud Run での自動実行（1時間ごと）

### アーキテクチャ

```
Cloud Scheduler（1時間ごと）
    ↓
Cloud Run Job（コンテナ起動）
    ↓
GCS バケット（token.json / last_run.json の永続化）
    ↓
YouTube API + Claude API
```

Cloud Run はコンテナが使い捨てのため、OAuthトークンと前回実行時刻を **Google Cloud Storage（GCS）** に保存します。

---

### デプロイ手順

#### ステップ 1: 変数の設定

以下の変数をターミナルで設定してからコマンドを実行してください。

```bash
PROJECT_ID=your-gcp-project-id
REGION=asia-northeast1
BUCKET_NAME=youtube-autoreply-state
IMAGE=gcr.io/$PROJECT_ID/youtube-autoreply
JOB_NAME=youtube-autoreply-job
SCHEDULER_NAME=youtube-autoreply-schedule
```

#### ステップ 2: 必要な API の有効化

```bash
gcloud config set project $PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
```

#### ステップ 3: GCS バケットの作成

```bash
gsutil mb -l $REGION gs://$BUCKET_NAME
```

#### ステップ 4: ローカルで OAuth 認証してトークンを GCS にアップロード

Cloud Run 上では対話的な認証ができないため、**ローカルで先に認証**します。

```bash
# ローカルで .env を設定済みの状態で実行
python main.py   # ブラウザで認証 → token.json が生成される

# 生成された token.json を GCS にアップロード
gsutil cp token.json gs://$BUCKET_NAME/token.json
```

#### ステップ 5: サービスアカウントの作成と権限付与

```bash
SA_NAME=youtube-autoreply-sa
SA_EMAIL=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com

# サービスアカウント作成
gcloud iam service-accounts create $SA_NAME \
  --display-name="YouTube AutoReply SA"

# GCS バケットへの読み書き権限
gsutil iam ch serviceAccount:$SA_EMAIL:roles/storage.objectAdmin \
  gs://$BUCKET_NAME
```

#### ステップ 6: Docker イメージのビルドとプッシュ

```bash
# Container Registry への認証
gcloud auth configure-docker

# ビルド & プッシュ
docker build -t $IMAGE .
docker push $IMAGE
```

#### ステップ 7: Cloud Run Job の作成

```bash
gcloud run jobs create $JOB_NAME \
  --image=$IMAGE \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --set-env-vars="GOOGLE_CLIENT_ID=ここにクライアントID" \
  --set-env-vars="GOOGLE_CLIENT_SECRET=ここにクライアントシークレット" \
  --set-env-vars="ANTHROPIC_API_KEY=ここにAnthropicAPIキー" \
  --set-env-vars="YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxxxx" \
  --set-env-vars="GCS_BUCKET_NAME=$BUCKET_NAME" \
  --max-retries=1 \
  --task-timeout=300
```

#### ステップ 8: 動作確認（手動実行）

```bash
gcloud run jobs execute $JOB_NAME --region=$REGION --wait
```

ログを確認：

```bash
gcloud run jobs executions list --job=$JOB_NAME --region=$REGION
# 実行IDをコピーして↓
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
  --limit=50 --format="table(timestamp, textPayload)"
```

#### ステップ 9: Cloud Scheduler で1時間ごとに自動実行

```bash
# Cloud Run Job を呼び出す権限をスケジューラに付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.invoker"

# スケジューラ作成（毎時0分に実行）
gcloud scheduler jobs create http $SCHEDULER_NAME \
  --location=$REGION \
  --schedule="0 * * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
  --http-method=POST \
  --oauth-service-account-email=$SA_EMAIL
```

#### 停止・削除したいとき

```bash
# スケジューラの一時停止
gcloud scheduler jobs pause $SCHEDULER_NAME --location=$REGION

# スケジューラの再開
gcloud scheduler jobs resume $SCHEDULER_NAME --location=$REGION

# 全削除
gcloud scheduler jobs delete $SCHEDULER_NAME --location=$REGION
gcloud run jobs delete $JOB_NAME --region=$REGION
gsutil rm -r gs://$BUCKET_NAME
```

---

## ファイル構成

```
YouTube-/
├── main.py             # エントリーポイント
├── auth.py             # Google OAuth 認証（GCS対応）
├── youtube_client.py   # YouTube API 操作
├── ai_reply.py         # Claude AI 返信生成
├── gcs_backend.py      # GCS 読み書きユーティリティ
├── state.py            # 前回実行時刻の管理（GCS対応）
├── Dockerfile          # Cloud Run 用コンテナ定義
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数サンプル
├── .env                # 環境変数（要作成・Gitに含めない）
├── token.json          # OAuthトークン（自動生成・Gitに含めない）
└── last_run.json       # 前回実行時刻（自動生成・Gitに含めない）
```

---

## 注意事項

- `.env` と `token.json` は機密情報です。Gitにコミットしないよう `.gitignore` で除外しています。
- YouTube Data API v3 の無料クォータは **1日10,000 units**。`comments.insert` は50 units/件のため、**1日約200件**が上限です。
- OAuthトークン（`token.json`）は有効期限が切れると自動でリフレッシュされ、GCSに上書き保存されます。
- リフレッシュトークン自体が失効した場合（長期未使用など）は、ローカルで再認証して `token.json` を GCS に再アップロードしてください。
