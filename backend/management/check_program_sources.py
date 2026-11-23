"""Check public New Brunswick CS pilot sources for changes before rule review."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

import requests


SOURCES = {
    "cs_ba": "https://www.cs.rutgers.edu/academics/undergraduate/cs-degrees/b-a-degree?catid=47",
    "cs_bs": "https://www.cs.rutgers.edu/academics/undergraduate/cs-degrees/b-s-degree?view=article",
    "cs_electives": "https://www.cs.rutgers.edu/academics/undergraduate/electives",
    "cs_admission": "https://www.cs.rutgers.edu/academics/undergraduate/admission-to-the-major",
    "cs_transition": "https://www.cs.rutgers.edu/academics/undergraduate/new-introductory-computer-science-course-sequence",
}


class PageText(HTMLParser):
    """Extract normalized page text while ignoring script and style contents."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self.hidden = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden = False

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(" ".join(data.split()))


def fingerprint(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    parser = PageText()
    parser.feed(response.text)
    content = "\n".join(parser.parts)
    if not content:
        raise ValueError(f"No page text returned from {url}")
    return hashlib.sha256(content.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Path to the reviewed source fingerprint file")
    parser.add_argument("--record", action="store_true", help="Record a baseline after reviewing the sources")
    args = parser.parse_args()
    try:
        baseline = {} if args.record else json.loads(args.baseline.read_text())
        if not isinstance(baseline, dict):
            raise ValueError("Baseline must be a JSON object of source fingerprints")
        current = {name: fingerprint(url) for name, url in SOURCES.items()}
        if args.record:
            args.baseline.write_text(json.dumps(current, indent=2) + "\n")
            return 0
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"Source check failed: {exc}")
        return 2

    changed = [name for name in SOURCES if baseline.get(name) != current[name]]
    for name in changed:
        print(f"Review required: {name} ({SOURCES[name]})")
    if not changed:
        print("All monitored program sources match the reviewed baseline.")
    return int(bool(changed))


if __name__ == "__main__":
    raise SystemExit(main())
