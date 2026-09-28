"""Empirical probe: measure real row yield per GitHub code search query.

For each candidate query this:
  1. reads total_count from the search API (one request),
  2. samples the top-ranked files the scanner would actually see,
  3. downloads them and counts canonical credential rows with the *same*
     regex the production scanner uses.

The output is a rows-per-query table. total_count alone is a bad predictor,
so the ranking is based on measured rows, not on reported counts.
"""
import base64
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from scanner import KeyScanner


# (label, query). Ordered by hypothesis priority.
CANDIDATES: List[Tuple[str, str]] = [
    # A. rare fingerprint x size floor  (primary hypothesis)
    ("A fingerprint+size", "MsaArtifacts size:100000..384000"),
    ("A fingerprint+size", "MsaArtifacts size:200000..384000"),
    ("A fingerprint+size", "MsaArtifacts size:>100000"),
    ("A fingerprint+size", "MsaArtifacts size:50000..200000"),
    ("A fingerprint+size", "MsaArtifacts"),
    ("A fingerprint+size", "MsaArtifacts size:>384000"),
    # B. bare domain, size bounded
    ("B domain+size", "hotmail size:100000..384000"),
    ("B domain+size", "outlook size:100000..384000"),
    ("B domain+size", "hotmail size:200000..384000"),
    ("B domain+size", "outlook size:200000..384000"),
    ("B domain+size", "hotmail size:50000..200000"),
    ("B domain+size", "outlook size:50000..200000"),
    # C. controls: symbol-stripping penalty
    ("C control", '"@hotmail.com" size:100000..384000'),
    ("C control", "@hotmail.com size:100000..384000"),
    ("C control", "hotmail size:100000..384000"),
    ("C control", '"----" MsaArtifacts'),
    ("C control", "M.C5 size:100000..384000"),
    ("C control", "MC5 size:100000..384000"),
    # D. file-structure partitions
    ("D structure", "MsaArtifacts filename:results"),
    ("D structure", "MsaArtifacts filename:accounts"),
    ("D structure", "MsaArtifacts filename:token"),
    ("D structure", "MsaArtifacts extension:csv"),
    ("D structure", "MsaArtifacts extension:json"),
    ("D structure", "MsaArtifacts extension:txt"),
    ("D structure", "hotmail extension:txt size:50000..384000"),
    # E. fork windows
    ("E fork", "MsaArtifacts fork:true"),
    ("E fork", "hotmail size:100000..384000 fork:true"),
]

SAMPLE_SIZE = int(os.getenv("PROBE_SAMPLE", "12"))
SEARCH_PER_PAGE = int(os.getenv("PROBE_PER_PAGE", "30"))
DOWNLOAD_WORKERS = int(os.getenv("PROBE_WORKERS", "16"))
MAX_DOWNLOAD_BYTES = int(os.getenv("PROBE_MAX_BYTES", str(400 * 1024)))
DENSE_LINES = int(os.getenv("PROBE_DENSE_LINES", "20"))
RESULT_CAP = 1000


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20),
    )
    return session


