import csv
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook
from .forms import SearchForm
from .services.google_places import GooglePlacesService, PlacesError
from .services.json_store import JSONDataStore
from .services.osm_places import OpenStreetMapError, OpenStreetMapService
from .services.website_enrichment import WebsiteEmailEnricher

PLACE={"id":"abc","displayName":{"text":"Acme Phones"},"formattedAddress":"Main Road","nationalPhoneNumber":"123","websiteUri":"https://example.com","location":{"latitude":31.5,"longitude":74.3},"primaryType":"electronics_store","googleMapsUri":"https://maps.google.com/?cid=1"}

class SearchFormTests(SimpleTestCase):
    def test_validation(self):
        self.assertFalse(SearchForm({}).is_valid())
        self.assertTrue(SearchForm({"provider":"osm","country":"Pakistan","province":"Punjab","city":"Lahore","area":"DHA","category":"Mobile Shops","keyword":"","limit":20}).is_valid())

class ServiceTests(SimpleTestCase):
    def test_missing_fields(self):
        self.assertEqual(GooglePlacesService.normalize_place({"id":"x","displayName":{}})["phone"],"N/A")

    @override_settings(MAX_RESULTS_PER_SEARCH=100)
    def test_pagination_and_duplicates(self):
        service=GooglePlacesService(api_key="test")
        service.text_search=Mock(side_effect=[{"places":[PLACE],"nextPageToken":"next"},{"places":[PLACE,{**PLACE,"id":"def"}]}])
        self.assertEqual(len(service.search_businesses("Pakistan","Lahore","Mobile Shops",limit=20)),2)

    def test_permission_error(self):
        response=Mock(status_code=403,ok=False,text="denied")
        service=GooglePlacesService(api_key="bad",session=Mock(request=Mock(return_value=response)))
        with self.assertRaisesMessage(PlacesError,"not configured"): service.text_search("test")

class JSONViewAndExportTests(SimpleTestCase):
    def setUp(self):
        cache.clear(); self.temp=tempfile.TemporaryDirectory(); self.store=JSONDataStore(Path(self.temp.name)/"data.json")
        self.store_patch=patch("finder.views.store",self.store); self.store_patch.start()
        self.payload={"provider":"google","country":"Pakistan","province":"Punjab","city":"Lahore","area":"DHA","category":"Mobile Shops","keyword":"iPhone","limit":10}

    def tearDown(self):
        self.store_patch.stop(); self.temp.cleanup()

    def _data(self):
        result={"place_id":"abc","name":"Acme","phone":"123","email":"info@example.org","address":"Road","website":"https://example.com","category":"Shop","area":"DHA","city":"Lahore","province":"Punjab","country":"Pakistan","latitude":"1","longitude":"2","google_maps_url":"https://maps.google.com","provider":"osm"}
        return self.store.save_search({"provider":"osm","country":"Pakistan","province":"Punjab","city":"Lahore","area":"DHA","category":"Mobile Shops","keyword":""},[result])

    @override_settings(ENABLE_EMAIL_ENRICHMENT=False)
    @patch("finder.views.GooglePlacesService.search_businesses")
    def test_search_saved_to_json(self,mocked):
        mocked.return_value=[GooglePlacesService.normalize_place(PLACE)]
        self.client.post(reverse("finder:search"),data=self.payload,content_type="application/json")
        self.client.post(reverse("finder:search"),data=self.payload,content_type="application/json")
        self.assertEqual(len(self.store.searches()),2); self.assertEqual(self.store.stats()["businesses"],1)

    def test_exports(self):
        search=self._data(); csv_result=self.client.get(reverse("finder:export_csv"),{"search":search["id"]})
        self.assertEqual(list(csv.reader(io.StringIO(csv_result.content.decode("utf-8-sig"))))[1][0],"Acme")
        excel=self.client.get(reverse("finder:export_excel"),{"search":search["id"]})
        self.assertEqual(load_workbook(io.BytesIO(excel.content)).active["A2"].value,"Acme")

    def test_latest_results(self):
        self._data()
        shell=self.client.get(reverse("finder:results"))
        response=self.client.get(reverse("finder:latest_search_api"))
        self.assertContains(shell,"static/frontend/app.js")
        self.assertEqual(response.json()["search"]["results"][0]["name"],"Acme")

    def test_result_can_be_edited_and_deleted(self):
        search=self._data(); result=search["results"][0]
        url=reverse("finder:result_item_api",args=[search["id"],result["id"]])
        response=self.client.patch(url,data=json.dumps({"name":"Updated Acme","email":"sales@acme.test"}),content_type="application/json")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["result"]["email"],"sales@acme.test")
        self.assertEqual(self.store.get_search(search["id"])["results"][0]["name"],"Updated Acme")
        response=self.client.delete(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.store.get_search(search["id"])["results"],[])

class OpenStreetMapServiceTests(SimpleTestCase):
    def test_normalization_and_duplicates(self):
        element={"type":"node","id":42,"lat":31.5,"lon":74.3,"tags":{"name":"Test Shop","shop":"mobile_phone"}}
        self.assertEqual(OpenStreetMapService.normalize_place(element,"Mobile Shops")["place_id"],"osm:node:42")
        service=OpenStreetMapService(); service.geocode_city=Mock(return_value=[31,32,74,75]); service.overpass_search=Mock(return_value=[element,element])
        self.assertEqual(len(service.search_businesses("Pakistan","Lahore","Mobile Shops",limit=10)),1)

    @override_settings(OSM_OVERPASS_URL="https://one.example", OSM_OVERPASS_FALLBACKS=["https://two.example"])
    def test_overpass_uses_fallback_endpoint(self):
        service=OpenStreetMapService()
        service._get=Mock(side_effect=[OpenStreetMapError("busy"),{"elements":[{"id":1}]}])
        self.assertEqual(service._overpass("query")["elements"],[{"id":1}])
        self.assertEqual(service._get.call_count,2)

    @patch("finder.views.GlobalLocationService.cities", return_value=["Espoo","Helsinki"])
    def test_city_endpoint(self,mocked):
        self.assertIn("Helsinki",self.client.get(reverse("finder:cities"),{"country":"FI"}).json()["cities"])

    @patch("finder.views.OpenStreetMapService.list_areas", return_value=["DHA"])
    @patch("finder.views.GlobalLocationService.provinces", return_value=[{"name":"Punjab","code":"PB"}])
    def test_location_endpoints(self,mocked_provinces,mocked_areas):
        self.assertEqual(self.client.get(reverse("finder:provinces"),{"country":"PK"}).status_code,200)
        self.assertIn("DHA",self.client.get(reverse("finder:areas"),{"country":"Pakistan","province":"Punjab","city":"Lahore"}).json()["areas"])


class WebsiteEmailEnricherTests(SimpleTestCase):
    @override_settings(EMAIL_ENRICHMENT_MAX=10, EMAIL_ENRICHMENT_TIMEOUT=1)
    @patch.object(WebsiteEmailEnricher,"email_from_website",return_value="sales@acme.test")
    def test_public_website_email_is_added(self,mocked):
        businesses=[{"website":"https://acme.test","email":"N/A"},{"website":"N/A"}]
        enriched=WebsiteEmailEnricher().enrich(businesses)
        self.assertEqual(enriched[0]["email"],"sales@acme.test")
        self.assertEqual(enriched[1]["email"],"N/A")
