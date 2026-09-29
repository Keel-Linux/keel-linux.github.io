# keellinux.org

The project site, served by GitHub Pages from `main`: three static pages, one
stylesheet and the brand assets. Nothing builds it, so what is in the
repository is what the browser gets.

| Path | What it is |
|------|------------|
| `index.html` | the home page, also served at `www` |
| `architecture.html` | the architecture the project aims for, in three scenarios, served at `/architecture` |
| `guidelines.html` | how the organization works, and the mark |
| `style.css` | the whole stylesheet, light and dark |
| `assets/` | the mark in its variants and the social card |
| `tools/sitecheck.py` | the checks a build step would have done |
| `tests/` | one test per rule, ending with the site itself |

## The check

```
python3 tools/sitecheck.py .
```

It exits 0 when the site is sound and 1 with one line per finding: an
internal link that resolves to nothing, a fragment naming an id that is not
there, a referenced asset that is missing, an asset no page references, an
external link that is not https, or a page without a language, a title or
exactly one h1. The gate `python / coverage` runs the same checks on every
pull request and is required on `main`.