class Probe:
    def __init__(self) -> None:
        if not config.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN is required")

        self.search_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.text-match+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "outlook-leak-probe",
        }
        self.raw_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.raw",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "outlook-leak-probe",
        }
        self._local = threading.local()
        self._cache: Dict[str, Optional[str]] = {}
        self._cache_lock = threading.Lock()
        self.search_remaining: Optional[int] = None
        self.search_reset = 0

    def session(self) -> requests.Session:
        current = getattr(self._local, "session", None)
        if current is None:
            current = build_session()
            self._local.session = current
        return current

    def get(self, url: str, **kwargs):
        return self.session().get(url, **kwargs)

    # ---------- rate limit ----------

    def _note_search_rate(self, response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is None or reset is None:
            return
        try:
            self.search_remaining = int(remaining)
            self.search_reset = int(reset)
        except ValueError:
            pass

    def _wait_for_search_slot(self) -> None:
        if self.search_remaining is None or self.search_remaining > 0:
            return
        wait = max(0.0, self.search_reset - time.time()) + 2
        if wait > 0:
            print(f"    search rate limit hit, waiting {wait:.0f}s", flush=True)
            time.sleep(wait)

    # ---------- search ----------

    def search(self, query: str) -> Optional[Dict]:
        url = f"{config.GITHUB_API_BASE}/search/code"
        params = {"q": query, "per_page": SEARCH_PER_PAGE, "page": 1}

        for attempt in range(4):
            self._wait_for_search_slot()
            try:
                response = self.get(
                    url,
                    headers=self.search_headers,
                    params=params,
                    timeout=30,
                )
            except requests.RequestException as exc:
                return {"error": f"request failed: {exc}"}

            self._note_search_rate(response)

            if response.status_code == 200:
                payload = response.json()
                return {
                    "total_count": payload.get("total_count"),
                    "incomplete": payload.get("incomplete_results", False),
                    "items": payload.get("items", [])[:SAMPLE_SIZE],
                }

            if response.status_code == 422:
                return {"error": "422 validation failed (query syntax rejected)"}

            if response.status_code in (403, 429) and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    time.sleep(min(float(retry_after), 120))
                else:
                    self.search_remaining = 0
                    time.sleep(15 * (attempt + 1))
                continue

            return {"error": f"HTTP {response.status_code}"}

        return {"error": "exhausted retries"}

    # ---------- download ----------

    @staticmethod
    def _too_large(response) -> bool:
        raw = response.headers.get("Content-Length")
        if not raw:
            return False
        try:
            return int(raw) > MAX_DOWNLOAD_BYTES
        except ValueError:
            return False

    def _fetch_uncached(self, item: Dict) -> Optional[str]:
        repository = item.get("repository") or {}
        full_name = repository.get("full_name")
        path = item.get("path")
        if not full_name or not path:
            return None

        branch = (
            repository.get("default_branch")
            or self._default_branch(full_name)
        )

        raw_url = (
            f"https://raw.githubusercontent.com/{full_name}/"
            f"{quote(branch, safe='')}/{quote(path, safe='/')}"
        )
        try:
            response = self.get(
                raw_url,
                headers=self.raw_headers,
                timeout=25,
            )
            if response.status_code == 200 and not self._too_large(response):
                return response.text
        except requests.RequestException:
            pass

        api_url = (
            f"{config.GITHUB_API_BASE}/repos/{full_name}/contents/"
            f"{quote(path, safe='/')}"
        )
        try:
            response = self.get(
                api_url,
                headers=self.raw_headers,
                params={"ref": branch},
                timeout=25,
            )
            if response.status_code != 200 or self._too_large(response):
                return None
            if "application/json" in response.headers.get("Content-Type", ""):
                payload = response.json()
                if payload.get("encoding") == "base64":
                    return base64.b64decode(payload.get("content", "")).decode(
                        "utf-8", errors="replace"
                    )
                return None
            return response.text
        except (requests.RequestException, ValueError):
            return None

    def _default_branch(self, full_name: str) -> str:
        try:
            response = self.get(
                f"{config.GITHUB_API_BASE}/repos/{full_name}",
                headers=self.search_headers,
                timeout=20,
            )
            if response.status_code == 200:
                return response.json().get("default_branch") or "main"
        except requests.RequestException:
            pass
        return "main"

    def file_content(self, item: Dict) -> Optional[str]:
        repository = item.get("repository") or {}
        key = f"{repository.get('full_name')}:{item.get('path')}"
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]

        content = self._fetch_uncached(item)
        with self._cache_lock:
            self._cache[key] = content
        return content

    def sample_files(self, items: List[Dict]) -> Dict[str, int]:
        """Download sample and return aggregate row stats."""
        rows = 0
        fetched = 0
        dense = 0
        per_file: List[Tuple[str, int]] = []

        with ThreadPoolExecutor(
            max_workers=min(DOWNLOAD_WORKERS, max(1, len(items)))
        ) as executor:
            futures = {executor.submit(self.file_content, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                repository = item.get("repository") or {}
                label = f"{repository.get('full_name')}/{item.get('path')}"
                try:
                    content = future.result()
                except Exception:
                    content = None

                if not content:
                    continue
                fetched += 1
                count = len(KeyScanner.extract_lines(content))
                if count:
                    rows += count
                    per_file.append((label, count))
                    if count >= DENSE_LINES:
                        dense += 1

        return {
            "rows": rows,
            "fetched": fetched,
            "dense": dense,
            "per_file": per_file,
        }

    # ---------- run ----------

    def run(self) -> List[Dict]:
        results: List[Dict] = []
        print(f"Probing {len(CANDIDATES)} queries, sample={SAMPLE_SIZE}", flush=True)

        for index, (label, query) in enumerate(CANDIDATES, 1):
            print(f"\n[{index}/{len(CANDIDATES)}] {label}: {query}", flush=True)
            found = self.search(query)

            if "error" in found:
                print(f"    ERROR {found['error']}", flush=True)
                results.append({
                    "label": label,
                    "query": query,
                    "error": found["error"],
                })
                time.sleep(random.uniform(0.5, 1.5))
                continue

            total = found["total_count"]
            items = found["items"]
            print(
                f"    total_count={total} sampling {len(items)} files",
                flush=True,
            )

            sample = self.sample_files(items)
            rows = sample["rows"]
            fetched = sample["fetched"]
            per_fetched = round(rows / fetched, 2) if fetched else 0.0

            print(
                f"    fetched={fetched} rows={rows} "
                f"rows/file={per_fetched} dense={sample['dense']}",
                flush=True,
            )
            for name, count in sorted(
                sample["per_file"], key=lambda p: p[1], reverse=True
            )[:3]:
                print(f"      {count:>4}  {name}", flush=True)

            results.append({
                "label": label,
                "query": query,
                "total_count": total,
                "incomplete_results": found["incomplete"],
                "sampled": len(items),
                "fetched": fetched,
                "rows": rows,
                "rows_per_file": per_fetched,
                "dense_files": sample["dense"],
                "truncated": bool(total and total > RESULT_CAP),
                "top_files": [
                    {"file": n, "lines": c}
                    for n, c in sorted(
                        sample["per_file"], key=lambda p: p[1], reverse=True
                    )[:5]
                ],
            })

            time.sleep(random.uniform(0.5, 1.5))

        return results


def verdict(row: Dict) -> str:
    if row.get("error"):
        return "INVALID"
    rows = row.get("rows", 0)
    density = row.get("rows_per_file", 0)
    if rows == 0:
        return "DEAD"
    if density >= 5:
        return "STRONG"
    if density >= 1:
        return "USABLE"
    return "WEAK"


def render_report(results: List[Dict], elapsed: float) -> str:
    ranked = sorted(
        [r for r in results if not r.get("error")],
        key=lambda r: r.get("rows", 0),
        reverse=True,
    )

    lines = [
        "# Search Query Probe",
        "",
        f"- elapsed: {elapsed:.1f}s",
        f"- sample per query: {SAMPLE_SIZE} files",
        f"- dense threshold: {DENSE_LINES} lines/file",
        "",
        "## Ranked by measured rows",
        "",
        "| # | verdict | rows | rows/file | dense | total_count | trunc | query |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(ranked, 1):
        lines.append(
            "| {i} | {v} | {r} | {d} | {dn} | {t} | {tr} | `{q}` |".format(
                i=i,
                v=verdict(row),
                r=row.get("rows", 0),
                d=row.get("rows_per_file", 0),
                dn=row.get("dense_files", 0),
                t=row.get("total_count"),
                tr="yes" if row.get("truncated") else "no",
                q=row.get("query", ""),
            )
        )

    errors = [r for r in results if r.get("error")]
    if errors:
        lines += ["", "## Rejected queries", "", "| query | error |", "|---|---|"]
        for row in errors:
            lines.append(f"| `{row['query']}` | {row['error']} |")

    lines += [
        "",
        "## Suggested file budget",
        "",
    ]
    winners = [r for r in ranked if verdict(r) in ("STRONG", "USABLE")]
    if not winners:
        lines.append("No query produced rows in this sample.")
    else:
        total_rows = sum(r.get("rows", 0) for r in winners) or 1
        lines += ["| query | share |", "|---|---|"]
        for row in winners:
            share = round(row.get("rows", 0) / total_rows * 100, 1)
            lines.append(f"| `{row['query']}` | {share}% |")

    return "\n".join(lines) + "\n"


def main() -> None:
    start = time.time()
    probe = Probe()
    results = probe.run()
    elapsed = time.time() - start

    with open("probe_results.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "elapsed_seconds": round(elapsed, 2),
                "sample_size": SAMPLE_SIZE,
                "dense_threshold": DENSE_LINES,
                "results": results,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )

    report = render_report(results, elapsed)
    with open("probe_report.md", "w", encoding="utf-8") as handle:
        handle.write(report)

    print("\n" + report, flush=True)


if __name__ == "__main__":
    main()
