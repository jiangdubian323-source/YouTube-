#!/usr/bin/env python3
"""Instagram コメント自動返信ツール — 波動鑑定士・天導"""

import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import anthropic

from instagram_auth import get_access_token
from instagram_client import get_ig_user_id, iter_new_unanswered_comments, post_reply
from ai_reply import generate_reply
from state import load_last_run, save_last_run

# 各処理間のウェイト設定（秒）
WAIT_BETWEEN_REPLIES = 2.0   # 返信投稿ごとの待機（レート制限対策）
WAIT_ON_RATE_LIMIT = 60.0    # レート制限エラー時の待機

# state.py の GCS キーを Instagram 用に上書き
import state as _state
_state.STATE_BLOB = "instagram_last_run.json"
_state.STATE_FILE = __import__("pathlib").Path("instagram_last_run.json")


def main() -> None:
    load_dotenv()

    required = [
        "INSTAGRAM_APP_ID",
        "INSTAGRAM_APP_SECRET",
        "INSTAGRAM_ACCESS_TOKEN",
        "ANTHROPIC_API_KEY",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[ERROR] .env に以下のキーが設定されていません: {', '.join(missing)}")
        print("        .env.example を参考に .env ファイルを作成してください。")
        sys.exit(1)

    print("=" * 60)
    print("  波動鑑定士・天導 — Instagram コメント自動返信ツール")
    print("=" * 60)

    # トークン取得（必要なら自動リフレッシュ）
    print("\n[1/3] Instagram アクセストークン確認中...")
    token = get_access_token()
    ig_user_id = get_ig_user_id(token)
    print(f"      認証完了（ユーザーID: {ig_user_id}）")

    # 前回実行時刻を取得して今回の開始時刻を記録
    last_run = load_last_run()
    run_started_at = datetime.now(timezone.utc)
    print(f"\n[2/3] {last_run} 以降の新着コメントを処理します...\n")

    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    success = 0
    errors = 0
    index = 0

    try:
        for comment in iter_new_unanswered_comments(token, ig_user_id, published_after=last_run):
            index += 1
            print(f"  [{index}] @{comment.username}: {comment.text[:60]}{'...' if len(comment.text) > 60 else ''}")

            try:
                reply_text = generate_reply(anthropic_client, comment.text)
                print(f"       返信: {reply_text}")

                post_reply(token, comment.comment_id, reply_text)
                print(f"       → 投稿完了\n")
                success += 1

                time.sleep(WAIT_BETWEEN_REPLIES)

            except Exception as e:
                err_str = str(e)
                if "rate limit" in err_str.lower() or "429" in err_str:
                    print(f"       [WARN] レート制限。{WAIT_ON_RATE_LIMIT}秒待機してリトライします...\n")
                    time.sleep(WAIT_ON_RATE_LIMIT)
                    try:
                        reply_text = generate_reply(anthropic_client, comment.text)
                        post_reply(token, comment.comment_id, reply_text)
                        print(f"       → リトライ成功\n")
                        success += 1
                    except Exception as retry_err:
                        print(f"       [ERROR] リトライも失敗: {retry_err}\n")
                        errors += 1
                else:
                    print(f"       [WARN] 投稿失敗: {e}\n")
                    errors += 1

    except Exception as e:
        print(f"\n[ERROR] コメント取得中にエラーが発生しました: {e}")

    if index == 0:
        print("      新着の未返信コメントはありませんでした。")

    if errors == 0 or success > 0:
        save_last_run(run_started_at)

    print("=" * 60)
    print(f"[3/3] 完了: 対象 {index} 件 / 成功 {success} 件 / 失敗 {errors} 件")
    print("=" * 60)


if __name__ == "__main__":
    main()
