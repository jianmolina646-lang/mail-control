from __future__ import annotations

from typing import Any

import httpx

MAX_PROVIDER_RESPONSE_BYTES = 30 * 1024 * 1024


async def bounded_request(
    client: httpx.AsyncClient, method: str, url: str, *,
    params: dict[str, str | int] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Bound decoded response bytes before JSON/base64 allocation."""
    async with client.stream(method, url, params=params, json=json, headers=headers) as response:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > MAX_PROVIDER_RESPONSE_BYTES:
                raise ValueError("Provider response exceeds the 30 MiB download limit")
            body.extend(chunk)
        # Content was decoded by aiter_bytes; avoid decoding a second time.
        response_headers = dict(response.headers)
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)
        return httpx.Response(
            response.status_code, headers=response_headers, content=bytes(body),
            request=response.request,
        )
