import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


class WebsiteEmailEnricher:
    def __init__(self, timeout=None):
        self.timeout = timeout or settings.EMAIL_ENRICHMENT_TIMEOUT
        self.headers = {"User-Agent": settings.OSM_USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    @staticmethod
    def _is_public_url(url):
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return False
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            return all(not (ipaddress.ip_address(item[4][0]).is_private or ipaddress.ip_address(item[4][0]).is_loopback or ipaddress.ip_address(item[4][0]).is_reserved) for item in addresses)
        except (OSError, ValueError):
            return False

    def email_from_website(self, url):
        if not self._is_public_url(url):
            return None
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, stream=True, allow_redirects=True)
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                return None
            content = response.raw.read(524288, decode_content=True).decode(response.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            mailtos = [link.get("href", "")[7:].split("?")[0] for link in soup.select('a[href^="mailto:"]')]
            candidates = mailtos + EMAIL_RE.findall(soup.get_text(" "))
            return next((email.strip().lower() for email in candidates if email and not email.lower().endswith(("@example.com", "@domain.com"))), None)
        except requests.RequestException as exc:
            logger.info("Email enrichment skipped for %s: %s", url, exc)
            return None

    def enrich(self, businesses):
        targets = [(i, item) for i, item in enumerate(businesses[:settings.EMAIL_ENRICHMENT_MAX]) if item.get("email") in {None, "", "N/A"} and item.get("website") not in {None, "", "N/A"}]
        with ThreadPoolExecutor(max_workers=min(5, len(targets) or 1)) as pool:
            futures = {pool.submit(self.email_from_website, item["website"]): i for i, item in targets}
            for future in as_completed(futures):
                email = future.result()
                businesses[futures[future]]["email"] = email or "N/A"
        for item in businesses:
            item.setdefault("email", "N/A")
        return businesses
