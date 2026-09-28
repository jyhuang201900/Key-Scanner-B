"""Empirical probe: measure real row yield per GitHub code search query.

Design constraints learned the hard way:
  * code search is 10 req/min, so every retry is expensive;
  * a probe that does real work for 30 queries will blow the job timeout;
  * partial results are more useful than no results, so everything is
    written incrementally and the run stops at a wall-clock deadline.

Downloads use raw.githubusercontent.com only. There is deliberately no
contents-API fallback: a fallback costs a core API call per file and can
consume the entire job budget on its own.
"""
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
from scanner import KeyScanner, item_ref_candidates


# (label, query). Kept small on purpose: every query costs a search call
# plus a sample of downloads.
CANDIDATES: List[Tuple[str, str]] = [
    ("A complete", "MsaArtifacts"),
    ("A complete", "MsaArtifacts hotmail"),
    ("A complete", "MsaArtifacts outlook"),
    ("B filename", "hotmail filename:results"),
    ("B filename", "outlook filename:results"),
    ("B filename", "hotmail filename:accounts"),
    ("B filename", "outlook filename:accounts"),
    ("B filename", "hotmail filename:token"),
    ("B filename", "outlook filename:token"),
    ("B filename", "hotmail filename:email"),
    ("B filename", "outlook filename:email"),
    ("C cooccur", "hotmail refreshtoken"),
    ("C cooccur", "outlook refreshtoken"),
    ("C cooccur", "hotmail clientid"),
]

SAMPLE_SIZE = int(os.getenv("PROBE_SAMPLE", "6"))
SEARCH_PER_PAGE = int(os.getenv("PROBE_PER_PAGE", "20"))
DOWNLOAD_WORKERS = int(os.getenv("PROBE_WORKERS", "8"))
MAX_DOWNLOAD_BYTES = int(os.getenv("PROBE_MAX_BYTES", str(400 * 1024)))
DENSE_LINES = int(os.getenv("PROBE_DENSE_LINES", "20"))
DEADLINE_SECONDS = int(os.getenv("PROBE_DEADLINE", "900"))
RESULT_CAP = 1000
RESULTS_JSON = "probe_results.json"
REPORT_MD = "probe_report.md"


class Deadline:
    def __init__(self, seconds: int) -> None:
        self.started = time.time()
        self.seconds = seconds

    def expired(self) -> bool:
        return (time.time() - self.started) > self.seconds

    def remaining(self) -> int:
        return max(0, int(self.seconds - (time.time() - self.started)))


def build_session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.4,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16),
    )
    return session


