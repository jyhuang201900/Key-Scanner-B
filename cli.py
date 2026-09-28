"""Command-line entry point."""
import argparse

import config
from scanner import KeyScanner
from storage import Storage


def main() -> None:
    parser = argparse.ArgumentParser(description="Outlook leak line scanner")
    parser.add_argument(
        "action",
        nargs="?",
        default="scan",
        choices=["scan"],
        help="scan GitHub and append matches to results.txt",
    )
    parser.parse_args()

    storage = Storage(config.RESULTS_FILE)
    scanner = KeyScanner(on_found=storage.append_line)
    result = scanner.scan()

    print(f"Saved to: {config.RESULTS_FILE}")
    print(f"New unique lines: {result['total_found']}")


if __name__ == "__main__":
    main()
