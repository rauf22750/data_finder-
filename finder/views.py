import json
import logging
import re
import time
import pycountry
import geonamescache
from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from .forms import SearchForm
from .location_data import CATEGORY_CHOICES
from .services.google_places import GooglePlacesService, PlacesError
from .services.osm_places import OpenStreetMapError, OpenStreetMapService
from .services.global_locations import GlobalLocationService, LocationDirectoryError
from .services.json_store import JSONDataStore
from .services.website_enrichment import WebsiteEmailEnricher
from .utils.export import csv_response, excel_response

logger = logging.getLogger(__name__)
store = JSONDataStore()

@ensure_csrf_cookie
def react_app(request):
    return render(request, "react_app.html")

def dashboard_api(request):
    countries = sorted(
        ({"name": country.name, "code": country.alpha_2} for country in pycountry.countries),
        key=lambda item: item["name"],
    )
    return JsonResponse({"success": True, "stats": store.stats(), "countries": countries,
                         "categories": [{"value": value, "label": label} for value, label in CATEGORY_CHOICES],
                         "latest_search": store.get_search()})

def searches_api(request):
    searches = store.searches()
    return JsonResponse({"success": True, "searches": [{k: v for k, v in item.items() if k != "results"} for item in searches]})

def search_detail_api(request, search_id=None):
    search_item = store.get_search(search_id)
    if not search_item:
        return JsonResponse({"success": False, "error": "Search results were not found."}, status=404)
    return JsonResponse({"success": True, "search": search_item})

def result_item_api(request, search_id, result_id):
    if request.method == "PATCH":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid edit data."}, status=400)
        allowed = {"name", "phone", "email", "address", "website", "category", "area", "city", "province", "country", "latitude", "longitude", "google_maps_url"}
        updates = {key: str(value).strip() for key, value in payload.items() if key in allowed and value is not None}
        if "name" in updates and not updates["name"]:
            return JsonResponse({"success": False, "error": "Business name cannot be empty."}, status=400)
        result = store.update_result(search_id, result_id, updates)
        if not result:
            return JsonResponse({"success": False, "error": "Business record was not found."}, status=404)
        return JsonResponse({"success": True, "result": result})
    if request.method == "DELETE":
        if not store.delete_result(search_id, result_id):
            return JsonResponse({"success": False, "error": "Business record was not found."}, status=404)
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)

def _serialize(business):
    return business

def dashboard(request):
    stats = store.stats()
    countries = sorted(
        ({"name": country.name, "code": country.alpha_2} for country in pycountry.countries),
        key=lambda item: item["name"],
    )
    latest_search = store.get_search()
    return render(request, "dashboard.html", {"stats": stats, "form": SearchForm(initial={"limit": 20}), "countries": countries, "categories": CATEGORY_CHOICES, "latest_search": latest_search})

def provinces(request):
    country_code = request.GET.get("country", "").strip().upper()
    if len(country_code) != 2 or pycountry.countries.get(alpha_2=country_code) is None:
        return JsonResponse({"success": False, "error": "Please select a valid country."}, status=400)
    country = pycountry.countries.get(alpha_2=country_code)
    cache_key = f"global-provinces:{country_code}"
    subdivisions = cache.get(cache_key)
    if subdivisions is None:
        try:
            subdivisions = GlobalLocationService(timeout=20).provinces(country.name)
        except LocationDirectoryError:
            subdivisions = sorted(
                ({"name": item.name, "code": item.code} for item in pycountry.subdivisions.get(country_code=country_code)),
                key=lambda item: item["name"].casefold(),
            )
        cache.set(cache_key, subdivisions, 60 * 60 * 24 * 30)
    return JsonResponse({"success": True, "provinces": subdivisions})