class Probe:
    def __init__(self, deadline: Deadline) -> None:
        if not config.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN is required")

        self.deadline = deadline
        self.search_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.text-match+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "outlook-leak-probe",
        }
        self.raw_headers = {
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "User-Agent": "outlook-leak-probe",
        }
        self._local = threading.local()
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

    def _note_rate(self, response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is None or reset is None:
            return
        try:
            self.search_remaining = int(remaining)
            self.search_reset = int(reset)
        except ValueError:
            pass

    def _wait_for_slot(self) -> bool:
        """Sleep only if the search budget is exhausted. False on timeout."""
        if self.search_remaining is None or self.search_remaining > 0:
            return True
        wait = int(self.search_reset - time.time()) + 1
        if wait <= 0:
            self.search_remaining = 1
            return True
        wait = min(wait, max(0, self.deadline.remaining() - 30))
        if wait <= 0:
            return False
        print(f"    rate limited, sleeping {wait}s", flush=True)
        time.sleep(wait)
        self.search_remaining = 1
        return not self.deadline.expired()

    def search(self, query: str) -> Dict:
        url = f"{config.GITHUB_API_BASE}/search/code"
        params = {"q": query, "per_page": SEARCH_PER_PAGE, "page": 1}

        for attempt in range(2):
            if not self._wait_for_slot():
                return {"error": "deadline reached while rate limited"}
            try:
                response = self.get(
                    url,
                    headers=self.search_headers,
                    params=params,
                    timeout=30,
                )
            except requests.RequestException as exc:
                return {"error": f"request failed: {exc}"}

            self._note_rate(response)

            if response.status_code == 200:
                payload = response.json()
                return {
                    "total_count": payload.get("total_count"),
                    "incomplete": payload.get("incomplete_results", False),
                    "items": payload.get("items", [])[:SAMPLE_SIZE],
                }
            if response.status_code == 422:
                return {"error": "422 rejected"}
            if response.status_code in (403, 429) and attempt == 0:
                self.search_remaining = 0
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        self.search_reset = time.time() + float(retry_after)
                    except ValueError:
                        pass
                continue
            return {"error": f"HTTP {response.status_code}"}

        return {"error": "rate limited twice"}

    def fetch_raw(self, item: Dict) -> Optional[str]:
        repository = item.get("repository") or {}
        full_name = repository.get("full_name")
        path = item.get("path")
        if not full_name or not path:
            return None

        for ref in item_ref_candidates(item):
            url = (
                f"https://raw.githubusercontent.com/{full_name}/"
                f"{quote(ref, safe='')}/{quote(path, safe='/')}"
            )
            try:
                response = self.get(url, headers=self.raw_headers, timeout=20)
            except requests.RequestException:
                continue
            if response.status_code != 200:
                continue
            raw_len = response.headers.get("Content-Length")
            if raw_len:
                try:
                    if int(raw_len) > MAX_DOWNLOAD_BYTES:
                        return None
                except ValueError:
                    pass
            return response.text
        return None

    def sample(self, items: List[Dict]) -> Dict:
        rows = 0
        fetched = 0
        dense = 0
        per_file: List[Tuple[str, int]] = []

        if not items:
            return {"rows": 0, "fetched": 0, "dense": 0, "per_file": []}

        with ThreadPoolExecutor(
            max_workers=min(DOWNLOAD_WORKERS, len(items))
        ) as executor:
            futures = {executor.submit(self.fetch_raw, i): i for i in items}
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

        return {"rows": rows, "fetched": fetched, "dense": dense, "per_file": per_file}

    def run(self) -> List[Dict]:
        results: List[Dict] = []
        print(
            f"probing {len(CANDIDATES)} queries, sample={SAMPLE_SIZE}, "
            f"deadline={self.deadline.seconds}s",
            flush=True,
        )

        for index, (label, query) in enumerate(CANDIDATES, 1):
            if self.deadline.expired():
                print("deadline reached, stopping early", flush=True)
                break

            print(f"\n[{index}/{len(CANDIDATES)}] {label}: {query}", flush=True)
            found = self.search(query)

            if "error" in found:
                print(f"    ERROR {found['error']}", flush=True)
                results.append({"label": label, "query": query, "error": found["error"]})
                self._flush(results)
                continue

            total = found["total_count"]
            items = found["items"]
            print(f"    total_count={total}, sampling {len(items)}", flush=True)

            stats = self.sample(items)
            density = round(stats["rows"] / stats["fetched"], 2) if stats["fetched"] else 0
            print(
                f"    fetched={stats['fetched']} rows={stats['rows']} "
                f"rows/file={density} dense={stats['dense']}",
                flush=True,
            )
            for name, count in sorted(stats["per_file"], key=lambda p: -p[1])[:3]:
                print(f"      {count:>4}  {name}", flush=True)

            results.append({
                "label": label,
                "query": query,
                "total_count": total,
                "incomplete_results": found["incomplete"],
                "sampled": len(items),
                "fetched": stats["fetched"],
                "rows": stats["rows"],
                "rows_per_file": density,
                "dense_files": stats["dense"],
                "truncated": bool(total and total > RESULT_CAP),
                "top_files": [
                    {"file": n, "lines": c}
                    for n, c in sorted(stats["per_file"], key=lambda p: -p[1])[:5]
                ],
            })
            self._flush(results)
            time.sleep(random.uniform(0.3, 0.8))

        return results

    def _flush(self, results: List[Dict]) -> None:
        """Write partial results after every query so a timeout still leaves data."""
        try:
            with open(RESULTS_JSON, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "sample_size": SAMPLE_SIZE,
                        "dense_threshold": DENSE_LINES,
                        "deadline_seconds": self.deadline.seconds,
                        "elapsed_seconds": round(time.time() - self.deadline.started, 1),
                        "results": results,
                    },
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError:
            pass


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


def render(results: List[Dict], elapsed: float, deadline: int) -> str:
    ok = [r for r in results if not r.get("error")]
    ranked = sorted(ok, key=lambda r: r.get("rows", 0), reverse=True)

    out = [
        "# Search Query Probe",
        "",
        f"- elapsed: {elapsed:.0f}s / budget {deadline}s",
        f"- queries completed: {len(results)}/{len(CANDIDATES)}",
        f"- sample per query: {SAMPLE_SIZE} files",
        f"- dense threshold: {DENSE_LINES} rows/file",
        "",
        "## Ranked by measured rows",
        "",
        "| # | verdict | rows | rows/file | dense | total_count | trunc | query |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(ranked, 1):
        out.append(
            f"| {i} | {verdict(row)} | {row.get('rows',0)} | "
            f"{row.get('rows_per_file',0)} | {row.get('dense_files',0)} | "
            f"{row.get('total_count')} | "
            f"{'yes' if row.get('truncated') else 'no'} | `{row.get('query','')}` |"
        )

    bad = [r for r in results if r.get("error")]
    if bad:
        out += ["", "## Rejected", "", "| query | error |", "|---|---|"]
        out += [f"| `{r['query']}` | {r['error']} |" for r in bad]

    out += ["", "## Suggested budget", ""]
    winners = [r for r in ranked if verdict(r) in ("STRONG", "USABLE")]
    if not winners:
        out.append("No query produced rows in this sample.")
    else:
        pool = sum(r.get("rows", 0) for r in winners) or 1
        out += ["| query | share |", "|---|---|"]
        out += [
            f"| `{r['query']}` | {round(r.get('rows',0)/pool*100,1)}% |"
            for r in winners
        ]
    return "\n".join(out) + "\n"


def main() -> None:
    deadline = Deadline(DEADLINE_SECONDS)
    probe = Probe(deadline)
    results = probe.run()
    elapsed = time.time() - deadline.started

    probe._flush(results)
    with open(REPORT_MD, "w", encoding="utf-8") as handle:
        handle.write(render(results, elapsed, DEADLINE_SECONDS))
    print("\n" + render(results, elapsed, DEADLINE_SECONDS), flush=True)


if __name__ == "__main__":
    main()
