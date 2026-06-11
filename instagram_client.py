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
    print(f"      [DEBUG] /me レスポンス: id={data.get('id')} username={data.get('username')}")
    return data["id"]


def iter_new_unanswered_comments(
    token: str, ig_user_id: str, published_after: str
) -> Generator[IgComment, None, None]:
    """published_after 以降の未返信トップレベルコメントをジェネレータで返す。

    Instagram のコメントは古い順で返されるため、reached_old による
    早期終了は使わず、全件取得してから Python 側で日時フィルタリングする。
    """
    cutoff = datetime.fromisoformat(published_after.replace("Z", "+00:00"))
    print(f"      [DEBUG] cutoff = {cutoff.isoformat()}")

    media_ids = _fetch_all_media_ids(token, ig_user_id)
    print(f"      [DEBUG] 取得した投稿数: {len(media_ids)}")

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
        page_ids = [item["id"] for item in data.get("data", [])]
        ids.extend(page_ids)
        print(f"      [DEBUG] 投稿ページ取得: {len(page_ids)} 件（累計 {len(ids)} 件）")

        cursors = data.get("paging", {}).get("cursors", {})
        after = cursors.get("after")
        if not after or not data.get("paging", {}).get("next"):
            break

    return ids


def _iter_comments_for_media(
    token: str, media_id: str, cutoff: datetime
) -> Generator[IgComment, None, None]:
    """1つの投稿の未返信コメントをジェネレータで返す。

    Instagram はコメントを古い順で返す。reached_old による早期終了は
    行わず全ページを取得し、cutoff より新しいコメントのみ yield する。
    """
    after: Optional[str] = None
    total_fetched = 0
    total_yielded = 0

    while True:
        params: dict = {
            # replies.summary(true) の代わりに replies{id} で件数を判定
            "fields": "id,text,timestamp,username,replies{id}",
            "limit": 100,
        }
        if after:
            params["after"] = after

        try:
            data = _get(f"/{media_id}/comments", token, **params)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (400, 404):
                print(f"      [DEBUG] 投稿 {media_id}: コメント取得スキップ (HTTP {e.response.status_code})")
                break
            raise

        items = data.get("data", [])
        total_fetched += len(items)

        for item in items:
            ts_str = item.get("timestamp", "")
            text = item.get("text", "").strip()

            # cutoff より古いコメントはスキップ（yield しない）
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts <= cutoff:
                    continue

            # すでに返信があるコメントはスキップ
            replies_data = item.get("replies", {}).get("data", [])
            if replies_data:
                print(f"      [DEBUG] コメント {item['id']}: 返信済みのためスキップ")
                continue

            if not text:
                continue

            print(f"      [DEBUG] 新着コメント発見: id={item['id']} ts={ts_str} text={text[:40]}")
            total_yielded += 1
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

    if total_fetched > 0:
        print(f"      [DEBUG] 投稿 {media_id}: 取得 {total_fetched} 件 → 新着未返信 {total_yielded} 件")


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
