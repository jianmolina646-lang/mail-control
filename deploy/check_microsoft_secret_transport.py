from __future__ import annotations

import os
from pathlib import Path

raw_value = ""
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("MICROSOFT_CLIENT_SECRET="):
        raw_value = line.split("=", 1)[1]
        break

container_value = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
print(f"raw_length={len(raw_value)}")
print(f"container_length={len(container_value)}")
print(f"transport_match={raw_value == container_value}")
print(f"looks_like_uuid={len(raw_value) == 36 and raw_value.count('-') == 4}")
