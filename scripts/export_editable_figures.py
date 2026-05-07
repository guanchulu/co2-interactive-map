"""Create editable, module-grouped SVG versions of manuscript figures.

The review PPT uses raster previews for readability. This exporter keeps the
source figures as SVG vectors, wraps visible elements into named groups, and
writes a small manifest so figures can be edited panel by panel in Illustrator,
Inkscape, Figma, or PowerPoint after SVG-to-shape conversion.
"""

from __future__ import annotations

import csv
import html
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "docs" / "joule_submission"
OUT = SUBMISSION / "figures_editable_svg"
MANIFEST = SUBMISSION / "editable_figure_manifest.csv"
INDEX = SUBMISSION / "editable_figures_index.html"
README = SUBMISSION / "editable_figures_readme.md"

FIGURE_SOURCES = [
    ("nature_joule_v2", SUBMISSION / "figures_nature_joule_v2"),
    ("main_storyline", SUBMISSION / "figures_storyline"),
    ("composite", SUBMISSION / "figures_composite"),
    ("legacy", SUBMISSION / "figures"),
]

ELEMENT_PREFIXES = (
    "<rect",
    "<text",
    "<line",
    "<circle",
    "<path",
    "<polygon",
    "<polyline",
)

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class Frame:
    group_id: str
    title: str
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


def attr(line: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', line)
    return match.group(1) if match else None


def num_attr(line: str, name: str, default: float = 0.0) -> float:
    value = attr(line, name)
    if value is None:
        return default
    if value.endswith("%"):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def text_value(line: str) -> str:
    match = re.search(r"<text[^>]*>(.*?)</text>", line)
    if not match:
        return ""
    return re.sub(r"<[^>]+>", "", html.unescape(match.group(1))).strip()


def points_bbox(points: str) -> tuple[float, float, float, float] | None:
    values = [float(value) for value in NUMBER_RE.findall(points)]
    if len(values) < 2:
        return None
    xs = values[0::2]
    ys = values[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def element_point(line: str) -> tuple[float, float] | None:
    stripped = line.strip()
    if stripped.startswith("<rect"):
        return (
            num_attr(line, "x") + num_attr(line, "width") / 2,
            num_attr(line, "y") + num_attr(line, "height") / 2,
        )
    if stripped.startswith("<text"):
        return num_attr(line, "x"), num_attr(line, "y")
    if stripped.startswith("<circle"):
        return num_attr(line, "cx"), num_attr(line, "cy")
    if stripped.startswith("<line"):
        return (
            (num_attr(line, "x1") + num_attr(line, "x2")) / 2,
            (num_attr(line, "y1") + num_attr(line, "y2")) / 2,
        )
    if stripped.startswith(("<polygon", "<polyline")):
        bbox = points_bbox(attr(line, "points") or "")
        if bbox:
            x1, y1, x2, y2 = bbox
            return (x1 + x2) / 2, (y1 + y2) / 2
    if stripped.startswith("<path"):
        bbox = points_bbox(attr(line, "d") or "")
        if bbox:
            x1, y1, x2, y2 = bbox
            return (x1 + x2) / 2, (y1 + y2) / 2
    return None


def visual_lines(lines: list[str]) -> list[str]:
    output: list[str] = []
    in_style = False
    in_defs = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<style"):
            in_style = True
        if stripped.startswith("<defs"):
            in_defs = True
        if not in_style and not in_defs and stripped.startswith(ELEMENT_PREFIXES):
            output.append(line)
        if "</style>" in stripped:
            in_style = False
        if "</defs>" in stripped:
            in_defs = False
    return output


def panel_letter_and_title(lines: list[str], x: float, y: float, w: float) -> tuple[str | None, str]:
    letter: str | None = None
    title = ""
    for line in lines:
        if not line.strip().startswith("<text"):
            continue
        tx = num_attr(line, "x")
        ty = num_attr(line, "y")
        if not (x <= tx <= x + w and y <= ty <= y + 48):
            continue
        value = text_value(line)
        if len(value) == 1 and value.isalpha() and letter is None:
            letter = value.upper()
        elif value and not title:
            title = value
    return letter, title


def detect_panel_frames(lines: list[str]) -> list[Frame]:
    frames: list[Frame] = []
    for line in lines:
        if not line.strip().startswith("<rect"):
            continue
        x = num_attr(line, "x")
        y = num_attr(line, "y")
        w = num_attr(line, "width")
        h = num_attr(line, "height")
        stroke = attr(line, "stroke") or ""
        fill = attr(line, "fill") or ""
        if w < 180 or h < 120 or stroke in ("", "none"):
            continue
        if fill.lower() not in {"#ffffff", "#f7f9f9", "#f6f8f8"}:
            continue
        letter, title = panel_letter_and_title(lines, x, y, w)
        if not letter:
            continue
        frames.append(Frame(f"panel-{letter}", title or f"Panel {letter}", x, y, w, h))
    return frames


def detect_module_frames(lines: list[str]) -> list[Frame]:
    frames: list[Frame] = []
    for line in lines:
        if not line.strip().startswith("<rect"):
            continue
        x = num_attr(line, "x")
        y = num_attr(line, "y")
        w = num_attr(line, "width")
        h = num_attr(line, "height")
        stroke = attr(line, "stroke") or ""
        fill = attr(line, "fill") or ""
        if w < 80 or h < 35 or stroke in ("", "none") or fill.lower() == "#ffffff":
            continue
        if x == 0 and y == 0:
            continue
        title = ""
        for candidate in lines:
            if not candidate.strip().startswith("<text"):
                continue
            px = num_attr(candidate, "x")
            py = num_attr(candidate, "y")
            if x <= px <= x + w and y <= py <= y + h:
                title = text_value(candidate)
                break
        frames.append(Frame(f"module-{len(frames) + 1:02d}", title or f"Module {len(frames) + 1}", x, y, w, h))
    return frames


def split_svg(lines: list[str]) -> tuple[list[str], list[str]]:
    header: list[str] = []
    body: list[str] = []
    in_style = False
    in_defs = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("</svg"):
            continue
        if stripped.startswith("<svg") or stripped.startswith("<style") or stripped.startswith("<defs"):
            header.append(line)
            in_style = stripped.startswith("<style") and "</style>" not in stripped
            in_defs = stripped.startswith("<defs") and "</defs>" not in stripped
            continue
        if in_style or in_defs:
            header.append(line)
            if "</style>" in stripped:
                in_style = False
            if "</defs>" in stripped:
                in_defs = False
            continue
        body.append(line)
    return header, body


def assign_groups(body: list[str], frames: list[Frame]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"canvas-title-background": []}
    for frame in frames:
        groups[frame.group_id] = []
    for line in body:
        point = element_point(line)
        target = None
        if point:
            px, py = point
            for frame in frames:
                if frame.contains(px, py):
                    target = frame.group_id
                    break
        groups[target or "canvas-title-background"].append(line)
    return groups


def grouped_svg(source: Path, destination: Path, source_group: str) -> list[dict[str, str]]:
    lines = source.read_text(encoding="utf-8").splitlines()
    header, body = split_svg(lines)
    candidates = visual_lines(body)
    frames = detect_panel_frames(candidates) or detect_module_frames(candidates)
    groups = assign_groups(body, frames)

    output: list[str] = []
    output.extend(header)
    output.append(f'<metadata>editable-source={source_group}/{source.name}; groups=panels-or-modules</metadata>')
    for group_id, items in groups.items():
        if not items:
            continue
        output.append(f'<g id="{group_id}" data-editable-group="{group_id}">')
        output.extend(f"  {item}" for item in items)
        output.append("</g>")
    output.append("</svg>")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")

    rows: list[dict[str, str]] = []
    frame_lookup = {frame.group_id: frame for frame in frames}
    for group_id, items in groups.items():
        frame = frame_lookup.get(group_id)
        rows.append(
            {
                "source_group": source_group,
                "figure": source.name,
                "editable_path": str(destination.relative_to(ROOT)),
                "group_id": group_id,
                "group_title": frame.title if frame else "Canvas, title, background, legends outside panels",
                "x": f"{frame.x:.1f}" if frame else "",
                "y": f"{frame.y:.1f}" if frame else "",
                "width": f"{frame.w:.1f}" if frame else "",
                "height": f"{frame.h:.1f}" if frame else "",
                "object_count": str(len(items)),
            }
        )
    return rows


def write_index(rows: list[dict[str, str]]) -> None:
    by_path: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_path.setdefault(row["editable_path"], []).append(row)

    body = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><title>Editable CO2 figures</title>",
        "<style>body{font-family:Arial,sans-serif;margin:28px;color:#202426} a{color:#225f74} table{border-collapse:collapse;width:100%;margin:12px 0 28px} td,th{border:1px solid #d6dedf;padding:6px 8px;font-size:13px} th{background:#f4f7f7;text-align:left} .hint{color:#627176}</style>",
        "</head><body>",
        "<h1>Editable CO2 manuscript figures</h1>",
        "<p class='hint'>Open the SVG files in Illustrator, Inkscape, Figma, or PowerPoint. Groups are named by panel/module; text remains editable text and vector shapes remain separate objects.</p>",
    ]
    for path, path_rows in sorted(by_path.items()):
        full_path = ROOT / path
        rel = full_path.relative_to(INDEX.parent).as_posix()
        body.append(f"<h2><a href='{html.escape(rel)}'>{html.escape(Path(path).name)}</a></h2>")
        body.append(f"<object data='{html.escape(rel)}' type='image/svg+xml' width='720'></object>")
        body.append("<table><tr><th>Group</th><th>Title</th><th>Objects</th></tr>")
        for row in path_rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(row['group_id'])}</td>"
                f"<td>{html.escape(row['group_title'])}</td>"
                f"<td>{html.escape(row['object_count'])}</td>"
                "</tr>"
            )
        body.append("</table>")
    body.append("</body></html>")
    INDEX.write_text("\n".join(body), encoding="utf-8")


