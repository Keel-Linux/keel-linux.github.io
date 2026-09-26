# Copyright (c) 2026 KeelLinux maintainers
"""Every rule the site checker enforces, and the site itself

The checker is a pure function of a mapping of path to text, so each rule is
stated here as the smallest page that breaks it. The last test runs the
checker over the repository it lives in, which is what the gate does: the
rules are only worth having if the site actually satisfies them.
"""

import os
import sys
import unittest
from os.path import abspath, dirname, join

ROOT = dirname(dirname(abspath(__file__)))
sys.path.insert(0, join(ROOT, "tools"))

import sitecheck  # noqa: E402

HEAD = '<!doctype html><html lang="en"><head><title>Keel</title></head><body>'
BODY = "<h1>Keel</h1>"


def page(body: str = "", head: str = HEAD, heading: str = BODY) -> str:
    return f"{head}{heading}{body}</body></html>"


class TestShape(unittest.TestCase):
    def test_a_well_formed_page_has_no_findings(self):
        self.assertEqual(sitecheck.check({"index.html": page()}), [])

    def test_a_page_without_a_language_is_reported(self):
        text = page(head="<!doctype html><html><head><title>K</title></head><body>")
        self.assertIn(
            "index.html: the html element has no lang",
            sitecheck.check({"index.html": text}),
        )

    def test_a_page_without_a_title_is_reported(self):
        text = page(head='<!doctype html><html lang="en"><body>')
        self.assertIn("index.html: no title", sitecheck.check({"index.html": text}))

    def test_an_empty_title_counts_as_none(self):
        text = page(head='<!doctype html><html lang="en"><title>  </title><body>')
        self.assertIn("index.html: no title", sitecheck.check({"index.html": text}))

    def test_a_page_without_an_h1_is_reported(self):
        findings = sitecheck.check({"index.html": page(heading="<p>no heading</p>")})
        self.assertIn("index.html: 0 h1 elements, expected 1", findings)

    def test_two_h1_elements_are_reported(self):
        text = page(heading="<h1>one</h1><h1>two</h1>")
        self.assertIn(
            "index.html: 2 h1 elements, expected 1",
            sitecheck.check({"index.html": text}),
        )


class TestInternalLinks(unittest.TestCase):
    def test_a_link_to_a_missing_page_is_reported(self):
        findings = sitecheck.check({"index.html": page('<a href="gone.html">x</a>')})
        self.assertEqual(
            findings, ["index.html: gone.html does not resolve to a file"]
        )

    def test_a_link_to_a_page_that_is_there_passes(self):
        pages = {"index.html": page('<a href="two.html">x</a>'), "two.html": page()}
        self.assertEqual(sitecheck.check(pages), [])

    def test_a_link_out_of_the_site_root_is_reported(self):
        findings = sitecheck.check(
            {"index.html": page('<a href="../secret.html">x</a>')}
        )
        self.assertEqual(
            findings, ["index.html: ../secret.html does not resolve to a file"]
        )

    def test_an_absolute_path_is_read_from_the_site_root(self):
        pages = {"index.html": page('<a href="/two.html">x</a>'), "two.html": page()}
        self.assertEqual(sitecheck.check(pages), [])

    def test_a_link_from_a_page_in_a_directory_resolves_beside_it(self):
        pages = {
            "docs/one.html": page('<a href="two.html">x</a>'),
            "docs/two.html": page(),
        }
        self.assertEqual(sitecheck.check(pages), [])


class TestFragments(unittest.TestCase):
    def test_a_fragment_on_the_same_page_must_exist(self):
        text = page('<a href="#nowhere">x</a>')
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: #nowhere names an id that is not there"],
        )

    def test_a_fragment_that_exists_passes(self):
        text = page('<a href="#here">x</a><section id="here"></section>')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_fragment_of_another_page_must_exist_there(self):
        pages = {
            "index.html": page('<a href="two.html#gone">x</a>'),
            "two.html": page('<section id="here"></section>'),
        }
        self.assertEqual(
            sitecheck.check(pages),
            ["index.html: two.html#gone names an id that is not there"],
        )

    def test_a_fragment_of_another_page_that_exists_passes(self):
        pages = {
            "index.html": page('<a href="two.html#here">x</a>'),
            "two.html": page('<section id="here"></section>'),
        }
        self.assertEqual(sitecheck.check(pages), [])

    def test_a_fragment_of_an_asset_is_reported(self):
        text = page('<a href="assets/a.svg#part">x</a>')
        findings = sitecheck.check({"index.html": text}, {"assets/a.svg"})
        self.assertEqual(
            findings,
            [
                "index.html: assets/a.svg#part names a fragment of a file"
                " that is not a page"
            ],
        )

    def test_an_empty_id_attribute_is_not_a_target(self):
        text = page('<a href="#x">x</a><section id=""></section>')
        self.assertEqual(len(sitecheck.check({"index.html": text})), 1)


