#!/usr/bin/env python3
"""YouTube コメント自動返信ツール — 波動鑑定士・天導"""

import os
import sys
import time
from dotenv import load_dotenv
import anthropic

from auth import get_credentials
from youtube_client import build_youtube, iter_unanswered_comments, post_reply
from ai_reply import generate_reply

# YouTube Data API v3 の書き込みクォータ消費量（単位: units）
# commentThreads.list: 1 unit/page、comments.insert: 50 units
# 1日の無料クォータは10,000 units。
# 200件返信するだけで約10,000 units消費するため大量実行に注意。

# 各処理間のウェイト設定（秒）
WAIT_BETWEEN_REPLIES = 2.0   # 返信投稿ごとの待機（連続書き込みのレート制限対策）
WAIT_BETWEEN_PAGES = 0.5     # ページ取得ごとの待機（読み取りクォータ節約）
WAIT_ON_QUOTA_ERROR = 60.0   # クォータ超過時の待機


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

    print("=" * 60)
    print("  波動鑑定士・天導 — YouTube コメント自動返信ツール")
    print("  ※ 未返信コメントを全件処理します")
    print("=" * 60)

    # 認証
    print("\n[1/3] Google OAuth 認証中...")
    creds = get_credentials()
    youtube = build_youtube(creds)
    print("      認証完了。")

    # 返信生成・投稿（ストリーミング処理: 取得しながら即返信）
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    success = 0
    errors = 0
    index = 0

    print(f"\n[2/3] 未返信コメントを順次取得・返信します...\n")

    try:
        for comment in iter_unanswered_comments(youtube, channel_id):
            index += 1
            print(f"  [{index}] {comment.author}: {comment.text[:60]}{'...' if len(comment.text) > 60 else ''}")

            try:
                reply_text = generate_reply(anthropic_client, comment.text)
                print(f"       返信: {reply_text}")

                post_reply(youtube, comment.comment_id, reply_text)
                print(f"       → 投稿完了\n")
                success += 1

                time.sleep(WAIT_BETWEEN_REPLIES)

            except Exception as e:
                err_str = str(e)
                if "quotaExceeded" in err_str or "rateLimitExceeded" in err_str:
                    print(f"       [WARN] APIクォータ超過。{WAIT_ON_QUOTA_ERROR}秒待機して続行します...\n")
                    time.sleep(WAIT_ON_QUOTA_ERROR)
                    # 同じコメントをリトライ
                    try:
                        reply_text = generate_reply(anthropic_client, comment.text)
                        post_reply(youtube, comment.comment_id, reply_text)
                        print(f"       → リトライ成功\n")
                        success += 1
                    except Exception as retry_err:
                        print(f"       [ERROR] リトライも失敗: {retry_err}\n")
                        errors += 1
                else:
                    print(f"       [WARN] 投稿失敗: {e}\n")
                    errors += 1

    except Exception as e:
        err_str = str(e)
        if "quotaExceeded" in err_str or "rateLimitExceeded" in err_str:
            print(f"\n[ERROR] コメント取得中にAPIクォータを超過しました。")
            print(f"        本日の残クォータが不足しています。明日再実行してください。")
        else:
            print(f"\n[ERROR] コメント取得中にエラーが発生しました: {e}")

    if index == 0:
        print("      未返信のコメントはありませんでした。")

    # サマリー
    print("=" * 60)
    print(f"[3/3] 完了: 処理対象 {index} 件 / 成功 {success} 件 / 失敗 {errors} 件")
    print("=" * 60)


if __name__ == "__main__":
    main()
