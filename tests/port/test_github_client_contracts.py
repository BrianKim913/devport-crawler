import asyncio
import time

import httpx
import pytest

from app.crawlers.port.client import GitHubPortClient
from app.crawlers.port.contracts import FetchState


def _transport_from_sequence(responses: list[httpx.Response]) -> httpx.MockTransport:
    queue = responses.copy()

    async def handler(_: httpx.Request) -> httpx.Response:
        if not queue:
            raise AssertionError("No more mock responses available")
        return queue.pop(0)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_get_repo_returns_ok_contract_for_200() -> None:
    transport = _transport_from_sequence(
        [
            httpx.Response(
                200,
                headers={"etag": '"repo-etag-v1"'},
                json={"full_name": "owner/repo", "stargazers_count": 42},
            )
        ]
    )
    client = GitHubPortClient(token="test", transport=transport, max_retries=2)

    result = await client.get_repo("owner", "repo")
    await client.aclose()

    assert result.state == FetchState.OK
    assert result.data is not None
    assert result.data["full_name"] == "owner/repo"
    assert result.etag == '"repo-etag-v1"'


@pytest.mark.asyncio
async def test_get_repo_returns_unchanged_contract_for_304() -> None:
    transport = _transport_from_sequence([httpx.Response(304, headers={"etag": '"repo-etag-v2"'})])
    client = GitHubPortClient(token="test", transport=transport, max_retries=2)

    result = await client.get_repo("owner", "repo", etag='"repo-etag-v1"')
    await client.aclose()

    assert result.state == FetchState.UNCHANGED
    assert result.data is None
    assert result.etag == '"repo-etag-v2"'


@pytest.mark.asyncio
async def test_list_releases_returns_empty_contract_for_empty_200() -> None:
    transport = _transport_from_sequence([httpx.Response(200, headers={"etag": '"release-etag"'}, json=[])])
    client = GitHubPortClient(token="test", transport=transport, max_retries=2)

    result = await client.list_releases("owner", "repo")
    await client.aclose()

    assert result.state == FetchState.EMPTY
    assert result.data == []
    assert result.etag == '"release-etag"'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,headers",
    [
        (429, {"retry-after": "0"}),
        (403, {"x-ratelimit-reset": str(int(time.time()))}),
    ],
)
async def test_rate_limited_responses_retry_then_succeed(status_code: int, headers: dict[str, str]) -> None:
    attempts: list[int] = []

    async def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(status_code, headers=headers)
        return httpx.Response(200, headers={"etag": '"ok-etag"'}, json={"full_name": "owner/repo"})

    async def fast_sleep(_: float) -> None:
        return None

    transport = httpx.MockTransport(handler)
    client = GitHubPortClient(
        token="test",
        transport=transport,
        max_retries=3,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.01,
        rate_limit_buffer_seconds=0,
    )

    original_sleep = asyncio.sleep
    asyncio.sleep = fast_sleep
    try:
        result = await client.get_repo("owner", "repo")
    finally:
        asyncio.sleep = original_sleep
        await client.aclose()

    assert result.state == FetchState.OK
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_rate_limit_failure_returns_failed_contract_after_retries() -> None:
    transport = _transport_from_sequence(
        [
            httpx.Response(429, headers={"retry-after": "0"}),
            httpx.Response(429, headers={"retry-after": "0"}),
        ]
    )
    client = GitHubPortClient(
        token="test",
        transport=transport,
        max_retries=2,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.01,
    )

    result = await client.get_repo("owner", "repo")
    await client.aclose()

    assert result.state == FetchState.FAILED
    assert result.status_code == 429
    assert result.error is not None
