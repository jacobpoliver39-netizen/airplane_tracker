import pytest

from opensky_client import OpenSkyClient, OpenSkyRateLimitError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload

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

    def get(self, url, params=None, headers=None, timeout=None):
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
