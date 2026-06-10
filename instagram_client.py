"""Instagram Graph API の操作: コメント取得・返信投稿。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generator, Optional
import requests

GRAPH_BASE = "https://graph.instagram.com/v21.0"


@dataclass
class IgComment:
    comment_id: str
    media_id: str
    username: str
    text: str
    timestamp: str


def _get(path: str, token: str, **params) -> dict:
    resp = requests.get(
        f"{GRAPH_BASE}{path}",
        params={"access_token": token, **params},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_ig_user_id(token: str) -> str:
    """認証済みユーザーの Instagram ユーザー ID を返す。"""
    data = _get("/me", token, fields="id,username")
    return data["id"]


def iter_new_unanswered_comments(
    token: str, ig_user_id: str, published_after: str
) -> Generator[IgComment, None, None]:
    """published_after 以降の未返信トップレベルコメントをジェネレータで返す。

    - ユーザーの全投稿を走査し、各投稿のコメントを取得する
    - すでに返信がある（replies フィールドに件数がある）コメントはスキップ
    - Python 側で timestamp を比較してフィルタリングする
    """
    cutoff = datetime.fromisoformat(published_after.replace("Z", "+00:00"))
    media_ids = _fetch_all_media_ids(token, ig_user_id)

    for media_id in media_ids:
        yield from _iter_comments_for_media(token, media_id, cutoff)


def _fetch_all_media_ids(token: str, ig_user_id: str) -> list[str]:
    """ユーザーの全投稿 ID を取得する。"""
    ids: list[str] = []
    after: Optional[str] = None

    while True:
        params: dict = {"fields": "id", "limit": 100}
        if after:
            params["after"] = after

        data = _get(f"/{ig_user_id}/media", token, **params)
        ids.extend(item["id"] for item in data.get("data", []))

        cursors = data.get("paging", {}).get("cursors", {})
        after = cursors.get("after")
        if not after or not data.get("paging", {}).get("next"):
            break

    return ids


def _iter_comments_for_media(
    token: str, media_id: str, cutoff: datetime
) -> Generator[IgComment, None, None]:
    """1つの投稿の未返信コメントをジェネレータで返す。"""
    after: Optional[str] = None
    reached_old = False

    while not reached_old:
        params: dict = {
            "fields": "id,text,timestamp,username,replies.summary(true)",
            "limit": 100,
        }
        if after:
            params["after"] = after

        try:
            data = _get(f"/{media_id}/comments", token, **params)
        except requests.HTTPError as e:
            # コメントが無効・削除済みの投稿はスキップ
            if e.response is not None and e.response.status_code in (400, 404):
                break
            raise

        for item in data.get("data", []):
            ts_str = item.get("timestamp", "")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts <= cutoff:
                    reached_old = True
                    break

            # すでに返信があるコメントはスキップ
            replies = item.get("replies", {})
            if replies.get("data") or replies.get("summary", {}).get("total_count", 0) > 0:
                continue

            text = item.get("text", "").strip()
            if not text:
                continue

            yield IgComment(
                comment_id=item["id"],
                media_id=media_id,
                username=item.get("username", ""),
                text=text,
                timestamp=ts_str,
            )

        cursors = data.get("paging", {}).get("cursors", {})
        after = cursors.get("after")
        if not after or not data.get("paging", {}).get("next"):
            break


def post_reply(token: str, comment_id: str, reply_text: str) -> Optional[str]:
    """コメントに返信を投稿し、新しいコメント ID を返す。"""
    resp = requests.post(
        f"{GRAPH_BASE}/{comment_id}/replies",
        params={"access_token": token},
        json={"message": reply_text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("id")
