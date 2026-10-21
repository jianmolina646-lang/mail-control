from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import httpx
import pytest

from mail_control.modules.mail.gmail import (
    GmailClient,
    GmailError,
    GmailOAuth,
    GmailReauthRequired,
    GmailTransientError,
    gmail_retry_at,
)


def response(
    status: int,
    payload: Any = None,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        headers=headers,
        request=httpx.Request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile"),
    )


def test_retry_after_seconds_preserves_the_provider_deadline() -> None:
    before = datetime.now(UTC)
    deadline = gmail_retry_at(response(429, {}, headers={"Retry-After": "120"}))
    after = datetime.now(UTC)

    assert deadline is not None
    assert before + timedelta(seconds=120) <= deadline <= after + timedelta(seconds=120)


def test_retry_after_http_date_preserves_the_provider_deadline() -> None:
    deadline = datetime(2099, 10, 20, 12, 0, tzinfo=UTC)

    assert gmail_retry_at(
        response(503, {}, headers={"Retry-After": format_datetime(deadline, usegmt=True)})
    ) == deadline


def test_later_deadline_wins_when_google_returns_json_and_header() -> None:
    earlier = datetime(2099, 10, 20, 12, 0, tzinfo=UTC)
    later = earlier + timedelta(minutes=10)

    for header, body in ((earlier, later), (later, earlier)):
        result = gmail_retry_at(
            response(
                429,
                {"error": {"message": f"User-rate limit exceeded. Retry after {body.isoformat()}"}},
                headers={"Retry-After": format_datetime(header, usegmt=True)},
            )
        )
        assert result == later


@pytest.mark.parametrize("header", ["invalid", "nan", "inf", "-inf", "1e999", "9" * 100])
def test_malformed_retry_header_is_ignored_without_crashing(header: str) -> None:
    assert gmail_retry_at(response(429, {}, headers={"Retry-After": header})) is None


@pytest.mark.parametrize("payload", [[], "not an object", {"error": []}, {"error": None}])
def test_malformed_json_does_not_hide_valid_retry_header(payload: Any) -> None:
    deadline = datetime(2099, 10, 20, 12, 0, tzinfo=UTC)
    assert gmail_retry_at(
        response(429, payload, headers={"Retry-After": format_datetime(deadline, usegmt=True)})
    ) == deadline


def test_timezone_less_google_deadline_cannot_crash_aware_datetime_comparison() -> None:
    deadline = gmail_retry_at(
        response(429, {"error": {"message": "Retry after 2099-10-20T12:00:00"}})
    )
    # Reject the ambiguous timestamp or normalize it to UTC, never return a naive date.
    assert deadline is None or deadline.utcoffset() is not None


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_temporary_oauth_errors_do_not_request_reauthorization(status: int) -> None:
    before = datetime.now(UTC)
    error = GmailOAuth._token_error(
        response(
            status,
            {"error": "invalid_grant", "error_description": "temporary upstream failure"},
            headers={"Retry-After": "120"},
        ),
        "refresh token",
    )
    after = datetime.now(UTC)

    assert isinstance(error, GmailTransientError)
    assert not isinstance(error, GmailReauthRequired)
    assert error.retry_at is not None
    assert before + timedelta(seconds=120) <= error.retry_at <= after + timedelta(seconds=120)


def test_real_invalid_grant_still_requests_reauthorization_without_leaking_description() -> None:
    error = GmailOAuth._token_error(
        response(
            400,
            {"error": "invalid_grant", "error_description": "PRIVATE_DESCRIPTION_SENTINEL"},
        ),
        "refresh token",
    )

    assert isinstance(error, GmailReauthRequired)
    assert error.code == "invalid_grant"
    assert "PRIVATE_DESCRIPTION_SENTINEL" not in str(error)


@pytest.mark.parametrize("code", ["invalid_client", "unauthorized_client", "invalid_scope"])
def test_oauth_configuration_errors_are_not_customer_reauthorization_errors(code: str) -> None:
    error = GmailOAuth._token_error(
        response(400, {"error": code, "error_description": "PRIVATE_DESCRIPTION_SENTINEL"}),
        "refresh token",
    )

    assert isinstance(error, GmailError)
    assert not isinstance(error, GmailReauthRequired | GmailTransientError)
    assert error.code == code
    assert "PRIVATE_DESCRIPTION_SENTINEL" not in str(error)


