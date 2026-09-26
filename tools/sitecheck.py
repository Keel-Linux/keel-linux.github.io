# Copyright (c) 2026 KeelLinux maintainers
"""What a static site must satisfy before it is served

The site is the public face of the project and nothing builds it: the files
in the repository are the files the browser gets. So the checks that a build
step would have done are here instead, and the gate runs them over the
repository's own pages.

What is checked, and why each one is worth a failed build:

  - every internal link resolves to a file in the repository, so a page
    never answers 404 from its own navigation;
  - every fragment resolves to an id on the page it names, including the
    fragments of another page, which is what silently rots when a heading
    is renamed;
  - every asset a page references exists, and every asset in the tree is
    referenced by some page, so a removed image is caught and an orphan is
    not served forever;
  - an external link is https, because a page served over TLS that links
    over plain HTTP teaches the reader the wrong habit;
  - a page carries a title, a language and one h1, which is the least a
    reader and a search engine can expect.

Pure but for `read_site`: `check` is given a mapping of path to text and
returns the findings, so every rule is tested without a filesystem.
"""

from __future__ import annotations

import os
import sys
from html.parser import HTMLParser

# Attributes that carry a reference to something else
REFERENCE_ATTRS = ("href", "src", "srcset", "poster")
# Extensions that are pages rather than assets
PAGE_SUFFIX = ".html"
# meta tags whose content is a reference, not text: the social card is
# fetched by a crawler, so a wrong path there breaks a link nobody sees
# until it is shared
META_REFERENCE_KEYS = (
    "og:image",
    "og:image:url",
    "og:url",
    "twitter:image",
)
# What the site serves. A file of any other kind in the tree is repository
# furniture (this checker, its tests, the packaging) and is not an asset.
ASSET_SUFFIXES = (
    ".css", ".js", ".png", ".svg", ".jpg", ".jpeg", ".webp", ".avif",
    ".ico", ".gif", ".woff", ".woff2", ".txt", ".json", ".xml", ".pdf",
    ".webmanifest",
)


class Page(HTMLParser):
    """The parts of one page the checks look at"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.ids: set[str] = set()
        self.titles: list[str] = []
        self.headings: list[str] = []
        self.language = ""
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: (value or "") for name, value in attrs}
        if tag == "html":
            self.language = values.get("lang", "")
        if tag == "title":
            self._in_title = True
            self.titles.append("")
        if tag == "h1":
            self._in_h1 = True
            self.headings.append("")
        if "id" in values and values["id"]:
            self.ids.add(values["id"])
        if tag == "meta":
            key = values.get("property") or values.get("name") or ""
            content = values.get("content", "").strip()
            if key.lower() in META_REFERENCE_KEYS and content:
                self.references.append(content)
        for attr in REFERENCE_ATTRS:
            value = values.get(attr, "").strip()
            if value:
                self.references.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._in_title and self.titles:
            self.titles[-1] += data
        if self._in_h1 and self.headings:
            self.headings[-1] += data


def parse(text: str) -> Page:
    page = Page()
    page.feed(text)
    page.close()
    return page


def is_external(reference: str) -> bool:
    return "//" in reference.split("?")[0] or reference.startswith("mailto:")


def split_fragment(reference: str) -> tuple[str, str]:
    """A reference as (path, fragment); either part may be empty"""
    path, _, fragment = reference.partition("#")
    return path, fragment


def check(pages: dict[str, str], assets: set[str] | None = None) -> list[str]:
    """Findings for a site given as {path: text}, one line each

    `assets` is every non page file in the tree, used to find the ones no
    page references. Leave it out to skip that rule.
    """
    findings: list[str] = []
    parsed = {path: parse(text) for path, text in sorted(pages.items())}
    referenced: set[str] = set()

    for path, page in parsed.items():
        findings.extend(_check_shape(path, page))
        for reference in page.references:
            if reference.startswith("data:"):
                continue
            if is_external(reference):
                findings.extend(_check_external(path, reference))
                continue
            target, fragment = split_fragment(reference)
            if target:
                referenced.add(_resolve(path, target))
            findings.extend(
                _check_internal(
                    path, reference, target, fragment, parsed, assets
                )
            )

    if assets is not None:
        for asset in sorted(assets - referenced):
            findings.append(f"{asset}: no page references it")
    return findings


def _check_shape(path: str, page: Page) -> list[str]:
    findings = []
    if not page.language.strip():
        findings.append(f"{path}: the html element has no lang")
    titles = [title.strip() for title in page.titles if title.strip()]
    if not titles:
        findings.append(f"{path}: no title")
    headings = [text.strip() for text in page.headings if text.strip()]
    if len(headings) != 1:
        findings.append(f"{path}: {len(headings)} h1 elements, expected 1")
    return findings


def _check_external(path: str, reference: str) -> list[str]:
    if reference.startswith(("https://", "mailto:")):
        return []
    return [f"{path}: {reference} is not https"]


def _resolve(path: str, target: str) -> str:
    """A reference on `path` as a site path, without normalising away ..

    A target that climbs above the site root is returned as it was, so the
    internal check reports it as missing rather than reaching outside.
    """
    if target.startswith("/"):
        return target.lstrip("/")
    base = os.path.dirname(path)
    joined = os.path.normpath(os.path.join(base, target)) if base else target
    return os.path.normpath(joined)


def _check_internal(
    path: str,
    reference: str,
    target: str,
    fragment: str,
    parsed: dict[str, Page],
    assets: set[str] | None,
) -> list[str]:
    """Findings for one internal reference made on `path`

    A reference to a page is resolved against the pages, which are all
    known. A reference to an asset is resolved against `assets` when the
    caller gave them, and left alone when it did not, so a caller that only
    has the pages is not told that every image is missing.
    """
    findings = []
    resolved = _resolve(path, target) if target else path
    if target and not _resolves(resolved, parsed, assets):
        return [f"{path}: {reference} does not resolve to a file"]
    if not fragment:
        return findings
    if resolved not in parsed:
        return [
            f"{path}: {reference} names a fragment of a file"
            " that is not a page"
        ]
    if fragment not in parsed[resolved].ids:
        findings.append(f"{path}: {reference} names an id that is not there")
    return findings


def _resolves(
    resolved: str, parsed: dict[str, Page], assets: set[str] | None
) -> bool:
    if resolved.endswith(PAGE_SUFFIX):
        return resolved in parsed
    if assets is None:
        return True
    return resolved in assets


def read_site(root: str) -> tuple[dict[str, str], set[str]]:
    """The pages and the assets of the tree at `root`"""
    pages: dict[str, str] = {}
    assets: set[str] = set()
    for base, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            full = os.path.join(base, name)
            path = os.path.relpath(full, root)
            if name.endswith(PAGE_SUFFIX):
                with open(full, encoding="utf-8") as fob:
                    pages[path] = fob.read()
            elif name.lower().endswith(ASSET_SUFFIXES):
                assets.add(path)
    return pages, assets


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    pages, assets = read_site(root)
    if not pages:
        print(f"{root}: no pages found", file=sys.stderr)
        return 2
    findings = check(pages, assets)
    for finding in findings:
        print(finding)
    print(
        f"{len(pages)} pages, {len(assets)} assets, {len(findings)} findings",
        file=sys.stderr,
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
