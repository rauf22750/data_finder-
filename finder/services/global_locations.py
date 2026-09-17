import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LocationDirectoryError(Exception):
    pass


class GlobalLocationService:
    """Country/state/city directory backed by CountriesNow's public API."""

    BASE_URL = "https://countriesnow.space/api/v0.1/countries"

    def __init__(self, session=None, timeout=None):
        self.session = session or requests.Session()
        self.timeout = timeout or settings.REQUEST_TIMEOUT

    def _get(self, path, params):
        try:
            response = self.session.get(f"{self.BASE_URL}/{path}", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Global location directory request failed: %s", exc)
            raise LocationDirectoryError("The global location directory is temporarily unavailable.") from exc
        if payload.get("error"):
            raise LocationDirectoryError(payload.get("msg") or "Location information was not found.")
        return payload.get("data")

    def provinces(self, country):
        data = self._get("states/q", {"country": country}) or {}
        return sorted(
            [{"name": item["name"], "code": item.get("state_code", "")} for item in data.get("states", []) if item.get("name")],
            key=lambda item: item["name"].casefold(),
        )

    def cities(self, country, province):
        data = self._get("state/cities/q", {"country": country, "state": province}) or []
        return sorted({str(name).strip() for name in data if str(name).strip()}, key=str.casefold)
