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


def iter_unanswered_comments(youtube, channel_id: str) -> Generator[Comment, None, None]:
    """チャンネルの未返信コメントを全件ジェネレータで返す。

    ページネーション（nextPageToken）を使って全ページを走査する。
    1ページあたり最大100件を取得し、API呼び出し回数を最小化する。
    """
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

        for item in response.get("items", []):
            snippet = item["snippet"]
            top = snippet["topLevelComment"]["snippet"]

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
                published_at=top.get("publishedAt", ""),
            )

        page_token = response.get("nextPageToken")
        if not page_token:
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
