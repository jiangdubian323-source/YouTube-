"""GCS バックエンド: token.json と last_run.json を Cloud Storage で永続化する。

環境変数 GCS_BUCKET_NAME が設定されている場合のみ有効になる。
ローカル実行時はこのモジュールは使われない。
"""
from __future__ import annotations
import json
import os
from typing import Optional

_bucket = None


def _get_bucket():
    global _bucket
    if _bucket is None:
        from google.cloud import storage
        bucket_name = os.environ["GCS_BUCKET_NAME"]
        _bucket = storage.Client().bucket(bucket_name)
    return _bucket


def is_enabled() -> bool:
    return bool(os.environ.get("GCS_BUCKET_NAME"))


def read_text(blob_name: str) -> Optional[str]:
    """GCS からテキストを読み込む。存在しない場合は None を返す。"""
    blob = _get_bucket().blob(blob_name)
    if not blob.exists():
        return None
    return blob.download_as_text()


def write_text(blob_name: str, text: str) -> None:
    """GCS にテキストを書き込む。"""
    _get_bucket().blob(blob_name).upload_from_string(text, content_type="application/json")
