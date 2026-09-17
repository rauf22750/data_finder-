from django.urls import path
from . import views

app_name = "finder"
urlpatterns = [
    path("", views.react_app, name="dashboard"),
    path("search/", views.search, name="search"),
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
    path("api/searches/", views.searches_api, name="searches_api"),
    path("api/searches/latest/", views.search_detail_api, name="latest_search_api"),
    path("api/searches/<int:search_id>/", views.search_detail_api, name="search_detail_api"),
    path("api/searches/<int:search_id>/results/<int:result_id>/", views.result_item_api, name="result_item_api"),
    path("api/cities/", views.cities, name="cities"),
    path("api/provinces/", views.provinces, name="provinces"),
    path("api/areas/", views.areas, name="areas"),
    path("results/", views.react_app, name="results"),
    path("export/excel/", views.export_results, {"file_type": "excel"}, name="export_excel"),
    path("export/csv/", views.export_results, {"file_type": "csv"}, name="export_csv"),
    path("history/", views.react_app, name="history"),
]
