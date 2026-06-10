import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE = Path("token.json")
CLIENT_SECRETS_FILE = Path("client_secret.json")


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
    """保存済みトークンを読み込むか、OAuthフローで新規認証する。"""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds

    # 新規認証フロー
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]

    client_config = _build_client_config(client_id, client_secret)
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print("\n" + "=" * 60)
    print("Google OAuth 認証が必要です。")
    print("ブラウザが開かない場合は、表示されるURLをコピーしてください。")
    print("=" * 60 + "\n")

    creds = flow.run_local_server(port=0, open_browser=True)
    _save_token(creds)
    print("\n認証完了。token.json を保存しました。\n")
    return creds


def _save_token(creds: Credentials) -> None:
    TOKEN_FILE.write_text(creds.to_json())
