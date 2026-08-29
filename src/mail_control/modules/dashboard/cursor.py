from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID


def encode_cursor(timestamp: datetime, item_id: UUID) -> str:
    raw = json.dumps(
        {"timestamp": timestamp.isoformat(), "id": str(item_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(cursor + padding))
        return datetime.fromisoformat(data["timestamp"]), UUID(data["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid pagination cursor") from error
