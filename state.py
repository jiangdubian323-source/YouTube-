"""前回実行時刻の保存・読み込み。GCS または ローカルファイルに保存する。"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gcs_backend

STATE_FILE = Path("last_run.json")
STATE_BLOB = "last_run.json"


def load_last_run() -> str:
    """前回実行時刻を RFC 3339 形式で返す。記録がなければ1時間前を返す。"""
    text = None
    if gcs_backend.is_enabled():
        text = gcs_backend.read_text(STATE_BLOB)
    elif STATE_FILE.exists():
        text = STATE_FILE.read_text()

    if text:
        return json.loads(text)["last_run"]

    # 初回起動時は直近1時間のコメントのみ対象にする
    one_hour_ago = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    return one_hour_ago.isoformat().replace("+00:00", "Z")


def save_last_run(dt: datetime) -> None:
    """実行時刻を保存する。"""
    text = json.dumps({"last_run": dt.isoformat().replace("+00:00", "Z")})
    if gcs_backend.is_enabled():
        gcs_backend.write_text(STATE_BLOB, text)
    else:
        STATE_FILE.write_text(text)
