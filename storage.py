"""Append-only storage for leaked account lines."""
import os
import threading
from typing import Dict, Iterable, List

import config
from line_format import normalize_account_line


class Storage:
    def __init__(self, path: str = config.RESULTS_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._seen = set(self.load_lines())

    def load_lines(self) -> List[str]:
        if not os.path.exists(self.path):
            return []

        with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
            lines = []
            for line in handle:
                clean = normalize_account_line(line)
                if clean:
                    lines.append(clean)
            return lines

    def append_line(self, line: str) -> bool:
        """Append one canonical line immediately and return True when written."""
        clean = normalize_account_line(line)
        if not clean:
            return False

        with self._lock:
            if clean in self._seen:
                return False

            parent = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(parent, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(clean + "\n")
                handle.flush()

            self._seen.add(clean)
            return True

    def save_scan_result(self, result: Dict) -> str:
        """Compatibility wrapper used by the API and CLI."""
        for line in result.get("keys", []):
            self.append_line(line)
        return self.path

    def export_plain_text(self, keys: Iterable[str], filename: str) -> str:
        """Export lines to a specific text file, one line at a time."""
        target = Storage(filename)
        for key in keys:
            target.append_line(key)
        return target.path

    # Compatibility methods for the existing API.
    def load_found_keys(self) -> List[str]:
        return self.load_lines()

    def load_valid_keys(self) -> List[str]:
        return self.load_lines()

    def save_validation_result(self, result: Dict) -> str:
        for line in result.get("valid", []):
            self.append_line(line)
        return self.path
