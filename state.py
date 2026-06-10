"""前回実行時刻の保存・読み込み。"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path("last_run.json")


def load_last_run() -> str:
    """前回実行時刻を RFC 3339 形式で返す。ファイルがなければ1時間前を返す。"""
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        return data["last_run"]
    # 初回起動時は直近1時間のコメントのみ対象にする
    one_hour_ago = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    one_hour_ago -= timedelta(hours=1)
    return one_hour_ago.isoformat().replace("+00:00", "Z")


def save_last_run(dt: datetime) -> None:
    """実行時刻を保存する。"""
    STATE_FILE.write_text(json.dumps({"last_run": dt.isoformat().replace("+00:00", "Z")}))
