"""
Polite HTTP client for DIDI collectors.
Enforces per-host rate limiting, random jitter, robots.txt compliance,
backoff on 429/503, and consecutive error capping.
"""
from __future__ import annotations

import logging
import random
import time
import urllib.robotparser
from urllib.parse import urlparse
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class CrawlerBlockedError(Exception):
    """Raised when crawling a source is blocked by robots.txt or rate limits."""
    pass


class MaxConsecutiveErrorsError(Exception):
    """Raised when 10 consecutive fetch errors occur on a single source."""
    pass


class PoliteSession:
    def __init__(
        self,
        user_agent: str = "DIDI-research-crawler/0.1 (Eurac Research)",
        delay_seconds: float = 3.0,
        respect_robots: bool = True,
        timeout: float = 25.0,
    ):
        self.user_agent = user_agent
        self.base_delay = delay_seconds
        self.respect_robots = respect_robots
        self.timeout = timeout

        self._host_delays: Dict[str, float] = {}
        self._last_hit: Dict[str, float] = {}
        self._robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self._robots_allowed_all: Dict[str, bool] = {}
        self._robots_blocked_all: Dict[str, bool] = {}
        self._consecutive_errors: Dict[str, int] = {}

        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it,de;q=0.9,en;q=0.5",
        })

        # Retry only transport errors and 5xx (up to 3 times)
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            respect_retry_after_header=True,
        )
        self.s.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        self.s.mount("https://", HTTPAdapter(max_retries=retry_strategy))

    def _get_host(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_netloc(self, url: str) -> str:
        return urlparse(url).netloc

    # ---- robots.txt ---------------------------------------------------------
    def load_robots(self, url: str) -> None:
        host = self._get_host(url)
        if host in self._robots or host in self._robots_blocked_all or host in self._robots_allowed_all:
            return

        robots_url = f"{host}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = self._raw_get(robots_url, check_content_type=False)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                self._robots[host] = rp
            elif r.status_code in (401, 403):
                # Bug fix: 401 or 403 means "fetch nothing", not "fetch everything"
                log.warning("robots.txt returned HTTP %d for %s: blocking all fetches", r.status_code, host)
                self._robots_blocked_all[host] = True
            else:
                # Other 4xx (e.g. 404): allowed
                self._robots_allowed_all[host] = True
        except requests.RequestException as e:
            # Bug fix: if robots.txt cannot be reached, do not fetch
            log.warning("robots.txt unreachable for %s (%s): blocking all fetches", host, e)
            self._robots_blocked_all[host] = True

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = self._get_host(url)
        self.load_robots(url)
        if self._robots_blocked_all.get(host):
            return False
        if self._robots_allowed_all.get(host):
            return True
        rp = self._robots.get(host)
        if rp is None:
            return False
        return rp.can_fetch(self.user_agent, url)

    def robots_sitemaps(self, url: str) -> List[str]:
        host = self._get_host(url)
        self.load_robots(url)
        rp = self._robots.get(host)
        if rp is not None:
            return list(rp.site_maps() or [])
        return []

    # ---- Throttling & Polite Fetching ---------------------------------------
    def _throttle(self, url: str) -> None:
        netloc = self._get_netloc(url)
        current_delay = self._host_delays.get(netloc, self.base_delay)
        # Random extra delay of up to 2.0s
        jitter = random.uniform(0.0, 2.0)
        total_wait = current_delay + jitter

        last = self._last_hit.get(netloc, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < total_wait:
            time.sleep(total_wait - elapsed)
        self._last_hit[netloc] = time.monotonic()

    def _raw_get(self, url: str, check_content_type: bool = True) -> requests.Response:
        self._throttle(url)
        r = self.s.get(url, timeout=self.timeout)

        # On 429 or 503: back off and double delay for host
        if r.status_code in (429, 503):
            netloc = self._get_netloc(url)
            self._host_delays[netloc] = self._host_delays.get(netloc, self.base_delay) * 2.0
            retry_after = r.headers.get("Retry-After")
            wait_time = int(retry_after) if retry_after and retry_after.isdigit() else 60
            log.warning("HTTP %d on %s. Backing off for %ds and doubling delay to %.1fs",
                        r.status_code, url, wait_time, self._host_delays[netloc])
            time.sleep(wait_time)

        return r

    def get(self, url: str) -> Optional[requests.Response]:
        netloc = self._get_netloc(url)

        # Stop source if 10 consecutive errors occurred
        if self._consecutive_errors.get(netloc, 0) >= 10:
            raise MaxConsecutiveErrorsError(f"10 consecutive errors on {netloc}. Aborting source run.")

        if not self.allowed(url):
            log.info("robots.txt disallows %s", url)
            return None

        try:
            r = self._raw_get(url)
        except requests.RequestException as e:
            self._consecutive_errors[netloc] = self._consecutive_errors.get(netloc, 0) + 1
            log.warning("GET error on %s: %s (consecutive errors: %d)",
                        url, e, self._consecutive_errors[netloc])
            return None

        if r.status_code != 200:
            self._consecutive_errors[netloc] = self._consecutive_errors.get(netloc, 0) + 1
            log.info("HTTP %d for %s (consecutive errors: %d)",
                     r.status_code, url, self._consecutive_errors[netloc])
            return None

        # Download only HTML pages / XML sitemaps: no media, images, binaries, PDFs
        ctype = (r.headers.get("Content-Type") or "").lower()
        if not any(t in ctype for t in ("text/html", "application/xhtml+xml", "text/xml", "application/xml")):
            log.info("Skipping non-HTML/XML Content-Type %s for %s", ctype, url)
            return None

        # Reset consecutive errors on successful fetch
        self._consecutive_errors[netloc] = 0

        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        return r