@pytest.mark.parametrize(
    "payload",
    [[], "PRIVATE_PAYLOAD_SENTINEL", {"error": {"message": "PRIVATE_PAYLOAD_SENTINEL"}},
     {"error": "PRIVATE_PAYLOAD_SENTINEL"}],
)
def test_unknown_oauth_payload_is_safe_and_cannot_break_error_classification(payload: Any) -> None:
    error = GmailOAuth._token_error(response(400, payload), "refresh token")

    assert isinstance(error, GmailError)
    assert not isinstance(error, GmailReauthRequired)
    assert "PRIVATE_PAYLOAD_SENTINEL" not in str(error)
    assert "PRIVATE_PAYLOAD_SENTINEL" not in (error.code or "")


@pytest.mark.asyncio
async def test_long_retry_after_releases_worker_and_preserves_retry_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "120"},
            json={"error": {"message": "Too many requests"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    async def unexpected_sleep(delay: float) -> None:
        raise AssertionError("Long provider cooldown must not occupy a worker with sleep")

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr("mail_control.modules.mail.gmail.asyncio.sleep", unexpected_sleep)
    before = datetime.now(UTC)

    with pytest.raises(GmailTransientError) as caught:
        await GmailClient("fake-test-token").profile()

    after = datetime.now(UTC)
    assert requests == 1
    assert caught.value.retry_at is not None
    expected_min = before + timedelta(seconds=120)
    expected_max = after + timedelta(seconds=120)
    assert expected_min <= caught.value.retry_at <= expected_max


@pytest.mark.asyncio
async def test_permanent_forbidden_is_not_retried_or_mislabelled_as_reauthorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "insufficientPermissions"}]}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(httpx.HTTPStatusError):
        await GmailClient("fake-test-token").profile()

    assert requests == 1


@pytest.mark.asyncio
async def test_persistent_503_has_bounded_retries_and_safe_actionable_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            503,
            json={"error": {"message": "PRIVATE_PROVIDER_PAYLOAD_SENTINEL"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr("mail_control.modules.mail.gmail.asyncio.sleep", fake_sleep)

    with pytest.raises(GmailTransientError) as caught:
        await GmailClient("fake-test-token").profile()

    assert requests == 4
    assert len(delays) == 3
    assert all(0 <= delay <= 30 for delay in delays)
    assert "503" in str(caught.value)
    assert "PRIVATE_PROVIDER_PAYLOAD_SENTINEL" not in str(caught.value)
    assert "fake-test-token" not in str(caught.value)


@pytest.mark.asyncio
async def test_refresh_transport_failure_is_transient_and_does_not_expose_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Request failed for https://private.example/token?refresh_token="
            "PRIVATE_REFRESH_TOKEN_SENTINEL; secret=PRIVATE_CLIENT_SECRET_SENTINEL",
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr("mail_control.modules.mail.gmail.asyncio.sleep", fake_sleep)
    oauth = GmailOAuth(
        object(),  # type: ignore[arg-type]
        client_id="fake-client-id",
        client_secret="PRIVATE_CLIENT_SECRET_SENTINEL",
        redirect_uri="https://example.com/callback",
    )

    with pytest.raises(GmailTransientError) as caught:
        await oauth.refresh_access_token("PRIVATE_REFRESH_TOKEN_SENTINEL")

    assert "PRIVATE_REFRESH_TOKEN_SENTINEL" not in str(caught.value)
    assert "PRIVATE_CLIENT_SECRET_SENTINEL" not in str(caught.value)
    assert "private.example" not in str(caught.value)
    assert "https://" not in str(caught.value)


@pytest.mark.asyncio
async def test_short_json_retry_deadline_is_honored_before_next_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            deadline = datetime.now(UTC) + timedelta(seconds=5)
            return httpx.Response(
                429,
                json={"error": {"message": f"Retry after {deadline.isoformat()}"}},
                request=request,
            )
        assert len(delays) == 1
        return httpx.Response(200, json={"historyId": "fake-history"}, request=request)

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr("mail_control.modules.mail.gmail.asyncio.sleep", fake_sleep)

    assert await GmailClient("fake-test-token").profile() == {"historyId": "fake-history"}
    assert requests == 2
    assert len(delays) == 1
    # A first-attempt exponential jitter delay (0-1 s) would violate Google's 5 s deadline.
    assert 3 <= delays[0] <= 7