def cities(request):
    country_code = request.GET.get("country", "").strip().upper()
    if len(country_code) != 2 or pycountry.countries.get(alpha_2=country_code) is None:
        return JsonResponse({"success": False, "error": "Please select a valid country."}, status=400)
    province = request.GET.get("province", "").strip()
    cache_key = f"cities:{country_code}:{province}"
    city_names = cache.get(cache_key)
    if city_names is None:
        country = pycountry.countries.get(alpha_2=country_code)
        try:
            city_names = GlobalLocationService(timeout=20).cities(country.name, province)
        except LocationDirectoryError:
            directory = geonamescache.GeonamesCache().get_cities().values()
            city_names = sorted(
                {item["name"].strip() for item in directory if item.get("countrycode") == country_code and item.get("name")},
                key=str.casefold,
            )
        cache.set(cache_key, city_names, 60 * 60 * 24 * 30)
    return JsonResponse({"success": True, "cities": city_names})

def areas(request):
    country = request.GET.get("country", "").strip()
    province = request.GET.get("province", "").strip()
    city = request.GET.get("city", "").strip()
    if not city:
        return JsonResponse({"success": False, "error": "Please select a city."}, status=400)
    cache_key = f"osm-areas:{country}:{province}:{city}"
    area_names = cache.get(cache_key)
    if area_names is None:
        try:
            area_names = OpenStreetMapService(timeout=8).list_areas(country, province, city)
        except OpenStreetMapError:
            area_names = []
        area_names = [f"All {city}"] + [name for name in area_names if name.casefold() != city.casefold()]
        cache.set(cache_key, area_names, 60 * 60 * 24 * 7)
    return JsonResponse({"success": True, "areas": area_names})

def _rate_limited(request):
    now = time.time()
    client = request.META.get("REMOTE_ADDR", "unknown")
    key = f"search-rate:{client}"
    attempts = [t for t in cache.get(key, []) if now - t < 60]
    if len(attempts) >= 10:
        return True
    attempts.append(now)
    cache.set(key, attempts, 60)
    return False

@require_POST
def search(request):
    if _rate_limited(request):
        return JsonResponse({"success": False, "error": "Too many searches. Please wait a minute and try again."}, status=429)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request."}, status=400)
    form = SearchForm(payload)
    if not form.is_valid():
        errors = {key: [str(message) for message in values] for key, values in form.errors.items()}
        return JsonResponse({"success": False, "error": "Please correct the search fields.", "fields": errors}, status=400)
    data = form.cleaned_data
    try:
        provider = data.pop("provider")
        service = OpenStreetMapService() if provider == "osm" else GooglePlacesService()
        found = service.search_businesses(**data)
    except (PlacesError, OpenStreetMapError) as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=503)
    except Exception:
        logger.exception("Unexpected search failure")
        return JsonResponse({"success": False, "error": "An unexpected error occurred. Please try again."}, status=500)

    businesses = [
        {**item, "provider": provider, "province": data["province"], "city": data["city"], "area": data["area"], "country": data["country"]}
        for item in found
    ]
    if settings.ENABLE_EMAIL_ENRICHMENT:
        businesses = WebsiteEmailEnricher().enrich(businesses)
    history = store.save_search({"provider": provider, **{k: data[k] for k in ("country", "province", "city", "area", "category", "keyword")}}, businesses)
    return JsonResponse({"success": True, "count": len(businesses), "search_id": history["id"], "results": history["results"]})

def results(request):
    history = store.get_search(request.GET.get("search"))
    businesses = history.get("results", []) if history else []
    return render(request, "results.html", {"search": history, "results": businesses, "results_json": json.dumps(businesses)})

def history(request):
    searches = store.searches()
    return render(request, "history.html", {"searches": searches})

def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "results"

def export_results(request, file_type):
    search_obj = store.get_search(request.GET.get("search"))
    if not search_obj:
        raise Http404("Search not found")
    businesses = search_obj.get("results", [])
    selected = request.GET.get("ids", "").strip()
    if selected:
        try:
            ids = [int(value) for value in selected.split(",")]
        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid selected results."}, status=400)
        businesses = [item for item in businesses if item.get("id") in ids]
    base = f"business_results_{_slug(search_obj['city'])}_{_slug(search_obj['country'])}"
    return excel_response(businesses, base + ".xlsx") if file_type == "excel" else csv_response(businesses, base + ".csv")