class TestAssets(unittest.TestCase):
    def test_a_referenced_asset_that_is_missing_is_reported(self):
        text = page('<img src="assets/gone.png">')
        self.assertEqual(
            sitecheck.check({"index.html": text}, set()),
            ["index.html: assets/gone.png does not resolve to a file"],
        )

    def test_a_referenced_asset_that_is_there_passes(self):
        text = page('<img src="assets/here.png">')
        self.assertEqual(sitecheck.check({"index.html": text}, {"assets/here.png"}), [])

    def test_an_asset_no_page_references_is_reported(self):
        findings = sitecheck.check({"index.html": page()}, {"assets/orphan.png"})
        self.assertEqual(findings, ["assets/orphan.png: no page references it"])

    def test_assets_are_not_checked_when_none_are_given(self):
        text = page('<img src="assets/unknown.png">')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_the_social_card_of_a_meta_tag_counts_as_a_reference(self):
        text = page(
            '<meta property="og:image" content="assets/card.png">'
        )
        self.assertEqual(sitecheck.check({"index.html": text}, {"assets/card.png"}), [])

    def test_a_twitter_image_counts_as_a_reference(self):
        text = page('<meta name="twitter:image" content="assets/card.png">')
        self.assertEqual(sitecheck.check({"index.html": text}, {"assets/card.png"}), [])

    def test_a_meta_tag_that_is_not_a_reference_is_ignored(self):
        text = page('<meta name="theme-color" content="#0B1F3A">')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_poster_and_a_stylesheet_count_as_references(self):
        text = page(
            '<link rel="stylesheet" href="style.css">'
            '<video poster="assets/still.png"></video>'
        )
        self.assertEqual(
            sitecheck.check({"index.html": text}, {"style.css", "assets/still.png"}),
            [],
        )


class TestExternalLinks(unittest.TestCase):
    def test_an_https_link_passes(self):
        text = page('<a href="https://example.org/x">x</a>')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_plain_http_link_is_reported(self):
        text = page('<a href="http://example.org/x">x</a>')
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: http://example.org/x is not https"],
        )

    def test_a_protocol_relative_link_is_reported(self):
        text = page('<a href="//example.org/x">x</a>')
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: //example.org/x is not https"],
        )

    def test_a_mailto_link_passes(self):
        text = page('<a href="mailto:admin@example.org">x</a>')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_data_uri_is_not_a_reference(self):
        text = page('<img src="data:image/gif;base64,R0lGOD">')
        self.assertEqual(sitecheck.check({"index.html": text}, set()), [])


class TestReadSite(unittest.TestCase):
    def test_it_reads_pages_and_assets_and_skips_the_rest(self):
        pages, assets = sitecheck.read_site(ROOT)
        self.assertIn("index.html", pages)
        self.assertIn("assets/keel-mark.svg", assets)
        self.assertNotIn("tools/sitecheck.py", assets)
        self.assertFalse([path for path in assets if path.startswith(".git")])

    def test_packaging_metadata_is_not_part_of_the_site(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            for directory in ("site.egg-info", "tools", "tests", "build"):
                os.makedirs(join(tmp, directory))
                with open(join(tmp, directory, "leftover.txt"), "w") as fob:
                    fob.write("x")
            with open(join(tmp, "index.html"), "w") as fob:
                fob.write(page())
            pages, assets = sitecheck.read_site(tmp)

        self.assertEqual(sorted(pages), ["index.html"])
        self.assertEqual(assets, set())

    def test_a_dotted_directory_is_skipped(self):
        pages, assets = sitecheck.read_site(ROOT)
        self.assertFalse([path for path in pages if "/." in path])


class TestCommandLine(unittest.TestCase):
    def test_the_site_of_this_repository_has_no_findings(self):
        self.assertEqual(sitecheck.main(["sitecheck", ROOT]), 0)

    def test_a_tree_with_no_page_is_a_usage_failure(self):
        self.assertEqual(sitecheck.main(["sitecheck", join(ROOT, "assets")]), 2)

    def test_it_exits_1_on_a_finding(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with open(join(tmp, "index.html"), "w") as fob:
                fob.write(page('<a href="gone.html">x</a>'))
            self.assertEqual(sitecheck.main(["sitecheck", tmp]), 1)

    def test_the_script_runs_as_a_program(self):
        import subprocess

        out = subprocess.run(
            [sys.executable, join(ROOT, "tools", "sitecheck.py"), ROOT],
            capture_output=True,
            text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("findings", out.stderr)

    def test_the_default_root_is_the_working_directory(self):
        here = os.getcwd()
        os.chdir(ROOT)
        try:
            self.assertEqual(sitecheck.main(["sitecheck"]), 0)
        finally:
            os.chdir(here)


if __name__ == "__main__":
    unittest.main()
