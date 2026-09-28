"""Search GitHub for leaked Outlook account lines."""
import base64
import random
import re
import time
from typing import Callable, Dict, List, Optional, Set
from urllib.parse import quote

import requests
from tqdm import tqdm

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
    + (
        rf"(?P<refresh_token>[A-Za-z0-9._~!@#$%^&*+/=-]"
        rf"{{{config.MIN_REFRESH_TOKEN_LENGTH},}})"
    )
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

    def validate_auth(self) -> None:
        """Fail fast when the GitHub token is invalid or unauthorized."""
        try:
            response = requests.get(
                f"{config.GITHUB_API_BASE}/rate_limit",
                headers=self.search_headers,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"GitHub authentication check failed: {exc}") from exc

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

        search_rate = response.json().get("resources", {}).get("search", {})
        print(
            "GitHub authentication OK, "
            f"search remaining: {search_rate.get('remaining', 'unknown')}"
        )

    def check_rate_limit(self) -> None:
        try:
            response = requests.get(
                f"{config.GITHUB_API_BASE}/rate_limit",
                headers=self.search_headers,
                timeout=15,
            )
            if response.status_code == 401:
                raise RuntimeError(
                    "GitHub API authentication failed (401): invalid token"
                )
            response.raise_for_status()
            rate = response.json()["resources"]["search"]
            remaining = rate["remaining"]
            if remaining < config.MIN_REMAINING_REQUESTS:
                wait = max(0, rate["reset"] - time.time()) + 5
                print(f"GitHub search rate limit reached, waiting {wait:.0f}s")
                time.sleep(wait)
        except RuntimeError:
            raise
        except Exception as exc:
            print(f"Rate-limit check failed: {exc}")

    @staticmethod
    def extract_lines(content: str) -> Set[str]:
        lines = set()
        for match in ACCOUNT_PATTERN.finditer(content):
            line = normalize_account_line(match.group(0))
            if line:
                lines.add(line)
        return lines

    def consume(self, content: str, source: str) -> int:
        added = 0
        for line in self.extract_lines(content):
            if line in self.found_keys:
                continue

            self.found_keys.add(line)
            if self.on_found is not None:
                self.on_found(line)
            added += 1
            print(f"  + [{len(self.found_keys)}] {line[:90]}... ({source})")
        return added

    def get_default_branch(self, full_name: str) -> str:
        if full_name in self.branch_cache:
            return self.branch_cache[full_name]

        branch = "main"
        try:
            response = requests.get(
                f"{config.GITHUB_API_BASE}/repos/{full_name}",
                headers=self.search_headers,
                timeout=15,
            )
            if response.status_code == 200:
                branch = response.json().get("default_branch") or branch
        except requests.RequestException:
            pass

        self.branch_cache[full_name] = branch
        return branch

    def fetch_file(self, item: Dict) -> Optional[str]:
        repository = item.get("repository") or {}
        full_name = repository.get("full_name")
        path = item.get("path")
        if not full_name or not path:
            return None

        branch = repository.get("default_branch") or self.get_default_branch(full_name)
        url = (
            f"{config.GITHUB_API_BASE}/repos/{full_name}/contents/"
            f"{quote(path, safe='/')}"
        )

        try:
            response = requests.get(
                url,
                headers=self.raw_headers,
                params={"ref": branch},
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"File download failed: {full_name}/{path}: {exc}")
            return None

        if response.status_code in (403, 429):
            print(f"File API rate limited for {full_name}/{path}")
            time.sleep(config.ABUSE_WAIT_TIME)
            return None

        if response.status_code != 200:
            print(f"File download HTTP {response.status_code}: {full_name}/{path}")
            return None

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > config.MAX_FILE_BYTES:
            print(f"Skip large file: {full_name}/{path}")
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type and response.text.lstrip().startswith("{"):
            payload = response.json()
            encoded = payload.get("content", "")
            if payload.get("encoding") == "base64":
                try:
                    return base64.b64decode(encoded).decode("utf-8", errors="replace")
                except (ValueError, TypeError):
                    return None
            download_url = payload.get("download_url")
            if download_url:
                raw = requests.get(download_url, headers=self.raw_headers, timeout=30)
                if raw.status_code == 200:
                    return raw.text
            return None

        return response.text

    def search_github(self, query: str) -> int:
        added = 0
        query_files = 0
        url = f"{config.GITHUB_API_BASE}/search/code"

        for page in range(1, config.MAX_PAGES + 1):
            if self.file_count >= config.MAX_FILES_PER_SCAN:
                return added
            if query_files >= config.MAX_FILES_PER_QUERY:
                return added

            self.check_rate_limit()
            params = {"q": query, "per_page": config.PER_PAGE, "page": page}
            try:
                response = requests.get(
                    url,
                    headers=self.search_headers,
                    params=params,
                    timeout=20,
                )
            except requests.RequestException as exc:
                print(f"Search failed: {query}: {exc}")
                return added

            if response.status_code == 401:
                raise RuntimeError(
                    "GitHub search returned HTTP 401: token is invalid or missing"
                )

            if response.status_code == 403:
                print("GitHub abuse detection triggered, waiting...")
                time.sleep(config.ABUSE_WAIT_TIME)
                continue

            if response.status_code == 422:
                print(f"Invalid search query: {query}")
                return added

            if response.status_code != 200:
                print(f"Search HTTP {response.status_code}: {query}")
                return added

            payload = response.json()
            items = payload.get("items", [])
            if page == 1:
                print(
                    f"  Search matches reported by GitHub: "
                    f"{payload.get('total_count', 'unknown')}"
                )
            if not items:
                return added

            for item in items:
                if self.file_count >= config.MAX_FILES_PER_SCAN:
                    return added
                if query_files >= config.MAX_FILES_PER_QUERY:
                    return added

                repository = item.get("repository") or {}
                full_name = repository.get("full_name", "unknown")
                path = item.get("path", "unknown")
                file_key = f"{full_name}:{path}"
                if file_key in self.visited_files:
                    continue
                self.visited_files.add(file_key)
                query_files += 1

                fragments = [
                    match.get("fragment", "")
                    for match in item.get("text_matches", [])
                ]
                self.file_count += 1
                for fragment in fragments:
                    added += self.consume(fragment, f"{full_name}/{path}")

                # Search fragments truncate long refresh tokens, so parse the
                # complete matching file as well.
                content = self.fetch_file(item)
                if content:
                    added += self.consume(content, f"{full_name}/{path}")

                if query_files >= config.MAX_FILES_PER_QUERY:
                    break

                time.sleep(random.uniform(
                    config.REQUEST_DELAY_MIN,
                    config.REQUEST_DELAY_MAX,
                ))

            if "next" not in response.links:
                break

            time.sleep(random.uniform(
                config.REQUEST_DELAY_MIN,
                config.REQUEST_DELAY_MAX,
            ))

        return added

    def scan(self) -> Dict[str, object]:
        print("Scanning GitHub for leaked account lines...")
        self.validate_auth()
        queries: List[str] = list(config.SEARCH_QUERIES)
        start_time = time.time()
        total_added = 0

        for query in tqdm(queries, desc="Queries"):
            if self.file_count >= config.MAX_FILES_PER_SCAN:
                tqdm.write(
                    f"Global file limit reached: {config.MAX_FILES_PER_SCAN}"
                )
                break
            tqdm.write(f"Search: {query}")
            total_added += self.search_github(query)

        elapsed = time.time() - start_time
        print(
            f"Scan complete: {len(self.found_keys)} unique lines, "
            f"{self.file_count} files, {elapsed:.2f}s"
        )
        return {
            "total_queries": len(queries),
            "total_found": total_added,
            "unique_keys": len(self.found_keys),
            "files_scanned": self.file_count,
            "elapsed_time": elapsed,
            "keys": list(self.found_keys),
        }
