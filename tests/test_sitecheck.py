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

META = (
    '<meta name="viewport" content="width=device-width">'
    '<meta name="description" content="Keel">'
    '<meta property="og:title" content="Keel">'
    '<meta property="og:description" content="Keel">'
    '<meta property="og:image" content="https://example.org/card.png">'
    '<meta name="twitter:card" content="summary_large_image">'
)
HEAD = (
    '<!doctype html><html lang="en"><head><title>Keel</title>'
    f"{META}</head><body>"
)
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

    def test_a_version_query_names_the_same_asset(self):
        text = page('<a href="assets/a.svg?v=2026093001">x</a>')
        self.assertEqual(
            sitecheck.check({"index.html": text}, {"assets/a.svg"}), []
        )

    def test_a_version_query_on_a_missing_asset_is_reported(self):
        text = page('<a href="assets/b.svg?v=1">x</a>')
        self.assertEqual(
            len(sitecheck.check({"index.html": text}, {"assets/a.svg"})), 2
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


class TestRequiredMeta(unittest.TestCase):
    def test_a_page_without_a_description_is_reported(self):
        text = page(head=HEAD.replace('name="description"', 'name="x"'))
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: no description meta"],
        )

    def test_every_missing_social_tag_is_reported(self):
        head = '<!doctype html><html lang="en"><head><title>K</title></head><body>'
        findings = sitecheck.check({"index.html": page(head=head)})
        for key in sitecheck.REQUIRED_META:
            self.assertIn(f"index.html: no {key} meta", findings)

    def test_an_empty_content_counts_as_missing(self):
        text = page(
            head=HEAD.replace(
                '<meta name="twitter:card" content="summary_large_image">',
                '<meta name="twitter:card" content=" ">',
            )
        )
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: no twitter:card meta"],
        )


class TestSiteOrigin(unittest.TestCase):
    def test_a_link_on_the_site_origin_is_checked_as_internal(self):
        text = page('<a href="https://keellinux.org/gone.html">x</a>')
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            [
                "index.html: https://keellinux.org/gone.html"
                " does not resolve to a file"
            ],
        )

    def test_the_origin_itself_is_the_home_page(self):
        text = page('<link rel="canonical" href="https://keellinux.org/">')
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_social_card_on_the_origin_counts_as_a_reference(self):
        text = page(
            '<meta property="og:image"'
            ' content="https://keellinux.org/assets/card.png">'
        )
        self.assertEqual(
            sitecheck.check({"index.html": text}, {"assets/card.png"}), []
        )

    def test_a_fragment_on_the_origin_is_checked(self):
        pages = {
            "index.html": page('<a href="https://keellinux.org/two.html#no">x</a>'),
            "two.html": page(),
        }
        self.assertEqual(
            sitecheck.check(pages),
            [
                "index.html: https://keellinux.org/two.html#no"
                " names an id that is not there"
            ],
        )


class TestExternalResources(unittest.TestCase):
    def test_an_external_script_is_reported(self):
        text = page('<script src="https://cdn.example.org/x.js"></script>')
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            [
                "index.html: https://cdn.example.org/x.js"
                " loads an external resource"
            ],
        )

    def test_an_external_stylesheet_is_reported(self):
        text = page(
            '<link rel="stylesheet" href="https://fonts.example.org/a.css">'
        )
        self.assertEqual(len(sitecheck.check({"index.html": text})), 1)

    def test_an_external_image_is_reported(self):
        text = page('<img src="https://example.org/a.png" alt="">')
        self.assertEqual(len(sitecheck.check({"index.html": text})), 1)

    def test_a_lazily_loaded_module_counts_as_a_resource(self):
        text = page('<div data-src="https://example.org/m.js"></div>')
        self.assertEqual(len(sitecheck.check({"index.html": text})), 1)

    def test_a_lazily_loaded_module_is_an_asset_reference(self):
        text = page('<div data-src="assets/js/m.js"></div>')
        self.assertEqual(
            sitecheck.check({"index.html": text}, {"assets/js/m.js"}), []
        )

    def test_the_analytics_script_is_allowed(self):
        text = page(
            '<script defer src="https://analytics.pop.coop/js/script.js">'
            "</script>"
        )
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_an_external_link_is_not_a_resource(self):
        text = page(
            '<a href="https://github.com/keel-linux">x</a>'
            '<link rel="canonical" href="https://example.org/">'
        )
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_an_external_url_in_a_stylesheet_is_reported(self):
        styles = {
            "style.css": "a{background:url('https://example.org/a.png')}"
            "@import url(//fonts.example.org/b.css);"
        }
        self.assertEqual(
            sitecheck.check_styles(styles),
            [
                "style.css: https://example.org/a.png"
                " loads an external resource",
                "style.css: //fonts.example.org/b.css"
                " loads an external resource",
            ],
        )

    def test_a_local_url_in_a_stylesheet_passes(self):
        styles = {"style.css": 'a{background:url("assets/a.svg")} b{x:url(data:,)}'}
        self.assertEqual(sitecheck.check_styles(styles), [])

    def test_check_includes_the_stylesheets_it_is_given(self):
        findings = sitecheck.check(
            {"index.html": page()},
            styles={"style.css": "@import 'https://example.org/c.css';"},
        )
        self.assertEqual(
            findings,
            ["style.css: https://example.org/c.css loads an external resource"],
        )


class TestCopy(unittest.TestCase):
    def test_a_forbidden_term_in_the_text_is_reported(self):
        text = page("<p>See our Pricing page.</p>")
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: the copy names 'pricing'"],
        )

    def test_a_city_is_reported(self):
        text = page("<p>A node in Lisbon.</p>")
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: the copy names 'lisbon'"],
        )

    def test_a_term_inside_a_longer_word_is_not_reported(self):
        text = page("<p>Priceless and contractual are fine.</p>")
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_a_forbidden_term_in_an_attribute_or_meta_is_reported(self):
        text = page(
            '<img src="data:," alt="customer logo">'
            '<meta name="keywords" content="rudder">'
        )
        findings = sitecheck.check({"index.html": text})
        self.assertIn("index.html: the copy names 'customer'", findings)
        self.assertIn("index.html: the copy names 'rudder'", findings)

    def test_scripts_and_styles_are_not_copy(self):
        text = page("<script>var price = 1;</script><style>.pricing{}</style>")
        self.assertEqual(sitecheck.check({"index.html": text}), [])

    def test_an_em_dash_in_the_copy_is_reported(self):
        text = page("<p>One file — the truth.</p>")
        self.assertEqual(
            sitecheck.check({"index.html": text}),
            ["index.html: the copy has an em dash"],
        )


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

    def test_it_reads_the_stylesheets_of_the_tree(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with open(join(tmp, "index.html"), "w") as fob:
                fob.write(page('<link rel="stylesheet" href="style.css">'))
            with open(join(tmp, "style.css"), "w") as fob:
                fob.write("@import 'https://example.org/c.css';")
            self.assertEqual(sitecheck.main(["sitecheck", tmp]), 1)

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
