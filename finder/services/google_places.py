import logging
import time
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class PlacesError(Exception):
    """Safe, user-facing Places API error."""

class GooglePlacesService:
    SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
    FIELDS = ",".join([
        "places.id", "places.displayName", "places.formattedAddress",
        "places.internationalPhoneNumber", "places.nationalPhoneNumber",
        "places.websiteUri", "places.location", "places.primaryType",
        "places.primaryTypeDisplayName", "places.googleMapsUri", "nextPageToken",
    ])

    def __init__(self, api_key=None, timeout=None, session=None):
        self.api_key = api_key if api_key is not None else settings.GOOGLE_MAPS_API_KEY
        self.timeout = timeout or settings.REQUEST_TIMEOUT
        self.session = session or requests.Session()

    def _headers(self, fields):
        return {"Content-Type": "application/json", "X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": fields}

    def _request(self, method, url, **kwargs):
        if not self.api_key:
            raise PlacesError("Google Places API is not configured correctly.")
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.Timeout as exc:
            logger.exception("Google Places request timed out")
            raise PlacesError("Google Places took too long to respond. Please try again.") from exc
        except requests.RequestException as exc:
            logger.exception("Google Places network error")
            raise PlacesError("Could not connect to Google Places. Please try again.") from exc
        if response.status_code == 429:
            raise PlacesError("Google Places rate limit was reached. Please try again later.")
        if response.status_code in (401, 403):
            logger.error("Google Places authorization error: %s", response.text[:500])
            raise PlacesError("Google Places API is not configured correctly.")
        if not response.ok:
            logger.error("Google Places API error %s: %s", response.status_code, response.text[:500])
            raise PlacesError("Google Places could not complete this search.")
        try:
            return response.json()
        except ValueError as exc:
            raise PlacesError("Google Places returned an invalid response.") from exc

    def text_search(self, query, page_token=None, page_size=20):
        payload = {"textQuery": query, "pageSize": min(20, page_size)}
        if page_token:
            payload["pageToken"] = page_token
        return self._request("POST", self.SEARCH_URL, headers=self._headers(self.FIELDS), json=payload)

    def get_place_details(self, place_id):
        fields = "id,displayName,formattedAddress,internationalPhoneNumber,nationalPhoneNumber,websiteUri,location,primaryType,primaryTypeDisplayName,googleMapsUri"
        return self._request("GET", self.DETAILS_URL.format(place_id=place_id), headers=self._headers(fields))

    @staticmethod
    def normalize_place(place):
        location = place.get("location") or {}
        primary = place.get("primaryTypeDisplayName") or {}
        name = place.get("displayName") or {}
        return {
            "place_id": str(place.get("id") or "").strip(),
            "name": str(name.get("text") or "N/A").strip(),
            "phone": str(place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or "N/A").strip(),
            "address": str(place.get("formattedAddress") or "N/A").strip(),
            "website": str(place.get("websiteUri") or "N/A").strip(),
            "category": str(primary.get("text") or place.get("primaryType") or "N/A").strip(),
            "latitude": location.get("latitude"), "longitude": location.get("longitude"),
            "google_maps_url": str(place.get("googleMapsUri") or "").strip(),
        }

    def search_businesses(self, country, city, category, keyword="", limit=20, province="", area=""):
        limit = min(int(limit), settings.MAX_RESULTS_PER_SEARCH)
        location = ", ".join(part for part in [area if not area.lower().startswith("all ") else "", city, province if not province.lower().startswith("all ") else "", country] if part)
        query = " ".join(part for part in [keyword, category, "in", location] if part).strip()
        results, seen, token = [], set(), None
        while len(results) < limit:
            data = self.text_search(query, token, min(20, limit - len(results)))
            for raw in data.get("places", []):
                item = self.normalize_place(raw)
                if item["place_id"] and item["place_id"] not in seen:
                    seen.add(item["place_id"])
                    results.append(item)
                    if len(results) >= limit:
                        break
            token = data.get("nextPageToken")
            if not token:
                break
            time.sleep(0.15)
        return results
