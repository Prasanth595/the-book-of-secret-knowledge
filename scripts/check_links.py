#!/usr/bin/env python3
"""Validate Markdown and HTML links with no third-party dependencies."""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import html
import json
import pathlib
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


HTML_LINK_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""", re.IGNORECASE)
SKIP_SCHEMES = {"mailto", "tel", "data", "javascript", "ftp", "irc", "ircs"}
TRANSIENT_STATUSES = {401, 403, 408, 429, 500, 502, 503, 504}
BROKEN_STATUSES = {400, 404, 410, 451}


@dataclasses.dataclass(frozen=True)
class LinkRef:
    source: pathlib.Path
    line: int
    target: str


@dataclasses.dataclass(frozen=True)
class LinkResult:
    target: str
    status: str
    detail: str
    refs: tuple[LinkRef, ...]
    elapsed_ms: int = 0

    @property
    def is_failure(self) -> bool:
        return self.status in {"broken", "missing-file", "invalid-url"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Markdown files to scan.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent external link checks.")
    parser.add_argument("--retries", type=int, default=1, help="Retries for transient network failures.")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    parser.add_argument("--max-external", type=int, default=0, help="Check only the first N unique external links.")
    return parser.parse_args()


def normalize_target(raw: str) -> str:
    target = html.unescape(raw.strip())
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target


def markdown_url_part(raw: str) -> str:
    if not raw:
        return ""
    if raw.startswith("<"):
        closing = raw.find(">")
        if closing != -1:
            return raw[1:closing]
    return raw.split(maxsplit=1)[0]


def extract_markdown_targets(line: str) -> list[str]:
    targets: list[str] = []
    search_from = 0
    while True:
        marker = line.find("](", search_from)
        if marker == -1:
            return targets

        opening_bracket = line.rfind("[", 0, marker)
        if opening_bracket == -1 or (opening_bracket > 0 and line[opening_bracket - 1] == "!"):
            search_from = marker + 2
            continue

        pos = marker + 2
        depth = 0
        content: list[str] = []
        while pos < len(line):
            char = line[pos]
            if char == "\\" and pos + 1 < len(line):
                content.append(char)
                pos += 1
                content.append(line[pos])
            elif char == "(":
                depth += 1
                content.append(char)
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
                content.append(char)
            else:
                content.append(char)
            pos += 1

        if pos >= len(line):
            search_from = marker + 2
            continue

        target = markdown_url_part("".join(content).strip())
        if target:
            targets.append(target)
        search_from = pos + 1


def extract_links(path: pathlib.Path) -> list[LinkRef]:
    refs: list[LinkRef] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in extract_markdown_targets(line):
            target = normalize_target(match)
            if target:
                refs.append(LinkRef(path, line_no, target))
        for match in HTML_LINK_RE.findall(line):
            target = normalize_target(match)
            if target:
                refs.append(LinkRef(path, line_no, target))
    return refs


def is_external(target: str) -> bool:
    parsed = urllib.parse.urlparse(target)
    return parsed.scheme in {"http", "https"}


def should_skip(target: str) -> bool:
    if target.startswith("#"):
        return True
    parsed = urllib.parse.urlparse(target)
    return parsed.scheme.lower() in SKIP_SCHEMES


def check_internal(target: str, refs: tuple[LinkRef, ...], root: pathlib.Path) -> LinkResult:
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme or parsed.netloc:
        return LinkResult(target, "skipped", "unsupported scheme", refs)

    if not parsed.path:
        return LinkResult(target, "ok", "document anchor", refs)

    source_dir = refs[0].source.parent
    candidate = (source_dir / urllib.parse.unquote(parsed.path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return LinkResult(target, "invalid-url", "path escapes repository", refs)

    if candidate.exists():
        return LinkResult(target, "ok", "local file exists", refs)
    return LinkResult(target, "missing-file", f"missing local file: {candidate.relative_to(root)}", refs)


def http_request(target: str, method: str, timeout: float) -> tuple[int | None, str]:
    req = urllib.request.Request(
        target,
        method=method,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; the-book-of-secret-knowledge-link-checker/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, response.url


def check_external(target: str, refs: tuple[LinkRef, ...], timeout: float, retries: int) -> LinkResult:
    start = time.monotonic()
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return LinkResult(target, "invalid-url", "invalid external URL", refs)

    last_error = ""
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            status, final_url = http_request(target, "HEAD", timeout)
            if status in {405, 501}:
                status, final_url = http_request(target, "GET", timeout)
            elapsed = int((time.monotonic() - start) * 1000)
            detail = str(status) if final_url == target else f"{status} -> {final_url}"
            if status is not None and 200 <= status < 400:
                return LinkResult(target, "ok", detail, refs, elapsed)
            if status in BROKEN_STATUSES:
                return LinkResult(target, "broken", detail, refs, elapsed)
            if status in TRANSIENT_STATUSES:
                return LinkResult(target, "transient", detail, refs, elapsed)
            return LinkResult(target, "warning", detail, refs, elapsed)
        except urllib.error.HTTPError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            detail = str(exc.code)
            if exc.code in {400, 404, 405, 410, 451, 501}:
                try:
                    status, final_url = http_request(target, "GET", timeout)
                    detail = str(status) if final_url == target else f"{status} -> {final_url}"
                    if status is not None and 200 <= status < 400:
                        return LinkResult(target, "ok", detail, refs, elapsed)
                    if status in BROKEN_STATUSES:
                        return LinkResult(target, "broken", detail, refs, elapsed)
                except Exception as inner_exc:  # noqa: BLE001 - report external failure text.
                    last_error = f"{type(inner_exc).__name__}: {inner_exc}"
                if exc.code in BROKEN_STATUSES:
                    return LinkResult(target, "broken", detail, refs, elapsed)
            elif exc.code in TRANSIENT_STATUSES:
                last_error = detail
            else:
                return LinkResult(target, "warning", detail, refs, elapsed)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < attempts - 1:
            time.sleep(0.4 * (attempt + 1))

    elapsed = int((time.monotonic() - start) * 1000)
    return LinkResult(target, "transient", last_error or "request failed", refs, elapsed)


def group_refs(refs: Iterable[LinkRef]) -> dict[str, list[LinkRef]]:
    grouped: dict[str, list[LinkRef]] = defaultdict(list)
    for ref in refs:
        if not should_skip(ref.target):
            grouped[ref.target].append(ref)
    return grouped


def format_ref(ref: LinkRef) -> str:
    return f"{ref.source.as_posix()}:{ref.line}"


def print_text(results: list[LinkResult]) -> None:
    for result in results:
        if result.status == "ok":
            continue
        first_ref = format_ref(result.refs[0])
        print(f"{result.status.upper():12} {result.target} ({result.detail}) at {first_ref}")

    failures = [r for r in results if r.is_failure]
    warnings = [r for r in results if r.status in {"warning", "transient"}]
    print(f"\nChecked {len(results)} unique links: {len(failures)} failures, {len(warnings)} warnings/transients.")


def print_markdown(results: list[LinkResult]) -> None:
    failures = [r for r in results if r.is_failure]
    warnings = [r for r in results if r.status in {"warning", "transient"}]
    print(f"Checked **{len(results)}** unique links: **{len(failures)}** failures, **{len(warnings)}** warnings/transients.")
    actionable = failures + warnings
    if not actionable:
        return
    print("\n| Status | URL | Detail | First reference |")
    print("| --- | --- | --- | --- |")
    for result in actionable:
        print(f"| {result.status} | `{result.target}` | {result.detail} | `{format_ref(result.refs[0])}` |")


def print_json(results: list[LinkResult]) -> None:
    payload = [
        {
            "target": result.target,
            "status": result.status,
            "detail": result.detail,
            "elapsed_ms": result.elapsed_ms,
            "refs": [format_ref(ref) for ref in result.refs],
        }
        for result in results
    ]
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    root = pathlib.Path.cwd().resolve()
    paths = [pathlib.Path(path) for path in args.paths]

    refs: list[LinkRef] = []
    for path in paths:
        if not path.exists():
            print(f"missing input file: {path}", file=sys.stderr)
            return 2
        refs.extend(extract_links(path))

    grouped = group_refs(refs)
    internal = {target: tuple(items) for target, items in grouped.items() if not is_external(target)}
    external = {target: tuple(items) for target, items in grouped.items() if is_external(target)}
    if args.max_external:
        external = dict(list(external.items())[: args.max_external])

    results: list[LinkResult] = []
    results.extend(check_internal(target, refs_for_target, root) for target, refs_for_target in internal.items())

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(check_external, target, refs_for_target, args.timeout, args.retries)
            for target, refs_for_target in external.items()
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: (item.status, item.target))
    if args.format == "json":
        print_json(results)
    elif args.format == "markdown":
        print_markdown(results)
    else:
        print_text(results)

    return 1 if any(result.is_failure for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
