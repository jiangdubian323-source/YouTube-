# 波動鑑定士・天導 — YouTube コメント自動返信ツール

YouTubeチャンネルの未返信コメントを自動取得し、占い師キャラ「波動鑑定士・天導（テンドウ）」として Claude AI が返信文を生成・投稿するツールです。

---

## 必要なもの

- Python 3.9 以上
- Google Cloud プロジェクト（YouTube Data API v3 が有効なもの）
- Anthropic API キー

---

## セットアップ手順

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

YouTubeのチャンネルページを開き、URLの `UC` で始まる部分がチャンネルIDです。

例: `https://www.youtube.com/@yourname` → チャンネルページの **詳細情報** タブでIDを確認できます。

### 4. リポジトリのセットアップ

```bash
# リポジトリをクローン
git clone <このリポジトリのURL>
cd YouTube-

# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 5. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定します。

```bash
cp .env.example .env
```

`.env` をテキストエディタで開いて編集：

```
GOOGLE_CLIENT_ID=取得したクライアントID
GOOGLE_CLIENT_SECRET=取得したクライアントシークレット
ANTHROPIC_API_KEY=取得したAnthropicAPIキー
YOUTUBE_CHANNEL_ID=UCから始まるチャンネルID
MAX_COMMENTS=10
```

---

## 実行方法

```bash
python main.py
```

### 初回実行時

初回はブラウザが自動で開き、Googleアカウントへのログインと権限の許可を求められます。  
許可すると `token.json` が保存され、次回以降は自動ログインになります。

### 動作の流れ

1. Google OAuth 認証
2. チャンネルの未返信コメントを取得
3. 各コメントに対して Claude AI が占い師キャラとして返信文を生成
4. YouTube API で返信を投稿

---

## ファイル構成

```
YouTube-/
├── main.py             # エントリーポイント
├── auth.py             # Google OAuth 認証
├── youtube_client.py   # YouTube API 操作
├── ai_reply.py         # Claude AI 返信生成
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数サンプル
├── .env                # 環境変数（要作成・Gitに含めない）
└── token.json          # OAuthトークン（自動生成・Gitに含めない）
```

---

## 注意事項

- `.env` と `token.json` は機密情報です。Gitにコミットしないよう `.gitignore` で除外しています。
- YouTube Data API v3 には1日あたりの使用量制限（クォータ）があります。大量実行にご注意ください。
- `MAX_COMMENTS` で1回の実行あたりの処理件数を調整できます（デフォルト: 10件）。
