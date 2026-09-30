# keellinux.org

The project site, served by GitHub Pages from `main`: six static pages, one
stylesheet, four small scripts and the brand assets. Nothing builds it, so
what is in the repository is what the browser gets.

| Path | What it is |
|------|------------|
| `index.html` | the home page, also served at `www` |
| `architecture.html` | composition, overlays, appliances, the manifest, the spec, IPv6-first, layers and upgrades |
| `security.html` | keys and identity, the request pipeline, what each installation mode enables, exposure classes |
| `cloud.html` | installation modes, the mesh, the registry, failover, replication, backup and monitoring |
| `roadmap.html` | a copy of the roadmap, tracker#46, phase by phase |
| `guidelines.html` | how the organization works, and the mark |
| `style.css` | the whole stylesheet, light and dark |
| `assets/js/site.js` | theme toggle, menu, scroll reveal, and the loader of the modules below |
| `assets/js/mesh.js`, `pipeline.js`, `terminal.js` | the hero's mesh, the request pipeline and the terminal replay; each loads only when its element comes into view |
| `assets/` | the mark in its variants and the social card |
| `tools/sitecheck.py` | the checks a build step would have done |
| `tests/` | one test per rule, ending with the site itself |

Every page works without JavaScript, and the animations stop under
`prefers-reduced-motion`. Nothing is loaded from another origin but the
Plausible analytics script.

## The check

```
python3 tools/sitecheck.py .
```

It exits 0 when the site is sound and 1 with one line per finding: an
internal link that resolves to nothing, a fragment naming an id that is not
there, a referenced asset that is missing, an asset no page references, an
external link that is not https, a page without a language, a title,
exactly one h1, a description or the social tags, a resource loaded from
another origin than the analytics one (in a page or in a stylesheet), and
copy that names a commercial offer, a customer or a city, or has an em
dash. A reference to `https://keellinux.org/` is checked as a path in the
tree. The gate `python / coverage` runs the same checks on every pull
request and is required on `main`.
