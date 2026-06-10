from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


@dataclass
class Comment:
    comment_id: str
    video_id: str
    author: str
    text: str
    published_at: str
    reply_count: int


def build_youtube(creds: Credentials):
    return build("youtube", "v3", credentials=creds)


def fetch_unanswered_comments(youtube, channel_id: str, max_results: int = 10) -> list[Comment]:
    """チャンネルの未返信コメントを取得する。"""
    comments: list[Comment] = []

    request = youtube.commentThreads().list(
        part="snippet",
        allThreadsRelatedToChannelId=channel_id,
        maxResults=min(max_results, 100),
        order="time",
        moderationStatus="published",
    )

    while request and len(comments) < max_results:
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            top = snippet["topLevelComment"]["snippet"]

            # チャンネルオーナー自身のコメントはスキップ
            if top.get("authorChannelId", {}).get("value") == channel_id:
                continue

            # すでに返信があるスレッドはスキップ
            if snippet.get("totalReplyCount", 0) > 0:
                continue

            comments.append(Comment(
                comment_id=item["snippet"]["topLevelComment"]["id"],
                video_id=snippet.get("videoId", ""),
                author=top.get("authorDisplayName", "名無し"),
                text=top.get("textDisplay", ""),
                published_at=top.get("publishedAt", ""),
                reply_count=snippet.get("totalReplyCount", 0),
            ))

            if len(comments) >= max_results:
                break

        request = youtube.commentThreads().list_next(request, response)

    return comments


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
