#!/usr/bin/env python3
"""YouTube コメント自動返信ツール — 波動鑑定士・天導"""

import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import anthropic

from auth import get_credentials
from youtube_client import build_youtube, iter_new_unanswered_comments, post_reply
from ai_reply import generate_reply
from state import load_last_run, save_last_run

# 各処理間のウェイト設定（秒）
WAIT_BETWEEN_REPLIES = 2.0   # 返信投稿ごとの待機（連続書き込みのレート制限対策）
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
    print("=" * 60)

    # 認証
    print("\n[1/3] Google OAuth 認証中...")
    creds = get_credentials()
    youtube = build_youtube(creds)
    print("      認証完了。")

    # 前回実行時刻を取得し、今回の実行開始時刻を記録
    last_run = load_last_run()
    run_started_at = datetime.now(timezone.utc)
    print(f"\n[2/3] {last_run} 以降の新着コメントを処理します...\n")

    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    success = 0
    errors = 0
    index = 0

    try:
        for comment in iter_new_unanswered_comments(youtube, channel_id, published_after=last_run):
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
                    print(f"       [WARN] APIクォータ超過。{WAIT_ON_QUOTA_ERROR}秒待機してリトライします...\n")
                    time.sleep(WAIT_ON_QUOTA_ERROR)
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
            print(f"\n[ERROR] コメント取得中にAPIクォータを超過しました。明日再実行してください。")
        else:
            print(f"\n[ERROR] コメント取得中にエラーが発生しました: {e}")

    if index == 0:
        print("      新着の未返信コメントはありませんでした。")

    # 正常処理できた場合のみ実行時刻を保存（エラー中断時は次回も同じ範囲を再処理）
    if errors == 0 or success > 0:
        save_last_run(run_started_at)

    print("=" * 60)
    print(f"[3/3] 完了: 対象 {index} 件 / 成功 {success} 件 / 失敗 {errors} 件")
    print("=" * 60)


if __name__ == "__main__":
    main()
