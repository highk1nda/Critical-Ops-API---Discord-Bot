import asyncio
import logging

import aiohttp

from config.constants import API_URL, API_TIMEOUT

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.5  # seconds; doubles on each attempt (0.5 → 1.0 → 2.0)


class ProfileApiClient:
    """Thin async wrapper around the Critical Force profile API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def fetch_profile(self, username: str) -> dict | None:
        """
        Fetch a single player profile by username.
        Retries up to _MAX_RETRIES times with exponential backoff.
        Returns None if the profile cannot be retrieved.
        """
        url = f"{API_URL}?usernames={username}"
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with self._session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        logger.warning(
                            "fetch_profile: HTTP %s for user=%r (attempt %d/%d)",
                            response.status, username, attempt, _MAX_RETRIES,
                        )
                        return None

                    data = await response.json()

                    if not isinstance(data, list) or not data:
                        logger.warning(
                            "fetch_profile: empty or invalid payload for user=%r", username,
                        )
                        return None

                    return data[0]

            except asyncio.TimeoutError:
                logger.warning(
                    "fetch_profile: timeout for user=%r (attempt %d/%d)",
                    username, attempt, _MAX_RETRIES,
                )
            except aiohttp.ClientError as exc:
                logger.warning(
                    "fetch_profile: client error for user=%r — %s (attempt %d/%d)",
                    username, exc, attempt, _MAX_RETRIES,
                )

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

        logger.error(
            "fetch_profile: all %d attempts exhausted for user=%r", _MAX_RETRIES, username,
        )
        return None
