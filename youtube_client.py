from __future__ import annotations
from dataclasses import dataclass
from typing import Generator, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


@dataclass
class Comment:
    comment_id: str
    video_id: str
    author: str
    text: str
    published_at: str


def build_youtube(creds: Credentials):
    return build("youtube", "v3", credentials=creds)


def iter_new_unanswered_comments(
    youtube, channel_id: str, published_after: str
) -> Generator[Comment, None, None]:
    """published_after 以降に投稿された未返信コメントをジェネレータで返す。

    commentThreads.list は publishedAfter パラメータ非対応のため、
    order="time"（新しい順）で取得しながら Python 側で日時比較し、
    published_after より古いコメントに達した時点で打ち切る。

    published_after: RFC 3339 形式の文字列 (例: "2024-01-01T00:00:00Z")
    """
    from datetime import datetime, timezone

    cutoff = datetime.fromisoformat(published_after.replace("Z", "+00:00"))
    page_token: Optional[str] = None

    while True:
        kwargs = dict(
            part="snippet",
            allThreadsRelatedToChannelId=channel_id,
            maxResults=100,
            order="time",
            moderationStatus="published",
        )
        if page_token:
            kwargs["pageToken"] = page_token

        response = youtube.commentThreads().list(**kwargs).execute()
        reached_old = False

        for item in response.get("items", []):
            snippet = item["snippet"]
            top = snippet["topLevelComment"]["snippet"]
            published_at_str = top.get("publishedAt", "")

            # 投稿日時が cutoff より古ければここで全走査を終了
            if published_at_str:
                published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                if published_at <= cutoff:
                    reached_old = True
                    break

            # チャンネルオーナー自身のコメントはスキップ
            if top.get("authorChannelId", {}).get("value") == channel_id:
                continue

            # すでに返信があるスレッドはスキップ
            if snippet.get("totalReplyCount", 0) > 0:
                continue

            yield Comment(
                comment_id=item["snippet"]["topLevelComment"]["id"],
                video_id=snippet.get("videoId", ""),
                author=top.get("authorDisplayName", "名無し"),
                text=top.get("textDisplay", ""),
                published_at=published_at_str,
            )

        page_token = response.get("nextPageToken")
        if reached_old or not page_token:
            break


def post_reply(youtube, parent_id: str, reply_text: str) -> Optional[str]:
    """コメントに返信を投稿し、新しいコメントIDを返す。"""
    response = youtube.comments().insert(
        part="snippet",
        body={
            "snippet": {
                "parentId": parent_id,
                "textOriginal": reply_text,
            }
        },
    ).execute()
    return response.get("id")
