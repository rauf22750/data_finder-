import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key")
DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework", "finder",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
MAX_RESULTS_PER_SEARCH = min(100, max(1, int(os.getenv("MAX_RESULTS_PER_SEARCH", "100"))))
REQUEST_TIMEOUT = max(1, int(os.getenv("REQUEST_TIMEOUT", "15")))
OSM_USER_AGENT = os.getenv("OSM_USER_AGENT", "BusinessDataFinder/1.0 (local development)").strip()
OSM_CONTACT_EMAIL = os.getenv("OSM_CONTACT_EMAIL", "").strip()
OSM_OVERPASS_URL = os.getenv("OSM_OVERPASS_URL", "https://overpass-api.de/api/interpreter").strip()
OSM_OVERPASS_FALLBACKS = [url.strip() for url in os.getenv(
    "OSM_OVERPASS_FALLBACKS",
    "https://overpass.private.coffee/api/interpreter,https://maps.mail.ru/osm/tools/overpass/api/interpreter",
).split(",") if url.strip()]
_json_data_path = Path(os.getenv("JSON_DATA_FILE", "data/business_data.json"))
JSON_DATA_FILE = _json_data_path if _json_data_path.is_absolute() else BASE_DIR / _json_data_path
ENABLE_EMAIL_ENRICHMENT = os.getenv("ENABLE_EMAIL_ENRICHMENT", "True").lower() in {"1", "true", "yes"}
EMAIL_ENRICHMENT_MAX = min(50, max(0, int(os.getenv("EMAIL_ENRICHMENT_MAX", "20"))))
EMAIL_ENRICHMENT_TIMEOUT = max(2, int(os.getenv("EMAIL_ENRICHMENT_TIMEOUT", "6")))

# Safe production defaults; terminate TLS at the app or set the proxy header correctly.
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() in {"1", "true", "yes"}
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
