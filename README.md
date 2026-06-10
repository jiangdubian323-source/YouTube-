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
├── main.py                  # YouTube エントリーポイント
├── auth.py                  # Google OAuth 認証（GCS対応）
├── youtube_client.py        # YouTube API 操作
├── instagram_main.py        # Instagram エントリーポイント
├── instagram_auth.py        # Instagram トークン管理（GCS対応）
├── instagram_client.py      # Instagram Graph API 操作
├── ai_reply.py              # Claude AI 返信生成（YouTube/Instagram 共通）
├── gcs_backend.py           # GCS 読み書きユーティリティ（共通）
├── state.py                 # 前回実行時刻の管理（GCS対応・共通）
├── Dockerfile               # YouTube 用 Cloud Run コンテナ
├── Dockerfile.instagram     # Instagram 用 Cloud Run コンテナ
├── requirements.txt         # 依存パッケージ
├── .env.example             # 環境変数サンプル
└── .env                     # 環境変数（要作成・Gitに含めない）
```

---

## 注意事項（YouTube）

- `.env` と `token.json` は機密情報です。Gitにコミットしないよう `.gitignore` で除外しています。
- YouTube Data API v3 の無料クォータは **1日10,000 units**。`comments.insert` は50 units/件のため、**1日約200件**が上限です。
- OAuthトークン（`token.json`）は有効期限が切れると自動でリフレッシュされ、GCSに上書き保存されます。
- リフレッシュトークン自体が失効した場合（長期未使用など）は、ローカルで再認証して `token.json` を GCS に再アップロードしてください。

---

---

# Instagram コメント自動返信ツール

Instagramの未返信コメントを自動取得し、占い師キャラ「波動鑑定士・天導（テンドウ）」として Claude AI が返信文を生成・投稿するツールです。

---

## Instagram API の事前準備

Instagram Graph API を使うには **Facebookビジネスアカウント** と **Instagramプロフェッショナルアカウント** が必要です。

### 1. Facebookアプリの作成

1. [Meta for Developers](https://developers.facebook.com/apps/) にアクセス
2. **アプリを作成** → **その他** → **ビジネス** を選択
3. アプリ名を入力して作成
4. **アプリID** と **アプリシークレット** をメモ（設定 → ベーシック）

### 2. Instagram Graph API の追加

1. アプリのダッシュボードで **製品を追加** → **Instagram Graph API** を選択
2. **設定 → ベーシック** でアプリモードを **本番** に変更（または自分のアカウントをテストユーザーに追加）

### 3. InstagramアカウントをFacebookページに連携

1. Facebookページの **設定 → リンク済みアカウント** からInstagramアカウントを連携
2. Instagramアカウントは **プロフェッショナルアカウント**（ビジネスまたはクリエイター）である必要があります

### 4. アクセストークンの取得

#### 方法A: Graph API Explorer（推奨・簡単）

1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/) を開く
2. 右上のアプリを作成したアプリに切り替える
3. **ユーザーまたはページ** で **ユーザートークンを取得** をクリック
4. 以下の権限にチェックを入れる：
   - `instagram_basic`
   - `instagram_manage_comments`
   - `pages_show_list`
5. **アクセストークンを生成** をクリック → 表示されたトークンをコピー

このトークンは **短期トークン（有効期限1時間）** ですが、ツール初回実行時に自動で **長期トークン（60日）** に交換・GCSへ保存されます。

#### 方法B: curl で直接取得

```bash
# ブラウザで以下のURLを開いてアクセスを許可
https://www.facebook.com/v21.0/dialog/oauth?\
  client_id=YOUR_APP_ID\
  &redirect_uri=https://localhost\
  &scope=instagram_basic,instagram_manage_comments,pages_show_list\
  &response_type=token

# リダイレクト先のURLから access_token= の値をコピー
```

---

## ローカルでの実行

```bash
# .env を設定
cp .env.example .env
# INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_ACCESS_TOKEN を記入

pip install -r requirements.txt
python instagram_main.py
```

初回実行時に短期トークンが長期トークンに自動交換され、`instagram_token.json` に保存されます。

---

## Cloud Run での自動実行（1時間ごと）

### ステップ 1: 変数の設定

```bash
PROJECT_ID=your-gcp-project-id
REGION=asia-northeast1
BUCKET_NAME=youtube-autoreply-state   # YouTube と共用可
IMAGE=gcr.io/$PROJECT_ID/instagram-autoreply
JOB_NAME=instagram-autoreply-job
SCHEDULER_NAME=instagram-autoreply-schedule
SA_EMAIL=youtube-autoreply-sa@$PROJECT_ID.iam.gserviceaccount.com
```

### ステップ 2: 初回ローカル実行でトークンを GCS にアップロード

```bash
# ローカルで .env を設定した状態で実行（instagram_token.json が生成される）
python instagram_main.py

# GCS にアップロード
gsutil cp instagram_token.json gs://$BUCKET_NAME/instagram_token.json
```

### ステップ 3: Docker イメージのビルドとプッシュ

```bash
gcloud auth configure-docker

docker build -f Dockerfile.instagram -t $IMAGE .
docker push $IMAGE
```

### ステップ 4: Cloud Run Job の作成

```bash
gcloud run jobs create $JOB_NAME \
  --image=$IMAGE \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --set-env-vars="INSTAGRAM_APP_ID=ここにアプリID" \
  --set-env-vars="INSTAGRAM_APP_SECRET=ここにアプリシークレット" \
  --set-env-vars="INSTAGRAM_ACCESS_TOKEN=dummy" \
  --set-env-vars="ANTHROPIC_API_KEY=ここにAnthropicAPIキー" \
  --set-env-vars="GCS_BUCKET_NAME=$BUCKET_NAME" \
  --max-retries=1 \
  --task-timeout=300
```

> `INSTAGRAM_ACCESS_TOKEN=dummy` と設定しておけば OK です。GCS に保存済みの長期トークンが使われます。

### ステップ 5: 動作確認

```bash
gcloud run jobs execute $JOB_NAME --region=$REGION --wait
```

### ステップ 6: Cloud Scheduler で1時間ごとに自動実行

```bash
gcloud scheduler jobs create http $SCHEDULER_NAME \
  --location=$REGION \
  --schedule="0 * * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME:run" \
  --http-method=POST \
  --oauth-service-account-email=$SA_EMAIL
```

### 停止・削除したいとき

```bash
gcloud scheduler jobs pause $SCHEDULER_NAME --location=$REGION
gcloud scheduler jobs delete $SCHEDULER_NAME --location=$REGION
gcloud run jobs delete $JOB_NAME --region=$REGION
```

---

## 注意事項（Instagram）

- Instagram Graph API のレート制限は **200コール/時間/ユーザー**。通常の運用では問題ありません。
- 長期トークンは **60日で失効**しますが、残り7日以内になると自動でリフレッシュされます。
- リフレッシュに失敗した場合は、ローカルで再度短期トークンを取得して `INSTAGRAM_ACCESS_TOKEN` を更新し、`python instagram_main.py` を実行してください。
- 返信できるのは **自分の投稿へのコメント** のみです（他アカウントの投稿には返信できません）。
