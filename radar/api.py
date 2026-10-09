"""Small client for the Bundesagentur für Arbeit job search API.

The API is unofficial and changes without notice (the v4 search was switched
off), so every request is retried with backoff and anything unexpected raises
ApiError with a message that says what broke.
"""

import base64
import logging
import threading
import time

import requests

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
SEARCH_PATH = "/pc/v6/jobs"
DETAIL_PATH = "/pc/v4/jobdetails/{b64}"
HEADERS = {
    # Public client id used by the arbeitsagentur.de web app; not a secret.
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "werkstudent-radar/0.1 (+https://github.com/morty1338/werkstudent-radar)",
    "Accept": "application/json",
}
RETRIES = 4
TIMEOUT = 30

log = logging.getLogger(__name__)
_local = threading.local()


class ApiError(Exception):
    """Raised when the API answers in a way we can't trust."""


class NotFound(ApiError):
    """The resource doesn't exist (e.g. a posting was taken down)."""


def _session():
    # requests.Session isn't guaranteed thread-safe, so each worker thread gets its own.
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers.update(HEADERS)
    return _local.session


def get_json(url, params=None):
    """GET with retries and exponential backoff on network errors, 429 and 5xx."""
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = _session().get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            last_error = f"network error: {e}"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    last_error = "response is not JSON"
            elif resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {resp.url}")
            elif resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
            else:
                # Other 4xx won't fix itself (e.g. 403 when an API version is retired).
                raise ApiError(f"HTTP {resp.status_code} from {resp.url}: {resp.text[:200]}")
        wait = 2 ** attempt
        log.warning("attempt %d/%d failed (%s), retrying in %ds", attempt, RETRIES, last_error, wait)
        time.sleep(wait)
    raise ApiError(f"giving up on {url} {params or ''}: {last_error}")


def search(query, page, size):
    """One page of search results: {"maxErgebnisse": int, "ergebnisliste": [...]}."""
    data = get_json(BASE_URL + SEARCH_PATH, {"was": query, "page": page, "size": size})
    if not isinstance(data, dict) or "maxErgebnisse" not in data:
        keys = list(data)[:10] if isinstance(data, dict) else type(data).__name__
        raise ApiError(f"unexpected search response for '{query}' page {page}: {keys}")
    return data


def job_details(refnr):
    """Full posting incl. the description text (field stellenangebotsBeschreibung).

    Returns None when the posting no longer exists.
    """
    b64 = base64.b64encode(refnr.encode()).decode()
    try:
        data = get_json(BASE_URL + DETAIL_PATH.format(b64=b64))
    except NotFound:
        return None
    if not isinstance(data, dict) or "referenznummer" not in data:
        raise ApiError(f"unexpected details response for {refnr}")
    return data
