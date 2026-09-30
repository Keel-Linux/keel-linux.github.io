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
    reader and a search engine can expect, and the description and social
    tags a shared link is previewed from;
  - a page loads nothing from another origin but the analytics script, and
    neither does a stylesheet: the site is self-hosted, so a reader's
    browser talks to one other party at most, and that one is named here;
  - the copy names no commercial offer, customer or place, and has no em
    dash: the site describes the architecture of the project and nothing
    else, and the house style keeps to plain punctuation.

Pure but for `read_site`: `check` is given a mapping of path to text and
returns the findings, so every rule is tested without a filesystem.
"""

from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser

# Attributes that carry a reference to something else. data-src is where a
# page names a script it loads only when the element comes into view.
REFERENCE_ATTRS = ("href", "src", "srcset", "poster", "data-src")
# The site's own origin: a reference to it is a reference into the tree, and
# is checked as one, so an absolute og:image or canonical URL cannot rot.
SITE_ORIGIN = "https://keellinux.org"
# Attributes whose reference the browser loads, whatever the tag
LOADING_ATTRS = ("src", "srcset", "poster", "data-src")
# rel values of a link element that make the browser load the target
LOADING_RELS = (
    "stylesheet", "icon", "apple-touch-icon", "mask-icon", "manifest",
    "preload", "modulepreload", "prefetch",
)
# The only other origin a page may load from: the analytics script
ALLOWED_RESOURCE_PREFIXES = ("https://analytics.pop.coop/",)
# meta tags a page must carry with a non-empty content: the description a
# search engine shows and the tags a shared link is previewed from
REQUIRED_META = (
    "viewport",
    "description",
    "og:title",
    "og:description",
    "og:image",
    "twitter:card",
)
# meta tags whose content is copy a reader sees, in a result or a preview
COPY_META_KEYS = (
    "description", "keywords", "og:title", "og:description", "og:site_name",
    "og:image:alt", "twitter:title", "twitter:description", "twitter:image:alt",
)
# Attributes that are copy: read aloud, or shown on hover
COPY_ATTRS = ("alt", "title", "aria-label")
# What the site never names. It describes the architecture of Keel Linux:
# no commercial offer, no customer, no place a node runs in. Matched as whole
# words, case insensitively.
FORBIDDEN_TERMS = (
    "pricing", "price", "prices", "customer", "customers", "testimonial",
    "testimonials", "contract", "contracts", "rudder",
    "lisbon", "lisboa", "porto", "madrid", "são paulo", "sao paulo",
    "curitiba", "florianópolis", "florianopolis", "rio de janeiro",
    "brasília", "brasilia",
)
EM_DASH = "\u2014"
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
# Directories that are in the repository but are not the site: this checker,
# its tests, and whatever a tool leaves behind. Packaging metadata is the
# reason this list exists rather than a suffix rule alone: an editable install
# writes *.egg-info/*.txt into the tree, and a .txt is something a site can
# serve, so the tree has to say which directories are the site at all.
EXCLUDE_DIRS = ("tools", "tests", "node_modules", "build", "dist")
EXCLUDE_DIR_SUFFIXES = (".egg-info", ".dist-info")
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
        self.resources: list[str] = []
        self.meta: dict[str, str] = {}
        self.copy: list[str] = []
        self.language = ""
        self._in_title = False
        self._in_h1 = False
        self._hidden = 0

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
        if tag in ("script", "style"):
            self._hidden += 1
        if tag == "meta":
            self._handle_meta(values)
        for attr in REFERENCE_ATTRS:
            value = values.get(attr, "").strip()
            if value:
                self.references.append(value)
                if self._loads(tag, attr, values):
                    self.resources.append(value)
        self.copy.extend(values[attr] for attr in COPY_ATTRS if values.get(attr))

    def _handle_meta(self, values: dict[str, str]) -> None:
        key = (values.get("property") or values.get("name") or "").lower()
        content = values.get("content", "").strip()
        if key and content:
            self.meta[key] = content
        if key in META_REFERENCE_KEYS and content:
            self.references.append(content)
        if key in COPY_META_KEYS:
            self.copy.append(content)

    @staticmethod
    def _loads(tag: str, attr: str, values: dict[str, str]) -> bool:
        """Whether the browser fetches this reference to render the page"""
        if attr in LOADING_ATTRS:
            return True
        if tag == "link" and attr == "href":
            rels = values.get("rel", "").lower().split()
            return any(rel in LOADING_RELS for rel in rels)
        return False

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in ("script", "style") and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.copy.append(data)
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


def on_site_origin(reference: str) -> bool:
    return reference == SITE_ORIGIN or reference.startswith(SITE_ORIGIN + "/")


def from_site_origin(reference: str) -> str:
    """A reference on the site's origin as a path from the site root"""
    rest = reference[len(SITE_ORIGIN):]
    target, sep, fragment = rest.partition("#")
    if not target or target.endswith("/"):
        target += "index.html"
    return target + sep + fragment


