#!/usr/bin/env python3
"""YouTube コメント自動返信ツール — 波動鑑定士・天導"""

import os
import sys
import time
from dotenv import load_dotenv
import anthropic

from auth import get_credentials
from youtube_client import build_youtube, fetch_unanswered_comments, post_reply
from ai_reply import generate_reply


def main() -> None:
    load_dotenv()

    # 必須環境変数チェック
    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ANTHROPIC_API_KEY", "YOUTUBE_CHANNEL_ID"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[ERROR] .env に以下のキーが設定されていません: {', '.join(missing)}")
        print("        .env.example を参考に .env ファイルを作成してください。")
        sys.exit(1)

    channel_id = os.environ["YOUTUBE_CHANNEL_ID"]
    max_comments = int(os.getenv("MAX_COMMENTS", "10"))

    print("=" * 60)
    print("  波動鑑定士・天導 — YouTube コメント自動返信ツール")
    print("=" * 60)

    # 認証
    print("\n[1/4] Google OAuth 認証中...")
    creds = get_credentials()
    youtube = build_youtube(creds)
    print("      認証完了。")

    # 未返信コメント取得
    print(f"\n[2/4] 未返信コメントを取得中（最大 {max_comments} 件）...")
    comments = fetch_unanswered_comments(youtube, channel_id, max_results=max_comments)
    if not comments:
        print("      未返信のコメントはありませんでした。")
        return
    print(f"      {len(comments)} 件の未返信コメントを取得しました。")

    # 返信生成・投稿
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    success = 0
    errors = 0

    print(f"\n[3/4] 返信を生成して投稿します...\n")
    for i, comment in enumerate(comments, 1):
        print(f"  [{i}/{len(comments)}] コメント: {comment.text[:60]}{'...' if len(comment.text) > 60 else ''}")
        print(f"           投稿者: {comment.author}")

        try:
            reply_text = generate_reply(anthropic_client, comment.text)
            print(f"           返信: {reply_text}")

            post_reply(youtube, comment.comment_id, reply_text)
            print(f"           → 投稿完了\n")
            success += 1

            # API レート制限対策
            if i < len(comments):
                time.sleep(1.5)

        except Exception as e:
            print(f"           [WARN] 投稿失敗: {e}\n")
            errors += 1

    # サマリー
    print("=" * 60)
    print(f"[4/4] 完了: 成功 {success} 件 / 失敗 {errors} 件")
    print("=" * 60)


if __name__ == "__main__":
    main()
