from __future__ import annotations

import pytest

from mail_control.modules.mail.image_proxy import (
    ImageProxyError,
    image_sources,
    validate_public_url,
)


def test_extracts_only_remote_image_sources() -> None:
    html = '<img src="https://cdn.example/a.png"><img src="cid:logo"><img src="data:image/png,x">'
    assert image_sources(html) == ["https://cdn.example/a.png"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/image.png",
        "http://[::1]/image.png",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "http://user:password@example.com/image.png",
    ],
)
async def test_blocks_unsafe_image_destinations(url: str) -> None:
    with pytest.raises(ImageProxyError):
        await validate_public_url(url)