def split_fragment(reference: str) -> tuple[str, str]:
    """A reference as (path, fragment); either part may be empty"""
    path, _, fragment = reference.partition("#")
    return path, fragment


def check(
    pages: dict[str, str],
    assets: set[str] | None = None,
    styles: dict[str, str] | None = None,
) -> list[str]:
    """Findings for a site given as {path: text}, one line each

    `assets` is every non page file in the tree, used to find the ones no
    page references. Leave it out to skip that rule. `styles` is the text of
    each stylesheet, checked for what it loads from elsewhere.
    """
    findings: list[str] = []
    parsed = {path: parse(text) for path, text in sorted(pages.items())}
    referenced: set[str] = set()

    for path, page in parsed.items():
        findings.extend(_check_shape(path, page))
        findings.extend(_check_meta(path, page))
        findings.extend(_check_resources(path, page))
        findings.extend(_check_copy(path, page))
        for reference in page.references:
            if reference.startswith("data:"):
                continue
            local = reference
            if on_site_origin(reference):
                local = from_site_origin(reference)
            elif is_external(reference):
                findings.extend(_check_external(path, reference))
                continue
            target, fragment = split_fragment(local)
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
    findings.extend(check_styles(styles or {}))
    return findings


def _check_meta(path: str, page: Page) -> list[str]:
    return [
        f"{path}: no {key} meta" for key in REQUIRED_META if key not in page.meta
    ]


def _loads_elsewhere(reference: str) -> bool:
    if reference.startswith("data:") or on_site_origin(reference):
        return False
    if not is_external(reference) or reference.startswith("mailto:"):
        return False
    return not reference.startswith(ALLOWED_RESOURCE_PREFIXES)


def _check_resources(path: str, page: Page) -> list[str]:
    return [
        f"{path}: {reference} loads an external resource"
        for reference in page.resources
        if _loads_elsewhere(reference)
    ]


def _check_copy(path: str, page: Page) -> list[str]:
    text = " ".join(page.copy)
    lowered = text.lower()
    findings = [
        f"{path}: the copy names {term!r}"
        for term in FORBIDDEN_TERMS
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", lowered)
    ]
    if EM_DASH in text:
        findings.append(f"{path}: the copy has an em dash")
    return findings


# url(...) and @import in a stylesheet, quoted or not
STYLE_REFERENCE = re.compile(
    r"""url\(\s*['"]?([^'")\s]+)|@import\s+['"]([^'"]+)['"]"""
)


def check_styles(styles: dict[str, str]) -> list[str]:
    """Findings for stylesheets given as {path: text}: what they load"""
    findings = []
    for path, text in sorted(styles.items()):
        for match in STYLE_REFERENCE.finditer(text):
            reference = match.group(1) or match.group(2)
            if _loads_elsewhere(reference):
                findings.append(f"{path}: {reference} loads an external resource")
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
        dirs[:] = [name for name in dirs if not _is_excluded_dir(name)]
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


def _is_excluded_dir(name: str) -> bool:
    """Whether a directory is repository furniture rather than the site"""
    return (
        name.startswith(".")
        or name in EXCLUDE_DIRS
        or name.endswith(EXCLUDE_DIR_SUFFIXES)
    )


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    pages, assets = read_site(root)
    if not pages:
        print(f"{root}: no pages found", file=sys.stderr)
        return 2
    styles = {}
    for asset in sorted(assets):
        if asset.endswith(".css"):
            with open(os.path.join(root, asset), encoding="utf-8") as fob:
                styles[asset] = fob.read()
    findings = check(pages, assets, styles)
    for finding in findings:
        print(finding)
    print(
        f"{len(pages)} pages, {len(assets)} assets, {len(findings)} findings",
        file=sys.stderr,
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
