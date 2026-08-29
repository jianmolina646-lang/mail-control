from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx
from redis.asyncio import Redis

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
CACHE_SECONDS = 7 * 24 * 60 * 60
ALLOWED_IMAGE_TYPES = {
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class ImageProxyError(ValueError):
    pass


class _ImageSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        values = {name.lower(): value for name, value in attrs}
        source = values.get("src")
        if source and urlsplit(source).scheme.lower() in {"http", "https"}:
            self.sources.append(source)


def image_sources(html: str) -> list[str]:
    parser = _ImageSourceParser()
    parser.feed(html)
    parser.close()
    return parser.sources[:100]


def _public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


async def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ImageProxyError("unsupported image URL")
    if parsed.username or parsed.password:
        raise ImageProxyError("credentials are not allowed in image URLs")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise ImageProxyError("image host could not be resolved") from error
    resolved = {entry[4][0] for entry in addresses}
    if not resolved or any(not _public_ip(address) for address in resolved):
        raise ImageProxyError("private image hosts are blocked")


def _cache_key(url: str) -> str:
    return f"mail:image:{hashlib.sha256(url.encode()).hexdigest()}"


async def _cached(redis: Redis, url: str) -> tuple[bytes, str] | None:
    raw = await redis.get(_cache_key(url))
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
        media_type = value["type"]
        content = base64.b64decode(value["data"], validate=True)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if media_type not in ALLOWED_IMAGE_TYPES or len(content) > MAX_IMAGE_BYTES:
        return None
    return content, media_type


async def fetch_image(redis: Redis, url: str) -> tuple[bytes, str]:
    cached = await _cached(redis, url)
    if cached is not None:
        return cached

    current_url = url
    timeout = httpx.Timeout(10, connect=5)
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout,
        trust_env=False,
        headers={"User-Agent": "MailControl-ImageProxy/1.0", "Accept": "image/*"},
    ) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            await validate_public_url(current_url)
            async with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    if redirect_count >= MAX_REDIRECTS:
                        raise ImageProxyError("too many image redirects")
                    location = response.headers.get("location")
                    if not location:
                        raise ImageProxyError("invalid image redirect")
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code != 200:
                    raise ImageProxyError("image server rejected the request")
                media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if media_type not in ALLOWED_IMAGE_TYPES:
                    raise ImageProxyError("unsupported image type")
                declared_size = response.headers.get("content-length")
                if declared_size and int(declared_size) > MAX_IMAGE_BYTES:
                    raise ImageProxyError("image is too large")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise ImageProxyError("image is too large")
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not content:
                    raise ImageProxyError("empty image")
                encoded = json.dumps(
                    {"type": media_type, "data": base64.b64encode(content).decode("ascii")}
                )
                await redis.setex(_cache_key(url), CACHE_SECONDS, encoded)
                return content, media_type
    raise ImageProxyError("image could not be fetched")
