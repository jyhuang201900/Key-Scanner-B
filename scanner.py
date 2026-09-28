"""High-recall GitHub scanner for leaked Outlook account lines."""
import base64
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

import config
from line_format import normalize_account_line


ACCOUNT_PATTERN = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+)"
    + re.escape(config.ACCOUNT_SEPARATOR)
    + r"(?P<password>[^\s]+?)"
    + re.escape(config.ACCOUNT_SEPARATOR)
    + r"(?P<client_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    + r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    + re.escape(config.ACCOUNT_SEPARATOR)
    + rf"(?P<refresh_token>\S{{{config.MIN_REFRESH_TOKEN_LENGTH},}})"
)


class KeyScanner:
    def __init__(self, on_found: Optional[Callable[[str], bool]] = None):
        if not config.GITHUB_TOKEN:
            raise ValueError("请设置 GITHUB_TOKEN")

        self.on_found = on_found
        self.search_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.text-match+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "outlook-leak-line-scanner",
        }
        self.raw_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.raw",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "outlook-leak-line-scanner",
        }
        self.found_keys: Set[str] = set()
        self.visited_files: Set[str] = set()
        self.branch_cache: Dict[str, str] = {}
        self.file_count = 0
        self._lock = threading.RLock()
        self._local = threading.local()
        self.search_remaining: Optional[int] = None
        self.search_reset = 0
        self.core_remaining: Optional[int] = None
        self.core_reset = 0

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is not None:
            return session

        retry = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=20,
            pool_maxsize=20,
        )
        session = requests.Session()
        session.mount("https://", adapter)
        self._local.session = session
        return session

    def _get(self, url: str, **kwargs):
        return self._session().get(url, **kwargs)

    def _update_rate_state(self, response) -> None:
        resource = response.headers.get("X-RateLimit-Resource", "").lower()
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is None or reset is None:
            return

        try:
            remaining_value = int(remaining)
            reset_value = int(reset)
        except ValueError:
            return

        with self._lock:
            if resource == "search":
                self.search_remaining = remaining_value
                self.search_reset = reset_value
            elif resource == "core":
                self.core_remaining = remaining_value
                self.core_reset = reset_value

    def _wait_for_limit(self, resource: str, minimum: int) -> None:
        with self._lock:
            remaining = (
                self.search_remaining if resource == "search" else self.core_remaining
            )
            reset = self.search_reset if resource == "search" else self.core_reset

        if remaining is None or remaining > minimum:
            return

        wait = max(0, reset - time.time()) + 2
        if wait > 0:
            print(f"GitHub {resource} limit reached, waiting {wait:.0f}s")
            time.sleep(wait)

    def validate_auth(self) -> None:
        """Fail fast when the GitHub token is invalid or unauthorized."""
        try:
            response = self._get(
                f"{config.GITHUB_API_BASE}/rate_limit",
                headers=self.search_headers,
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"GitHub authentication check failed: {exc}") from exc

        self._update_rate_state(response)
        if response.status_code == 401:
            raise RuntimeError(
                "GitHub API authentication failed (401). "
                "Use the built-in github.token or a valid PAT."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "GitHub API authentication failed (403). "
                "Check token permissions or rate limits."
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"GitHub authentication check returned HTTP {response.status_code}"
            )

        resources = response.json().get("resources", {})
        search_rate = resources.get("search", {})
        core_rate = resources.get("core", {})
        with self._lock:
            self.search_remaining = search_rate.get("remaining")
            self.search_reset = search_rate.get("reset", 0)
            self.core_remaining = core_rate.get("remaining")
            self.core_reset = core_rate.get("reset", 0)

        print(
            "GitHub authentication OK, "
            f"search remaining: {self.search_remaining}, "
            f"core remaining: {self.core_remaining}"
        )

    @staticmethod
    def extract_lines(content: str) -> Set[str]:
        lines = set()
        for match in ACCOUNT_PATTERN.finditer(content):
            line = normalize_account_line(match.group(0))
            if line:
                lines.add(line)
        return lines

    def consume(self, content: str, source: str) -> int:
        candidates = self.extract_lines(content)
        if not candidates:
            return 0

        new_lines = []
        with self._lock:
            for line in candidates:
                if line not in self.found_keys:
                    self.found_keys.add(line)
                    new_lines.append(line)

        stored = 0
        for line in new_lines:
            was_stored = self.on_found(line) if self.on_found else True
            if was_stored:
                stored += 1
                print(
                    f"  + [{len(self.found_keys)}] "
                    f"{line[:90]}... ({source})"
                )
        return stored

    def get_default_branch(self, full_name: str) -> str:
        with self._lock:
            cached = self.branch_cache.get(full_name)
        if cached:
            return cached

        branch = "main"
        try:
            self._wait_for_limit("core", config.MIN_REMAINING_REQUESTS)
            response = self._get(
                f"{config.GITHUB_API_BASE}/repos/{full_name}",
                headers=self.search_headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            self._update_rate_state(response)
            if response.status_code == 200:
                branch = response.json().get("default_branch") or branch
        except requests.RequestException:
            pass

        with self._lock:
            self.branch_cache[full_name] = branch
        return branch

    @staticmethod
    def _response_too_large(response) -> bool:
        content_length = response.headers.get("Content-Length")
        if not content_length:
            return False
        try:
            return int(content_length) > config.MAX_FILE_BYTES
        except ValueError:
            return False

    @staticmethod
    def _decode_content(response) -> Optional[str]:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type and response.text.lstrip().startswith("{"):
            try:
                payload = response.json()
            except ValueError:
                return None

            encoded = payload.get("content", "")
            if payload.get("encoding") == "base64":
                try:
                    return base64.b64decode(encoded).decode(
                        "utf-8",
                        errors="replace",
                    )
                except (ValueError, TypeError):
                    return None
            return None
        return response.text

    def fetch_file(self, item: Dict) -> Optional[str]:
        repository = item.get("repository") or {}
        full_name = repository.get("full_name")
        path = item.get("path")
        if not full_name or not path:
            return None

        branch = (
            repository.get("default_branch")
            or self.get_default_branch(full_name)
        )
        raw_url = (
            f"https://raw.githubusercontent.com/{full_name}/"
            f"{quote(branch, safe='')}/{quote(path, safe='/')}"
        )

        try:
            response = self._get(
                raw_url,
                headers=self.raw_headers,
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException:
            response = None

        if (
            response is not None
            and response.status_code == 200
            and not self._response_too_large(response)
        ):
            return self._decode_content(response)

        return self.fetch_file_from_api(full_name, path, branch)

    def fetch_file_from_api(
        self,
        full_name: str,
        path: str,
        branch: str,
    ) -> Optional[str]:
        url = (
            f"{config.GITHUB_API_BASE}/repos/{full_name}/contents/"
            f"{quote(path, safe='/')}"
        )

        for attempt in range(3):
            self._wait_for_limit("core", config.MIN_REMAINING_REQUESTS)
            try:
                response = self._get(
                    url,
                    headers=self.raw_headers,
                    params={"ref": branch},
                    timeout=config.REQUEST_TIMEOUT,
                )
            except requests.RequestException:
                return None

            self._update_rate_state(response)
            if response.status_code == 200:
                if self._response_too_large(response):
                    return None
                decoded = self._decode_content(response)
                if decoded is not None:
                    return decoded

                try:
                    download_url = response.json().get("download_url")
                except ValueError:
                    download_url = None
                if download_url:
                    try:
                        raw = self._get(
                            download_url,
                            headers=self.raw_headers,
                            timeout=config.REQUEST_TIMEOUT,
                        )
                    except requests.RequestException:
                        return None
                    if raw.status_code == 200:
                        return raw.text
                return None

            if response.status_code in (403, 429) and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    time.sleep(min(float(retry_after), 300))
                else:
                    self._wait_for_limit("core", config.MIN_REMAINING_REQUESTS)
                continue

            return None

        return None

    def _search_page(self, query: str, page: int):
        params = {"q": query, "per_page": config.PER_PAGE, "page": page}
        url = f"{config.GITHUB_API_BASE}/search/code"

        for attempt in range(3):
            self._wait_for_limit("search", 1)
            try:
                response = self._get(
                    url,
                    headers=self.search_headers,
                    params=params,
                    timeout=config.REQUEST_TIMEOUT,
                )
            except requests.RequestException as exc:
                print(f"Search request failed: {query}: {exc}")
                return None

            self._update_rate_state(response)
            if response.status_code == 200:
                return response
            if response.status_code == 401:
                raise RuntimeError(
                    "GitHub search returned HTTP 401: token is invalid"
                )
            if response.status_code == 422:
                print(f"Invalid search query: {query}")
                return None
            if response.status_code in (403, 429) and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    time.sleep(min(float(retry_after), 300))
                else:
                    self._wait_for_limit("search", 1)
                    time.sleep(10 * (attempt + 1))
                continue

            print(f"Search HTTP {response.status_code}: {query}")
            return None

        return None

    def collect_query_items(self, query: str, limit: int) -> List[Dict]:
        items: List[Dict] = []
        total_count = None

        for page in range(1, config.MAX_PAGES + 1):
            remaining_query = limit - len(items)
            if remaining_query <= 0:
                break

            response = self._search_page(query, page)
            if response is None:
                break

            payload = response.json()
            if page == 1:
                total_count = payload.get("total_count", "unknown")
                print(f"  GitHub matches reported: {total_count}")

            page_items = payload.get("items", [])
            if not page_items:
                break

            for item in page_items:
                repository = item.get("repository") or {}
                full_name = repository.get("full_name", "unknown")
                path = item.get("path", "unknown")
                file_key = f"{full_name}:{path}"

                with self._lock:
                    if file_key in self.visited_files:
                        continue
                    if self.file_count >= config.MAX_FILES_PER_SCAN:
                        break
                    self.visited_files.add(file_key)
                    self.file_count += 1

                items.append(item)
                if len(items) >= limit:
                    break

            if len(items) >= limit:
                break
            if "next" not in response.links:
                break

            time.sleep(random.uniform(
                config.REQUEST_DELAY_MIN,
                config.REQUEST_DELAY_MAX,
            ))

        return items

    def process_item(self, item: Dict) -> int:
        repository = item.get("repository") or {}
        full_name = repository.get("full_name", "unknown")
        path = item.get("path", "unknown")
        source = f"{full_name}/{path}"
        added = 0

        fragments = [
            match.get("fragment", "")
            for match in item.get("text_matches", [])
        ]
        for fragment in fragments:
            added += self.consume(fragment, source)

        content = self.fetch_file(item)
        if content:
            added += self.consume(content, source)
        return added

    def process_items_parallel(self, items: Iterable[Dict]) -> int:
        item_list = list(items)
        if not item_list:
            return 0

        added = 0
        workers = min(config.DOWNLOAD_WORKERS, len(item_list))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.process_item, item): item
                for item in item_list
            }
            for future in as_completed(futures):
                try:
                    added += future.result()
                except Exception as exc:
                    item = futures[future]
                    repo = (item.get("repository") or {}).get("full_name", "?")
                    path = item.get("path", "?")
                    print(f"File processing failed: {repo}/{path}: {exc}")
        return added

    def search_github(self, query: str, limit: int) -> int:
        items = self.collect_query_items(query, limit)
        if not items:
            return 0
        print(f"  Processing {len(items)} unique files")
        return self.process_items_parallel(items)

    def scan(self) -> Dict[str, object]:
        print("Scanning GitHub for leaked account lines...")
        self.validate_auth()
        search_plan: List[Tuple[str, int]] = list(config.SEARCH_PLAN)
        total_weight = sum(weight for _, weight in search_plan) or 1
        start_time = time.time()
        total_added = 0

        for query, weight in tqdm(search_plan, desc="Queries"):
            with self._lock:
                if self.file_count >= config.MAX_FILES_PER_SCAN:
                    tqdm.write(
                        f"Global file limit reached: "
                        f"{config.MAX_FILES_PER_SCAN}"
                    )
                    break
            weighted_limit = max(
                1,
                config.MAX_FILES_PER_SCAN * weight // total_weight,
            )
            query_limit = min(config.MAX_FILES_PER_QUERY, weighted_limit)
            tqdm.write(f"Search: {query} (limit={query_limit})")
            total_added += self.search_github(query, query_limit)

        elapsed = time.time() - start_time
        print(
            f"Scan complete: {total_added} new lines, "
            f"{len(self.found_keys)} seen, {self.file_count} files, "
            f"{elapsed:.2f}s"
        )
        return {
            "total_queries": len(search_plan),
            "total_found": total_added,
            "unique_keys": len(self.found_keys),
            "files_scanned": self.file_count,
            "elapsed_time": elapsed,
            "keys": list(self.found_keys),
        }
