import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import gcs_backend

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE = Path("token.json")
TOKEN_BLOB = "token.json"


def _build_client_config(client_id: str, client_secret: str) -> dict:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }


def get_credentials() -> Credentials:
    """保存済みトークンを読み込むか、OAuthフローで新規認証する。

    GCS_BUCKET_NAME が設定されている場合は GCS からトークンを読み書きする。
    Cloud Run 上では対話的 OAuth フローは実行できないため、
    事前に `python auth.py` でローカル認証を済ませておく必要がある。
    """
    creds = _load_token()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds

    if gcs_backend.is_enabled():
        raise RuntimeError(
            "Cloud Run 環境でトークンが見つかりません。\n"
            "ローカルで `python auth.py` を実行して token.json を GCS にアップロードしてください。\n"
            "  gsutil cp token.json gs://$GCS_BUCKET_NAME/token.json"
        )

    # ローカル: 対話的 OAuth フロー
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    flow = InstalledAppFlow.from_client_config(
        _build_client_config(client_id, client_secret), SCOPES
    )

    print("\n" + "=" * 60)
    print("Google OAuth 認証が必要です。")
    print("ブラウザが開かない場合は、表示されるURLをコピーしてください。")
    print("=" * 60 + "\n")

    creds = flow.run_local_server(port=0, open_browser=True)
    _save_token(creds)
    print("\n認証完了。token.json を保存しました。\n")
    return creds


def _load_token() -> Credentials | None:
    if gcs_backend.is_enabled():
        text = gcs_backend.read_text(TOKEN_BLOB)
        if text:
            return Credentials.from_authorized_user_info(json.loads(text), SCOPES)
        return None
    if TOKEN_FILE.exists():
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    return None


def _save_token(creds: Credentials) -> None:
    if gcs_backend.is_enabled():
        gcs_backend.write_text(TOKEN_BLOB, creds.to_json())
    else:
        TOKEN_FILE.write_text(creds.to_json())
