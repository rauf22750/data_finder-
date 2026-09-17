import logging
import re
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class OpenStreetMapError(Exception):
    """A safe error that may be displayed to the user."""


class OpenStreetMapService:
    """Best-effort business search using Nominatim and Overpass public APIs."""

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    CATEGORY_FILTERS = {
        "restaurant": '["amenity"="restaurant"]',
        "restaurants": '["amenity"="restaurant"]',
        "dentist": '["amenity"="dentist"]',
        "dentists": '["amenity"="dentist"]',
        "hotel": '["tourism"="hotel"]',
        "hotels": '["tourism"="hotel"]',
        "hospital": '["amenity"="hospital"]',
        "hospitals": '["amenity"="hospital"]',
        "school": '["amenity"="school"]',
        "schools": '["amenity"="school"]',
        "car dealer": '["shop"="car"]',
        "car dealers": '["shop"="car"]',
        "mobile shop": '["shop"="mobile_phone"]',
        "mobile shops": '["shop"="mobile_phone"]',
        "electronics store": '["shop"="electronics"]',
        "electronics stores": '["shop"="electronics"]',
        "software company": '["office"="it"]',
        "software companies": '["office"="it"]',
        "software houses": '["office"~"^(it|company)$"]',
        "property and real estate": '["office"="estate_agent"]',
        "wood and furniture businesses": '["shop"~"^(furniture|carpenter)$"]',
        "e-commerce businesses": '["office"~"^(company|it)$"]',
    }

    def __init__(self, timeout=None, session=None):
        self.timeout = timeout or settings.REQUEST_TIMEOUT
        self.session = session or requests.Session()
        self.headers = {"User-Agent": settings.OSM_USER_AGENT, "Accept-Language": "en"}
        self.overpass_url = settings.OSM_OVERPASS_URL
        self.overpass_urls = list(dict.fromkeys([self.overpass_url, *settings.OSM_OVERPASS_FALLBACKS]))

    def _get(self, url, **kwargs):
        try:
            response = self.session.get(url, timeout=self.timeout, headers=self.headers, **kwargs)
        except requests.Timeout as exc:
            raise OpenStreetMapError("OpenStreetMap took too long to respond. Please try again.") from exc
        except requests.RequestException as exc:
            logger.exception("OpenStreetMap network error")
            raise OpenStreetMapError("Could not connect to OpenStreetMap. Please try again.") from exc
        if response.status_code == 429:
            raise OpenStreetMapError("The free OpenStreetMap service is busy. Please wait and try again.")
        if not response.ok:
            logger.error("OpenStreetMap error %s: %s", response.status_code, response.text[:500])
            raise OpenStreetMapError("OpenStreetMap could not complete this search.")
        try:
            return response.json()
        except ValueError as exc:
            raise OpenStreetMapError("OpenStreetMap returned an invalid response.") from exc

    def geocode_city(self, city, country):
        params = {"q": ", ".join(part for part in [city, country] if part), "format": "jsonv2", "limit": 1, "addressdetails": 1}
        if settings.OSM_CONTACT_EMAIL:
            params["email"] = settings.OSM_CONTACT_EMAIL
        data = self._get(self.NOMINATIM_URL, params=params)
        if not data:
            raise OpenStreetMapError("City or country was not found on OpenStreetMap.")
        return [float(value) for value in data[0]["boundingbox"]]

    def _overpass(self, query):
        last_error = None
        for url in self.overpass_urls:
            try:
                return self._get(url, params={"data": query})
            except OpenStreetMapError as exc:
                last_error = exc
                logger.warning("Overpass endpoint failed; trying fallback: %s", url)
        raise last_error or OpenStreetMapError("No OpenStreetMap query endpoint is configured.")

    @staticmethod
    def _safe_regex(value):
        return re.escape(value.strip())[:120]

    def _overpass_query(self, bbox, category, keyword, limit):
        south, north, west, east = bbox
        category_key = category.strip().lower()
        known_filter = self.CATEGORY_FILTERS.get(category_key)
        name_term = keyword.strip() or ("" if known_filter else category.strip())
        name_filter = f'["name"~"{self._safe_regex(name_term)}",i]' if name_term else '["name"]'
        if known_filter:
            selector = known_filter + name_filter
        else:
            term = self._safe_regex(category)
            selector = f'["name"][~"^(amenity|shop|office|tourism|healthcare|craft)$"~"{term}",i]'
        bbox_text = f"{south},{west},{north},{east}"
        return f"[out:json][timeout:{min(60, self.timeout)}];nwr{selector}({bbox_text});out tags center {limit};"

    def overpass_search(self, bbox, category, keyword, limit):
        query = self._overpass_query(bbox, category, keyword, limit)
        return self._overpass(query).get("elements", [])

    def list_cities(self, country_code, limit=1000):
        """Return mapped cities/towns for an ISO-3166 alpha-2 country code."""
        code = country_code.upper()
        query = (
            f'[out:json][timeout:{min(60, self.timeout)}];'
            f'area["ISO3166-1"="{code}"]["admin_level"="2"]->.country;'
            f'node["place"~"^(city|town)$"](area.country);out tags {limit};'
        )
        elements = self._overpass(query).get("elements", [])
        names = {
            (item.get("tags") or {}).get("name:en") or (item.get("tags") or {}).get("name")
            for item in elements
        }
        return sorted((name.strip() for name in names if name and name.strip()), key=str.casefold)

    def list_areas(self, country, province, city, limit=300):
        bbox = self.geocode_city(", ".join(part for part in [city, province] if part), country)
        south, north, west, east = bbox
        query = (
            f'[out:json][timeout:{min(45, self.timeout)}];'
            f'node["place"~"^(suburb|neighbourhood|quarter|borough|district)$"]'
            f'({south},{west},{north},{east});out tags {limit};'
        )
        elements = self._overpass(query).get("elements", [])
        names = {(item.get("tags") or {}).get("name:en") or (item.get("tags") or {}).get("name") for item in elements}
        return sorted((name.strip() for name in names if name and name.strip()), key=str.casefold)

    @staticmethod
    def normalize_place(element, category):
        tags = element.get("tags") or {}
        center = element.get("center") or element
        address_parts = [
            " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")])),
            tags.get("addr:suburb"), tags.get("addr:city"), tags.get("addr:postcode"),
        ]
        address = ", ".join(part for part in address_parts if part) or tags.get("addr:full") or "N/A"
        website = tags.get("website") or tags.get("contact:website") or "N/A"
        if website != "N/A" and not website.startswith(("http://", "https://")):
            website = "https://" + website
        osm_type, osm_id = element.get("type", "node"), element.get("id")
        latitude, longitude = center.get("lat"), center.get("lon")
        google_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}" if latitude is not None and longitude is not None else ""
        return {
            "place_id": f"osm:{osm_type}:{osm_id}",
            "name": (tags.get("name:en") or tags.get("name") or "N/A").strip(),
            "phone": (tags.get("phone") or tags.get("contact:phone") or "N/A").strip(),
            "email": (tags.get("email") or tags.get("contact:email") or "N/A").strip(),
            "address": address.strip(), "website": website.strip(),
            "category": (tags.get("amenity") or tags.get("shop") or tags.get("office") or tags.get("tourism") or category).replace("_", " ").title(),
            "latitude": latitude, "longitude": longitude,
            "google_maps_url": google_url,
            "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        }

    def search_businesses(self, country, city, category, keyword="", limit=20, province="", area=""):
        limit = min(int(limit), settings.MAX_RESULTS_PER_SEARCH)
        bbox = self.geocode_city(city, country)
        elements = self.overpass_search(bbox, category, keyword, limit)
        results, seen = [], set()
        for element in elements:
            item = self.normalize_place(element, category)
            if item["place_id"] not in seen and item["name"] != "N/A":
                seen.add(item["place_id"])
                results.append(item)
            if len(results) >= limit:
                break
        return results