def write_readme() -> None:
    README.write_text(
        "\n".join(
            [
                "# Editable figure package",
                "",
                "Use `figures_editable_svg/` for manual figure editing.",
                "",
                "- SVG files are grouped by panel or module.",
                "- Text remains editable text.",
                "- Rectangles, lines, circles, paths, polygons, and polylines remain vector objects.",
                "- In PowerPoint, insert an SVG and use Graphic Format > Convert to Shape when available.",
                "- For dense map panels, prefecture polygons are separate vector objects but grouped inside the map panel.",
                "",
                "Open `editable_figures_index.html` for a quick visual index.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, str]] = []
    for source_group, source_dir in FIGURE_SOURCES:
        if not source_dir.exists():
            continue
        for source in sorted(source_dir.glob("*.svg")):
            destination = OUT / source_group / source.name
            all_rows.extend(grouped_svg(source, destination, source_group))

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_group",
                "figure",
                "editable_path",
                "group_id",
                "group_title",
                "x",
                "y",
                "width",
                "height",
                "object_count",
            ],
        )
        writer.writeheader()
        writer.writerows(all_rows)
    write_index(all_rows)
    write_readme()
    print(OUT)
    print(MANIFEST)
    print(INDEX)
    print(f"editable_svgs={len({row['editable_path'] for row in all_rows})}")
    print(f"editable_groups={len(all_rows)}")


if __name__ == "__main__":
    main()
