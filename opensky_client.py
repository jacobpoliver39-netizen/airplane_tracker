"""Small client for the OpenSky /states/all endpoint."""

import json
import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


class OpenSkyRateLimitError(Exception):
    """Raised when OpenSky reports that the API credits are used up."""

    def __init__(self, retry_after_seconds):
        super().__init__(
            f"OpenSky rate limit reached, retry after {retry_after_seconds} s"
        )
        self.retry_after_seconds = retry_after_seconds


class OpenSkyClient:
    """
    Fetches state vectors, using OAuth2 client credentials when they
    are configured and anonymous access otherwise.
    """

    def __init__(
        self,
        session=None,
        client_id=config.OPENSKY_CLIENT_ID,
        client_secret=config.OPENSKY_CLIENT_SECRET,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        max_response_bytes=config.MAX_RESPONSE_BYTES,
    ):
        self._session = session if session is not None else requests.Session()
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes
        self._token = None
        self._token_expires_at = 0.0

    @property
    def authenticated(self):
        return bool(self._client_id and self._client_secret)

    def close(self):
        self._session.close()

    def seconds_until_next_poll(self):
        return config.POLL_INTERVAL_SECONDS

    def get_states(self, bounding_box=config.BOUNDING_BOX):
        """
        Return (response_time, states) from OpenSky.

        states is a list of raw state arrays, or None when OpenSky has no
        aircraft in the area. Raises requests.RequestException,
        ValueError for an unexpected response shape or a body larger
        than max_response_bytes, or OpenSkyRateLimitError.
        """
        response = self._request_states(bounding_box)

        # A 401 means the token expired early; refresh once and retry.
        if response.status_code == 401 and self.authenticated:
            response.close()
            self._token = None
            response = self._request_states(bounding_box)

        if response.status_code == 429:
            retry_after = response.headers.get(
                "X-Rate-Limit-Retry-After-Seconds"
            )
            try:
                retry_after = int(retry_after)
            except (TypeError, ValueError):
                retry_after = None
            response.close()
            raise OpenSkyRateLimitError(retry_after)

        try:
            response.raise_for_status()
            data = self._read_json(response)
        finally:
            response.close()

        if not isinstance(data, dict) or "states" not in data:
            raise ValueError("Unexpected OpenSky response structure")

        states = data["states"]

        if states is not None and not isinstance(states, list):
            raise ValueError("OpenSky states must be a list or null")

        return data.get("time"), states

    def _request_states(self, bounding_box):
        headers = {}

        if self.authenticated:
            headers["Authorization"] = f"Bearer {self._get_token()}"

        # Streamed, so the body is only read through _read_json's cap.
        return self._session.get(
            config.OPENSKY_STATES_URL,
            params=bounding_box,
            headers=headers,
            timeout=self._timeout,
            stream=True,
        )

    def _read_json(self, response):
        """
        Parse the body as JSON, refusing to read more than
        max_response_bytes. The limit applies to the decompressed body,
        so a small gzip response that expands enormously is refused too.
        """
        limit = self._max_response_bytes
        declared = response.headers.get("Content-Length")

        if declared is not None and declared.isdigit() and int(declared) > limit:
            raise ValueError(
                f"OpenSky response is {int(declared):,} bytes; limit is {limit:,}"
            )

        body = bytearray()

        for chunk in response.iter_content(chunk_size=64 * 1024):
            body += chunk

            if len(body) > limit:
                raise ValueError(f"OpenSky response exceeds {limit:,} bytes")

        return json.loads(body)

    def _get_token(self):
        # Refresh a minute early so a request never carries an
        # about-to-expire token.
        if self._token is not None and time.time() < self._token_expires_at - 60:
            return self._token

        response = self._session.post(
            config.OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        try:
            self._token = payload["access_token"]
        except (TypeError, KeyError) as error:
            raise ValueError("OpenSky token response has no access_token") from error

        self._token_expires_at = time.time() + float(
            payload.get("expires_in", 1800)
        )
        logger.info("Obtained OpenSky access token")
        return self._token
