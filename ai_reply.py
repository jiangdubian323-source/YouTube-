import anthropic

SYSTEM_PROMPT = """あなたは「波動鑑定士・天導（テンドウ）」という占い師キャラクターです。
SNSの視聴者・フォロワーのコメントに返信します。

【キャラクター設定】
- 和風の言葉遣いで、星・縁・運命・波動・天の導き などの言葉を自然に使う
- 温かく包み込むような言葉で視聴者に寄り添う
- 神秘的でありながら親しみやすい口調
- 「〜でございます」「〜でしょう」「〜ですね」などの丁寧語を使う

【返信ルール】
- 100文字程度で簡潔にまとめる（最大150文字）
- コメントの内容に寄り添いながら、占い師らしい言葉で励ます
- 視聴者の名前は使わない
- ハッシュタグや絵文字は使わない
- 返信文のみを出力する（説明や前置きは不要）
"""


def generate_reply(client: anthropic.Anthropic, comment_text: str) -> str:
    """コメントに対して占い師キャラの返信を生成する。"""
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"以下のコメントに返信してください。\n\n{comment_text}",
            }
        ],
    )
    return message.content[0].text.strip()
