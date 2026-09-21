# Business Data Finder

A production-minded application with a **React/Vite frontend** and **Python/Django JSON API backend** for finding businesses by country, city, category, and keyword. It supports free **OpenStreetMap/Nominatim/Overpass** search and the optional official **Google Places API (New)**. It provides a responsive dashboard, saved search history, public website email enrichment, manual result editing/deletion, result selection, and UTF-8 CSV/Excel exports. It does not scrape Google Maps.

## Requirements

- Python 3.11 or newer (the project may also run on Python 3.10 with the pinned Django range)
- A Google Cloud project with billing configured as required by Google
- Places API (New) enabled and a restricted API key

## Installation — macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python manage.py runserver
```

The compiled React bundle is committed under `static/frontend`. When editing React source, rebuild it with:

```bash
cd frontend
npm install
npm run build
cd ..
```

Open <http://127.0.0.1:8000/>.

## One-command start

From the project root, build React and start Django together:

```bash
python start.py
```

The first run installs frontend packages if needed. Later runs rebuild React and start the server. To start immediately with the existing compiled bundle:

```bash
python start.py --skip-build
```

## Deploy to Vercel

The repository includes `vercel.json` and `api/index.py` for deploying the Django API and built React bundle as one Vercel project:

```bash
vercel
```

In Vercel Project Settings, add the values from `.env.example` as Environment Variables. At minimum set a strong `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=.vercel.app`, and any Google/OSM settings you use. Vercel's filesystem is temporary, so the default `/tmp/business_data.json` is only a short-lived cache; saved searches and manual edits are not durable across cold starts or redeploys. For persistent production data, set `JSON_DATA_FILE` only when using a mounted persistent store, or migrate `JSONDataStore` to a managed Postgres/Neon database before launch.

You can also pass Django server arguments, for example `python start.py 0.0.0.0:8080`.

## Installation — Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` from an appropriate PowerShell session, or invoke `.venv\Scripts\python.exe` directly.

## Google Cloud setup

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Open **APIs & Services → Library**, find **Places API (New)**, and enable it.
4. Configure billing according to Google's current requirements.
5. Open **APIs & Services → Credentials** and create an API key.
6. Restrict the key to **Places API (New)**. Because calls originate from Django, use server-appropriate application restrictions (for a deployed service, typically the server's fixed IP); do not use browser referrer restrictions for this key.
7. Copy `.env.example` to `.env` and set the key:

```dotenv
GOOGLE_MAPS_API_KEY=your_real_api_key_here
MAX_RESULTS_PER_SEARCH=100
REQUEST_TIMEOUT=15
DEBUG=True
SECRET_KEY=replace-this-with-a-random-secret
```

The `.env` file is ignored by Git. Never commit or expose the key to frontend JavaScript.

## Commands

```bash
# Run all tests (Google is mocked; no API quota is used)
python manage.py test

# Run the local server
python manage.py runserver

```

## Using the application

Choose a provider, then select country, province/state, city, area, category, optional keyword, and result limit. Countries and subdivisions are global; dependent state/city data uses a cached public geographic directory with local fallbacks, while area lookup uses OpenStreetMap. OpenStreetMap is the default business provider and needs no API key. The backend searches mapped businesses with Overpass, removes duplicate OSM IDs, and saves a snapshot. Public endpoints are best-effort and rate-limited; they may contain fewer phone numbers and websites. For high-volume production use, host the required datasets/services yourself or use a commercial provider.

Google mode builds a text query such as `iPhone Mobile Shops in Lahore, Pakistan`, requests the configured Places fields, follows bounded page tokens, and removes duplicate place IDs.

When a result has a public website but no email, the backend checks that website's HTML for a publicly displayed email or `mailto:` link. It does not guess addresses, bypass access controls, or scrape Google Maps, so businesses that do not publish an email remain `N/A`.

On the results page you can search within results, select rows, edit every saved business field, delete an individual record, open coordinates in Google Maps, and download CSV or Excel (including email). Edits and deletions are written directly to `data/business_data.json`. “Export all” exports the entire saved search, not only the current UI view. The history page opens each prior search snapshot.

## Configuration and deployment

| Variable | Purpose | Default |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Server-side Places API key | empty |
| `MAX_RESULTS_PER_SEARCH` | Hard result ceiling (also capped at 100) | `100` |
| `REQUEST_TIMEOUT` | Google request timeout in seconds | `15` |
| `OSM_USER_AGENT` | Identifies your application to public OSM services | local development value |
| `OSM_CONTACT_EMAIL` | Optional contact email sent to Nominatim | empty |
| `OSM_OVERPASS_URL` | Configurable OpenStreetMap Overpass endpoint | `https://overpass-api.de/api/interpreter` |
| `OSM_OVERPASS_FALLBACKS` | Comma-separated fallback Overpass endpoints | Private.coffee and VK Maps mirrors |
| `ENABLE_EMAIL_ENRICHMENT` | Check public business websites for displayed email addresses | `True` |
| `EMAIL_ENRICHMENT_MAX` | Maximum websites checked per search | `20` |
| `EMAIL_ENRICHMENT_TIMEOUT` | Timeout per website request in seconds | `6` |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS behind a configured production proxy | `False` |
| `DEBUG` | Django debug mode | `False` |
| `SECRET_KEY` | Django signing secret | development fallback |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1,testserver` |

Searches and results are stored in `data/business_data.json`; no database or migration command is required. Writes use an atomic temporary-file replacement and an in-process lock. This is suitable for a local/single-process deployment. For multiple workers or high-volume production, replace `JSONDataStore` with a shared transactional store. Also set `DEBUG=False`, use a strong secret, configure HTTPS/security headers, collect static files, and run behind a production WSGI/ASGI server.

## Billing, quota, storage, and security

Google Places requests can consume quota and incur charges. Review current pricing and quotas in Google Cloud, apply budget alerts, restrict the key, and request only the result count you need. Field masks minimize unnecessary data and cost. Google can return fewer results than requested.

The application uses Django CSRF protection, validated fields, a server-side maximum, timeouts, and a basic per-session limit of 10 searches/minute. The browser never receives the API key. Before public deployment, add infrastructure-level rate limiting and authentication as appropriate.

Places data use and retention must comply with the current Google Maps Platform terms. Confirm that your intended storage, display, and export behavior is permitted for your use case. This project uses only official API responses and never scrapes Google Maps HTML.

## Project layout

- `finder/services/google_places.py` — API client, pagination, error mapping, normalization
- `finder/services/json_store.py` — atomic JSON persistence, history, and dashboard statistics
- `data/business_data.json` — project-local searches and result data
- `frontend/src/` — React dashboard, results, and history screens
- `static/frontend/` — production Vite bundle served by Django
- `finder/utils/export.py` — CSV and Excel generation
- `finder/views.py` — dashboard, AJAX search, history, results, exports
- `templates/` and `static/` — responsive server-rendered UI and browser interactions
- `finder/tests.py` — validation, mocked API, errors, deduplication, history, and exports
