#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the SRS 'Shipped model catalogue' chapter from model.json.

Everything in the catalogue is derived from geest/resources/model.json at
build time so the SRS can never drift from the shipped model. Outputs:

- srs/generated/model-catalogue.md          — chapter 8 markdown (included
  into GeoE3_SRS.md by build_docx.py via an include marker)
- srs/diagrams/fig19-model-overview.puml    — whole-model WBS tree
- srs/diagrams/fig20..22-dim-*.puml         — one WBS tree per dimension
- srs/diagrams/fig23-indicator-processor-matrix.svg/.png — the matrix,
  drawn as SVG and rasterised with PIL from the same geometry.

Usage: gen_model_catalogue.py <model.json> <srs-dir>
Set LATO_DIR to the directory holding the Lato *.ttf files (falls back to a
/nix/store glob).
"""

import glob
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MODEL_PATH = Path(sys.argv[1])
SRS = Path(sys.argv[2])
GEN = SRS / "generated"
DIA = SRS / "diagrams"
GEN.mkdir(exist_ok=True)

model = json.loads(MODEL_PATH.read_text())
DIMS = model["dimensions"]

# --------------------------------------------------------------------------
# Brand palette (kartoza.iuml / brand pack)
# --------------------------------------------------------------------------
CHARCOAL = "#383939"
GREY = "#676869"
LIGHT_GREY = "#D1D1D1"
PAPER = "#F5F5F2"
BLUE = "#54A2CC"
BLUE_TINT = "#EAF3FA"
AMBER = "#EEB348"
AMBER_TINT = "#FCF3E0"
WHITE = "#FFFFFF"

DIM_BAND = {"contextual": BLUE, "accessibility": AMBER, "place_characterization": GREY}

# --------------------------------------------------------------------------
# Processor registry: flag -> (matrix label, workflow class, SRS section)
# Order and grouping mirror chapter 6 (Processor reference).
# --------------------------------------------------------------------------
PROCESSORS = [
    ("use_index_score", "Index score", "DefaultIndexScoreWorkflow", "6.1.1"),
    ("use_contextual_index_score", "Contextual index", "ContextualIndexScoreWorkflow", "6.1.2"),
    ("use_eplex_score", "EPLEX score", "EPLEXWorkflow", "6.1.3"),
    ("use_index_score_with_ghsl", "Index + GHSL", "IndexScoreWithGHSLWorkflow", "6.1.4"),
    ("use_index_score_with_ookla", "Index + Ookla", "IndexScoreWithOoklaWorkflow", "6.1.5"),
    ("use_point_per_cell", "Points per cell", "PointPerCellWorkflow", "6.2.1"),
    ("use_polyline_per_cell", "Polylines per cell", "PolylinePerCellWorkflow", "6.2.1"),
    ("use_polygon_per_cell", "Polygons per cell", "PolygonPerCellWorkflow", "6.2.2"),
    ("use_osm_transport_polyline_per_cell", "OSM transport", "OsmTransportPolylinePerCellWorkflow", "6.2.3"),
    ("use_single_buffer_point", "Single buffer", "SinglePointBufferWorkflow", "6.3.1"),
    (
        "use_multi_buffer_point",
        "Multi-buffer / isochrone",
        "MultiBufferDistancesNativeWorkflow · MultiBufferDistancesORSWorkflow",
        "6.3.2–6.3.3",
    ),
    ("use_street_lights", "Street lights", "StreetLightsBufferWorkflow", "6.3.4"),
    ("use_environmental_hazards", "Hazard raster", "RasterReclassificationWorkflow", "6.4.1"),
    ("use_nighttime_lights", "Night-time lights", "SafetyRasterWorkflow", "6.4.2"),
    ("use_classify_polygon_into_classes", "Classify polygons", "ClassifiedPolygonWorkflow", "6.5.1"),
    ("use_classify_safety_polygon_into_classes", "Classify safety", "SafetyPolygonWorkflow", "6.5.1"),
    ("use_csv_to_point_layer", "ACLED CSV", "AcledImpactWorkflow", "6.6.1"),
]
FLAG_INDEX = {flag: n for n, (flag, *_rest) in enumerate(PROCESSORS)}
FAMILIES = [  # (label, first flag index, count) — mirrors §6 families
    ("Index scores", 0, 5),
    ("Per-cell", 5, 4),
    ("Buffers", 9, 3),
    ("Rasters", 12, 2),
    ("Classify", 14, 2),
    ("Conflict", 16, 1),
]

# Compact display names for the matrix rows, keyed by indicator id.
SHORT = {
    "eplex_score_indicator": "EPLEX score",
    "Workplace_Index": "WBL Workplace Index",
    "Pay_Parenthood_Index": "WBL Pay & Parenthood Index",
    "Entrepreneurship_Index": "WBL Entrepreneurship Index",
    "Kindergartens_Location": "Kindergartens / childcare",
    "Primary_School_Location": "Primary schools",
    "Groceries_Location": "Groceries",
    "Pharmacies_Location": "Pharmacies",
    "Green_Space_location": "Green spaces",
    "Public_Transport_location": "Public transport stops",
    "Hospital_Location": "Hospitals & clinics",
    "Universities_Location": "Universities & tech schools",
    "Banks_Location": "Banks & financial facilities",
    "Active_Transport_Network": "Active transport network",
    "Street_Lights": "Street / night-time lights",
    "FCV": "ACLED conflict events",
    "Education": "Labour force with degrees",
    "Digital_Inclusion": "Internet use (% population)",
    "Fire": "Fire hazard",
    "Flood": "Flood hazard",
    "Landslide": "Landslide hazard",
    "Cyclone": "Tropical cyclone hazard",
    "Drought": "Drought hazard",
    "Water_Sanitation": "Water & sanitation facilities",
}


def short_name(ind):
    return SHORT.get(ind["id"], ind["indicator"])


def enabled_flags(ind):
    return [f for (f, *_r) in PROCESSORS if ind.get(f)]


def fmt_weight(w):
    return f"{float(w):.2f}".rstrip("0").rstrip(".") if w is not None else "—"


# --------------------------------------------------------------------------
# 1. WBS diagrams (PlantUML)
# --------------------------------------------------------------------------
WBS_STYLE = f"""<style>
wbsDiagram {{
  FontName Lato
  FontColor {CHARCOAL}
  LineColor #8A8B8B
  node {{ BackgroundColor {WHITE}; LineColor #8A8B8B; RoundCorner 8; Padding 6; Margin 4 }}
  :depth(0) {{ BackgroundColor {BLUE}; FontColor {WHITE}; FontStyle bold; LineColor {BLUE} }}
  :depth(1) {{ BackgroundColor {BLUE_TINT}; LineColor {BLUE}; FontStyle bold }}
  :depth(2) {{ BackgroundColor {AMBER_TINT}; LineColor {AMBER} }}
}}
</style>"""


def wbs(path, root, children):
    """children: list of (label, [grandchild labels])."""
    lines = ["@startwbs", WBS_STYLE, f"* {root}"]
    for n, (label, kids) in enumerate(children):
        side = "<" if n % 2 else ""  # alternate sides to stay compact
        lines.append(f"**{side} {label}")
        for kid in kids:
            lines.append(f"***{side} {kid}")
    lines.append("@endwbs")
    path.write_text("\n".join(lines) + "\n")


wbs(
    DIA / "fig19-model-overview.puml",
    "GeoE3 analysis model\\n<size:11>3 dimensions · 16 factors · 24 indicators</size>",
    [
        (
            f"{d['name']}\\n<size:11>weight {fmt_weight(d.get('default_analysis_weighting'))}</size>",
            [
                f"{f['name']}\\n<size:10>{len(f.get('indicators', []))} indicator"
                + ("s" if len(f.get("indicators", [])) != 1 else "")
                + "</size>"
                for f in d["factors"]
            ],
        )
        for d in DIMS
    ],
)

DIM_FIG_FILE = {}
for n, d in enumerate(DIMS):
    fname = f"fig{20 + n}-dim-{d['id'].replace('_', '-')}.puml"
    DIM_FIG_FILE[d["id"]] = fname.replace(".puml", ".png")
    wbs(
        DIA / fname,
        f"{d['name']}\\n<size:11>weight {fmt_weight(d.get('default_analysis_weighting'))}</size>",
        [
            (
                f"{f['name']}\\n<size:10>weight {fmt_weight(f.get('default_dimension_weighting'))}</size>",
                [short_name(i) for i in f.get("indicators", [])],
            )
            for f in d["factors"]
        ],
    )

# --------------------------------------------------------------------------
# 2. Indicator x processor matrix (SVG + PNG from one geometry)
# --------------------------------------------------------------------------
lato_dir = os.environ.get("LATO_DIR")
if not lato_dir:
    hits = glob.glob("/nix/store/*-lato-*/share/fonts/lato")
    lato_dir = hits[0] if hits else None
if not lato_dir:
    sys.exit("Lato fonts not found: set LATO_DIR")
F_REG = os.path.join(lato_dir, "Lato-Regular.ttf")
F_BOLD = os.path.join(lato_dir, "Lato-Bold.ttf")

ROW_H = 26
CELL_W = 30
LABEL_W = 250
BAND_W = 26
TOP = 128  # rotated column labels
FAM_H = 26  # family strip below the matrix
LEGEND_H = 40
MARGIN = 8

rows = []  # (dim_id, indicator)
for d in DIMS:
    for f in d["factors"]:
        for ind in f.get("indicators", []):
            rows.append((d["id"], ind))

W = MARGIN + BAND_W + LABEL_W + len(PROCESSORS) * CELL_W + MARGIN
H = TOP + len(rows) * ROW_H + FAM_H + LEGEND_H + MARGIN


def col_x(c):
    return MARGIN + BAND_W + LABEL_W + c * CELL_W


def row_y(r):
    return TOP + r * ROW_H


svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" ' f'viewBox="0 0 {W} {H}" font-family="Lato">',
    f'<rect width="{W}" height="{H}" fill="{WHITE}"/>',
]
png = Image.new("RGB", (W * 3, H * 3), WHITE)
pd = ImageDraw.Draw(png)


def font(size, bold=False):
    return ImageFont.truetype(F_BOLD if bold else F_REG, int(size * 3))


def text(x, y, s, size=12, colour=CHARCOAL, bold=False, anchor="start", rotate=None):
    """anchor: start|middle|end (SVG semantics, y = baseline)."""
    weight = ' font-weight="bold"' if bold else ""
    rot = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
    esc = s.replace("&", "&amp;").replace("<", "&lt;")
    svg.append(
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{colour}"' f' text-anchor="{anchor}"{weight}{rot}>{esc}</text>'
    )
    f = font(size, bold)
    wpx = pd.textlength(s, font=f)
    asc, desc = f.getmetrics()
    if rotate:  # render on a transparent tile, rotate, paste
        tile = Image.new("RGBA", (int(wpx) + 12, asc + desc + 12), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        td.text((6, 6), s, font=f, fill=colour)
        tile = tile.rotate(-rotate, expand=True, resample=Image.BICUBIC)
        # anchor point of the baseline start, in PNG space
        ax, ay = x * 3, y * 3
        import math

        rad = math.radians(rotate)
        # position of the (6,6+asc) baseline-start point after rotation
        cx, cy = tile.width / 2, tile.height / 2
        ox, oy = 6 - (int(wpx) + 12) / 2, 6 + asc - (asc + desc + 12) / 2
        rx = ox * math.cos(rad) - oy * math.sin(rad)
        ry = ox * math.sin(rad) + oy * math.cos(rad)
        png.paste(tile, (int(ax - (cx + rx)), int(ay - (cy + ry))), tile)
    else:
        tx = {"start": x * 3, "middle": x * 3 - wpx / 2, "end": x * 3 - wpx}[anchor]
        pd.text((tx, y * 3 - asc), s, font=f, fill=colour)


def rect(x, y, w, h, fill, rx=0):
    extra = f' rx="{rx}"' if rx else ""
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{extra}/>')
    if rx:
        pd.rounded_rectangle([x * 3, y * 3, (x + w) * 3, (y + h) * 3], rx * 3, fill=fill)
    else:
        pd.rectangle([x * 3, y * 3, (x + w) * 3, (y + h) * 3], fill=fill)


def line(x1, y1, x2, y2, colour, width=1):
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="{width}"/>')
    pd.line([x1 * 3, y1 * 3, x2 * 3, y2 * 3], fill=colour, width=width * 3)


def dot(cx, cy, r, fill):
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')
    pd.ellipse([(cx - r) * 3, (cy - r) * 3, (cx + r) * 3, (cy + r) * 3], fill=fill)


# zebra rows
for r in range(len(rows)):
    if r % 2 == 1:
        rect(MARGIN + BAND_W, row_y(r), LABEL_W + len(PROCESSORS) * CELL_W, ROW_H, PAPER)

# dimension bands + separators
r0 = 0
for d in DIMS:
    count = sum(len(f.get("indicators", [])) for f in d["factors"])
    y0, y1 = row_y(r0), row_y(r0 + count)
    rect(MARGIN, y0, BAND_W - 8, y1 - y0, DIM_BAND[d["id"]], rx=4)
    text(
        MARGIN + (BAND_W - 8) / 2 + 4,
        (y0 + y1) / 2,
        d["name"].upper(),
        size=10.5,
        colour=WHITE,
        bold=True,
        anchor="middle",
        rotate=-90,
    )
    if r0:
        line(MARGIN, y0, W - MARGIN, y0, LIGHT_GREY, 1)
    r0 += count

# column labels (rotated 45deg) + family separators
for c, (flag, label, _cls, _sec) in enumerate(PROCESSORS):
    x = col_x(c) + CELL_W / 2
    text(x, TOP - 8, label, size=11.5, colour=CHARCOAL, rotate=-45)
for fam, (label, start, count) in enumerate(FAMILIES):
    if start:
        line(col_x(start), TOP - 4, col_x(start), row_y(len(rows)), LIGHT_GREY, 1)

# row labels + dots
for r, (dim_id, ind) in enumerate(rows):
    cy = row_y(r) + ROW_H / 2
    text(MARGIN + BAND_W + LABEL_W - 12, cy + 4, short_name(ind), size=12, anchor="end")
    flags = set(enabled_flags(ind))
    for c, (flag, *_r2) in enumerate(PROCESSORS):
        if flag in flags:
            dot(col_x(c) + CELL_W / 2, cy, 7, BLUE)

# frame around the dot area
bot = row_y(len(rows))
line(MARGIN + BAND_W, TOP, W - MARGIN, TOP, CHARCOAL, 1)
line(MARGIN + BAND_W, bot, W - MARGIN, bot, CHARCOAL, 1)

# family strip below
for fam, (label, start, count) in enumerate(FAMILIES):
    x0, x1 = col_x(start), col_x(start + count)
    rect(x0 + 1, bot + 6, x1 - x0 - 2, FAM_H - 8, BLUE_TINT if fam % 2 == 0 else AMBER_TINT, rx=4)
    text((x0 + x1) / 2, bot + 6 + (FAM_H - 8) / 2 + 4, label, size=10.5, colour=GREY, bold=True, anchor="middle")

# legend
ly = bot + FAM_H + 22
dot(MARGIN + BAND_W + 8, ly - 4, 7, BLUE)
text(
    MARGIN + BAND_W + 22,
    ly,
    "processor available for this indicator (model.json use_* flag) — families group the chapter 6 sections",
    size=11.5,
    colour=GREY,
)

svg.append("</svg>")
(DIA / "fig23-indicator-processor-matrix.svg").write_text("\n".join(svg) + "\n")
png.save(DIA / "fig23-indicator-processor-matrix.png")

# --------------------------------------------------------------------------
# 3. Markdown chapter
# --------------------------------------------------------------------------
md = []
add = md.append

n_factors = sum(len(d["factors"]) for d in DIMS)
n_inds = len(rows)

add("# 8. Shipped model catalogue")
add("")
add(
    "This chapter is generated from `geest/resources/model.json` at build time and"
    " enumerates every node of the shipped analysis model: each dimension and each"
    " factor has its own page, every indicator is described with its defaults, and a"
    " matrix maps each indicator to the processors (chapter 6) that can run it. The"
    f" shipped model contains **{len(DIMS)} dimensions**, **{n_factors} factors** and"
    f" **{n_inds} indicators**. All indicators ship in the `Do Not Use` state — the"
    " analyst activates exactly one processor per indicator in the data-source dialog"
    " (except the EPLEX indicator, which is pre-set to `use_eplex_score`)."
)
add("")
add(
    "![Figure 17 — The shipped analysis model — three weighted dimensions decompose"
    " into sixteen factors; the indicator counts show where the model is broad"
    " (women's travel patterns, environmental hazards) versus"
    " single-indicator.](diagrams/fig19-model-overview.png)"
)
add("")
add("| Dimension | Default weight | Factors | Indicators |")
add("|-----------|----------------|---------|------------|")
for d in DIMS:
    add(
        f"| {d['name']} | {fmt_weight(d.get('default_analysis_weighting'))} |"
        f" {len(d['factors'])} | {sum(len(f.get('indicators', [])) for f in d['factors'])} |"
    )
add("")
add("<!-- pagebreak -->")
add("")
add("## 8.1 Indicator × processor matrix")
add("")
add(
    "Each indicator declares, through its `use_*` flags, which of the seventeen"
    " processor types can compute it. The matrix below is the complete capability"
    " map: rows are the shipped indicators grouped by dimension, columns are the"
    " processors grouped into the families of chapter 6. Where several processors"
    " are available for one indicator (for example street lights, which can be"
    " computed from point buffers, classified polygons, a raster, or a fixed index"
    " score), the choice is made per indicator in the data-source dialog and depends"
    " on which input data exist for the study area."
)
add("")
add(
    "![Figure 18 — Indicator × processor capability matrix — every dot is a valid"
    " indicator/processor pairing declared in model.json; the families along the"
    " bottom mirror the processor reference sections"
    " (§6.1–§6.6).](diagrams/fig23-indicator-processor-matrix.png)"
)
add("")
add("The same matrix as a reference table, using the processor section numbers:")
add("")
add("| Indicator | Available processors (§) |")
add("|-----------|--------------------------|")
for dim_id, ind in rows:
    secs = " · ".join(f"{label} (§{sec})" for (flag, label, _c, sec) in PROCESSORS if ind.get(flag))
    add(f"| {short_name(ind)} | {secs} |")
add("")

section = 1
fig = 19
for d in DIMS:
    section += 1
    add("<!-- pagebreak -->")
    add("")
    add(f"## 8.{section} The {d['name']} dimension")
    add("")
    add(d["description"])
    add("")
    add("| Property | Value |")
    add("|---|---|")
    add(f"| Dimension ID | `{d['id']}` |")
    add(f"| Default analysis weight | {fmt_weight(d.get('default_analysis_weighting'))} |")
    add(f"| Factors | {len(d['factors'])} |")
    add(f"| Indicators | {sum(len(f.get('indicators', [])) for f in d['factors'])} |")
    add(f"| Output raster | `{d.get('output_filename', '—')}.tif` |")
    add("")
    add(
        f"![Figure {fig} — The {d['name']} dimension — factors with their default"
        f" weights and their indicators, as shipped in"
        f" model.json.](diagrams/{DIM_FIG_FILE[d['id']]})"
    )
    fig += 1
    add("")
    for fn, f in enumerate(d["factors"], start=1):
        add("<!-- pagebreak -->")
        add("")
        add(f"### 8.{section}.{fn} {f['name']}")
        add("")
        add(f.get("description", ""))
        add("")
        add("| Property | Value |")
        add("|---|---|")
        add(f"| Factor ID | `{f['id']}` |")
        add(f"| Default weight in {d['name']} | {fmt_weight(f.get('default_dimension_weighting'))} |")
        add(f"| Indicators | {len(f.get('indicators', []))} |")
        add(f"| Output raster | `{f.get('output_filename', '—')}.tif` |")
        add("")
        for ind in f.get("indicators", []):
            add(f"**{ind['indicator']}** (`{ind['id']}`)")
            add("")
            if ind.get("description"):
                add(ind["description"])
                add("")
            details = [("Default factor weighting", fmt_weight(ind.get("default_factor_weighting")))]
            if ind.get("osm_download_enabled"):
                details.append(("OSM auto-download", "Yes — one-click Overpass acquisition"))
            sbd = ind.get("default_single_buffer_distance") or 0
            if sbd:
                details.append(("Default single-buffer distance", f"{sbd} m"))
            mbd = (ind.get("default_multi_buffer_distances") or "").replace(" ", "")
            if mbd and mbd != "0,0,0":
                details.append(("Default multi-buffer bands", f"{ind['default_multi_buffer_distances']} m"))
            if ind.get("analysis_mode") not in (None, "", "Do Not Use"):
                details.append(("Pre-configured mode", f"`{ind['analysis_mode']}`"))
            procs = " · ".join(f"{label} (§{sec})" for (flag, label, _c, sec) in PROCESSORS if ind.get(flag))
            details.append(("Available processors", procs))
            add("| Property | Value |")
            add("|---|---|")
            for k, v in details:
                add(f"| {k} | {v} |")
            add("")

(GEN / "model-catalogue.md").write_text("\n".join(md) + "\n")
print(
    f"catalogue: {len(DIMS)} dimensions, {n_factors} factors, {n_inds} indicators; "
    f"matrix {len(rows)}×{len(PROCESSORS)}; wrote model-catalogue.md + 4 puml + svg/png"
)
