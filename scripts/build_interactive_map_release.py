"""Build public-release packages for the interactive CO2 map.

Outputs:
- docs/interactive_map_public/static_site/: normal static site for GitHub Pages,
  Cloudflare Pages, Netlify, Vercel, or any static file host.
- docs/interactive_map_public/standalone_html/co2_interactive_map_standalone.html:
  one-file version that can be opened directly without a local HTTP server.
- ZIP archives under docs/joule_submission/.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "interactive_map"
OUT = ROOT / "docs" / "interactive_map_public"
STATIC = OUT / "static_site"
STANDALONE = OUT / "standalone_html"
SUBMISSION = ROOT / "docs" / "joule_submission"


DATA_FILES = {
    "data/city_boundaries.geojson": SRC / "data" / "city_boundaries.geojson",
    "data/city_metrics.json": SRC / "data" / "city_metrics.json",
    "data/route_links.json": SRC / "data" / "route_links.json",
    "data/supporting_tables.json": SRC / "data" / "supporting_tables.json",
    "data/summary.json": SRC / "data" / "summary.json",
}


def clean_dir(path: Path) -> None:
    resolved = path.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"Refusing to delete outside repository: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_static_site() -> None:
    clean_dir(STATIC)
    for item in SRC.iterdir():
        if item.name.startswith("preview_"):
            continue
        target = STATIC / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    (STATIC / ".nojekyll").write_text("", encoding="utf-8")
    (STATIC / "README_DEPLOY.md").write_text(
        """# China CO2 Allocation Interactive Map

This folder is a static website. Upload the folder contents to any static host.

Recommended public deployment options:

1. GitHub Pages
   - Create a public GitHub repository.
   - Upload every file in this `static_site` folder to the repository root.
   - In GitHub, open Settings -> Pages.
   - Set Source to `Deploy from a branch`, branch `main`, folder `/root`.
   - The map will be available at `https://<user>.github.io/<repo>/`.

2. Cloudflare Pages
   - Create a Pages project.
   - Upload this folder directly or connect a GitHub repository.
   - Build command: leave empty.
   - Output directory: `/` if uploading this folder, or `docs/interactive_map_public/static_site` if deploying the full repository.

3. Netlify or Vercel
   - Drag-and-drop this folder in the web UI.
   - No build command is required.

Do not open `index.html` directly from disk for the normal static-site version,
because browsers may block local JSON/GeoJSON fetches. Use a static host or the
single-file standalone HTML package instead.
""",
        encoding="utf-8",
    )


def js_string_safe(value: str) -> str:
    return value.replace("</script>", "<\\/script>")


def build_standalone_html() -> Path:
    clean_dir(STANDALONE)
    html = (SRC / "index.html").read_text(encoding="utf-8")
    css = (SRC / "styles.css").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    data = {
        key: json.loads(path.read_text(encoding="utf-8"))
        for key, path in DATA_FILES.items()
    }
    data_json = js_string_safe(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    fetch_shim = f"""<script>
window.__CO2_MAP_DATA__ = {data_json};
window.fetch = async function(url) {{
  const key = String(url).replace(/^\\.\\//, "");
  if (!Object.prototype.hasOwnProperty.call(window.__CO2_MAP_DATA__, key)) {{
    throw new Error(`Inline map data not found: ${{key}}`);
  }}
  return {{
    ok: true,
    json: async () => JSON.parse(JSON.stringify(window.__CO2_MAP_DATA__[key])),
  }};
}};
</script>"""
    html = html.replace('<link rel="stylesheet" href="./styles.css" />', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="./app.js"></script>', f"{fetch_shim}\n<script>\n{js_string_safe(app)}\n</script>")
    out = STANDALONE / "co2_interactive_map_standalone.html"
    out.write_text(html, encoding="utf-8")
    (STANDALONE / "README.md").write_text(
        """# Standalone Interactive Map

Open `co2_interactive_map_standalone.html` directly in a modern browser.
All JSON, GeoJSON, CSS, and JavaScript are embedded in the file.
""",
        encoding="utf-8",
    )
    return out


def zip_dir(source: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source))


def main() -> None:
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    copy_static_site()
    standalone = build_standalone_html()
    static_zip = SUBMISSION / "co2_interactive_map_static_site.zip"
    standalone_zip = SUBMISSION / "co2_interactive_map_standalone_html.zip"
    zip_dir(STATIC, static_zip)
    zip_dir(STANDALONE, standalone_zip)
    print(f"static_site={STATIC}")
    print(f"standalone_html={standalone}")
    print(f"static_zip={static_zip}")
    print(f"standalone_zip={standalone_zip}")


if __name__ == "__main__":
    main()
