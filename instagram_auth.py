"""Instagram アクセストークンの管理。

長期トークン（60日間有効）を GCS またはローカルファイルで管理する。
有効期限が 7 日以内に迫っていれば自動でリフレッシュする。
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import requests
import gcs_backend

TOKEN_FILE = Path("instagram_token.json")
TOKEN_BLOB = "instagram_token.json"
GRAPH_BASE = "https://graph.instagram.com"

# 残り有効期限がこの日数以下になったらリフレッシュ
REFRESH_THRESHOLD_DAYS = 7


def _load_stored() -> Optional[dict]:
    text = None
    if gcs_backend.is_enabled():
        text = gcs_backend.read_text(TOKEN_BLOB)
    elif TOKEN_FILE.exists():
        text = TOKEN_FILE.read_text()
    return json.loads(text) if text else None


def _save_stored(data: dict) -> None:
    text = json.dumps(data)
    if gcs_backend.is_enabled():
        gcs_backend.write_text(TOKEN_BLOB, text)
    else:
        TOKEN_FILE.write_text(text)


def get_access_token() -> str:
    """有効なアクセストークンを返す。必要なら自動リフレッシュする。"""
    stored = _load_stored()

    if stored:
        token = stored["access_token"]
        expires_at = stored.get("expires_at")

        if expires_at:
            remaining = datetime.fromisoformat(expires_at) - datetime.now(timezone.utc)
            if remaining > timedelta(days=REFRESH_THRESHOLD_DAYS):
                return token

        # リフレッシュ
        print("      Instagramトークンをリフレッシュ中...")
        return _refresh_and_save(token)

    # 環境変数から初期トークンを取得
    initial_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not initial_token:
        raise RuntimeError(
            "INSTAGRAM_ACCESS_TOKEN が設定されていません。\n"
            ".env に初期アクセストークンを設定してください。"
        )

    # 長期トークンに交換して保存
    print("      短期トークンを長期トークンに交換中...")
    return _exchange_and_save(initial_token)


def _exchange_and_save(short_token: str) -> str:
    """短期トークン → 長期トークン（60日）に交換して保存する。"""
    app_id = os.environ["INSTAGRAM_APP_ID"]
    app_secret = os.environ["INSTAGRAM_APP_SECRET"]

    resp = requests.get(
        f"{GRAPH_BASE}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    token = data["access_token"]
    expires_in = data.get("expires_in", 5184000)  # デフォルト60日
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    _save_stored({"access_token": token, "expires_at": expires_at})
    print(f"      長期トークン取得完了（有効期限: {expires_at[:10]}）")
    return token


def _refresh_and_save(token: str) -> str:
    """長期トークンをリフレッシュして保存する。"""
    resp = requests.get(
        f"{GRAPH_BASE}/refresh_access_token",
        params={
            "grant_type": "ig_refresh_token",
            "access_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    new_token = data["access_token"]
    expires_in = data.get("expires_in", 5184000)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    _save_stored({"access_token": new_token, "expires_at": expires_at})
    print(f"      トークンリフレッシュ完了（有効期限: {expires_at[:10]}）")
    return new_token
