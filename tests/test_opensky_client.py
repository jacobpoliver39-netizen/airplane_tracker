import json

import pytest

from opensky_client import OpenSkyClient, OpenSkyRateLimitError


class FakeResponse:
    """
    A requests.Response stand-in. The body is `payload` as JSON, or raw
    `body` bytes, served in chunks like a streamed response.
    """

    def __init__(self, status_code=200, payload=None, headers=None, body=None):
        self.status_code = status_code
        self._payload = payload
        self._body = body if body is not None else json.dumps(payload).encode()
        self.headers = headers or {}
        self.bytes_served = 0
        self.closed = False

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self._body), chunk_size):
            chunk = self._body[start:start + chunk_size]
            self.bytes_served += len(chunk)
            yield chunk

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, get_responses, post_responses=()):
        self._get_responses = list(get_responses)
        self._post_responses = list(post_responses)
        self.get_calls = []
        self.post_calls = 0

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        self.get_calls.append(headers or {})
        return self._get_responses.pop(0)

    def post(self, url, data=None, timeout=None):
        self.post_calls += 1
        return self._post_responses.pop(0)

    def close(self):
        pass


def token_response(token="token-1"):
    return FakeResponse(payload={"access_token": token, "expires_in": 1800})


def test_anonymous_request_returns_time_and_states():
    session = FakeSession([FakeResponse(payload={"time": 1000, "states": []})])
    client = OpenSkyClient(session=session, client_id=None, client_secret=None)

    assert client.get_states() == (1000, [])
    assert "Authorization" not in session.get_calls[0]


def test_null_states_are_returned_as_none():
    session = FakeSession([FakeResponse(payload={"time": 1000, "states": None})])
    client = OpenSkyClient(session=session, client_id=None, client_secret=None)

    assert client.get_states() == (1000, None)


@pytest.mark.parametrize(
    "payload",
    [[], {"time": 1000}, {"time": 1000, "states": "bad"}],
)
def test_unexpected_response_shape_raises_value_error(payload):
    session = FakeSession([FakeResponse(payload=payload)])
    client = OpenSkyClient(session=session, client_id=None, client_secret=None)

    with pytest.raises(ValueError):
        client.get_states()


def test_rate_limit_raises_with_retry_after():
    session = FakeSession([
        FakeResponse(
            status_code=429,
            headers={"X-Rate-Limit-Retry-After-Seconds": "120"},
        )
    ])
    client = OpenSkyClient(session=session, client_id=None, client_secret=None)

    with pytest.raises(OpenSkyRateLimitError) as error:
        client.get_states()

    assert error.value.retry_after_seconds == 120


def test_authenticated_client_sends_and_reuses_token():
    session = FakeSession(
        [
            FakeResponse(payload={"time": 1, "states": []}),
            FakeResponse(payload={"time": 2, "states": []}),
        ],
        [token_response()],
    )
    client = OpenSkyClient(session=session, client_id="id", client_secret="secret")

    client.get_states()
    client.get_states()

    assert session.post_calls == 1
    assert all(
        call["Authorization"] == "Bearer token-1" for call in session.get_calls
    )


def test_expired_token_is_refreshed_once_on_401():
    session = FakeSession(
        [
            FakeResponse(status_code=401),
            FakeResponse(payload={"time": 1, "states": []}),
        ],
        [token_response("old"), token_response("new")],
    )
    client = OpenSkyClient(session=session, client_id="id", client_secret="secret")

    assert client.get_states() == (1, [])
    assert session.get_calls[-1]["Authorization"] == "Bearer new"


# --- response size cap ------------------------------------------------------

def anonymous_client(response, limit=1000):
    return OpenSkyClient(
        session=FakeSession([response]),
        client_id=None,
        client_secret=None,
        max_response_bytes=limit,
    )


def test_response_within_size_limit_is_parsed():
    response = FakeResponse(payload={"time": 1000, "states": []})

    assert anonymous_client(response).get_states() == (1000, [])
    assert response.closed


def test_oversized_body_is_refused_without_reading_it_all():
    big = b'{"time": 1000, "states": [' + b'0,' * 1_000_000 + b'0]}'
    response = FakeResponse(body=big)

    with pytest.raises(ValueError, match="exceeds"):
        anonymous_client(response, limit=100_000).get_states()

    # Stopped at the first chunk past the limit, not after 2 MB.
    assert response.bytes_served <= 100_000 + 64 * 1024
    assert response.closed


def test_declared_oversized_body_is_refused_before_reading():
    response = FakeResponse(
        payload={"time": 1000, "states": []},
        headers={"Content-Length": str(50_000_000)},
    )

    with pytest.raises(ValueError, match="limit"):
        anonymous_client(response).get_states()

    assert response.bytes_served == 0


def test_default_limit_is_ten_megabytes():
    import config

    assert config.MAX_RESPONSE_BYTES == 10 * 1024 * 1024
    assert OpenSkyClient(session=FakeSession([]))._max_response_bytes == config.MAX_RESPONSE_BYTES
