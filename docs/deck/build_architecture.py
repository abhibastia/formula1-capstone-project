"""Render the architecture diagram once, for the README and the deck.

    python3 docs/deck/build_architecture.py

Writes docs/assets/architecture.png at 2400x1350 (16:9), which is sharp on a
projector and readable inline on GitHub.

WHY GENERATED RATHER THAN DRAWN
-------------------------------
The same reason the deck is code. A diagram made in a drawing tool drifts the
moment the platform changes, and nobody notices because nothing fails. This one
is rebuilt from a description of the pipeline that sits next to the pipeline —
when a mart is added, the diagram is a one-line edit and a rerun, and
`tests/test_architecture_diagram.py` fails if the counts stop matching the
repository.

The palette is Formula 1's: #15151E behind everything, #E10600 for the sources
and the flow, team liveries for the layers.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2400, 1160

BG = (0x15, 0x15, 0x1E)
CARD = (0x1F, 0x1F, 0x2B)
CARD2 = (0x27, 0x27, 0x3A)
LINE = (0x3A, 0x3A, 0x50)
TEXT = (0xFF, 0xFF, 0xFF)
MUTED = (0x9A, 0x9A, 0xB0)
RED = (0xE1, 0x06, 0x00)
TEAL = (0x00, 0xD2, 0xBE)
AMBER = (0xFF, 0x87, 0x00)
BLUE = (0x00, 0x90, 0xFF)

FONTS = "/System/Library/Fonts/Supplemental"


def font(size, bold=False):
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    try:
        return ImageFont.truetype(f"{FONTS}/{name}", size)
    except OSError:  # not macOS — fall back to whatever Pillow ships
        return ImageFont.load_default(size)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def box(x, y, w, h, fill=CARD, outline=LINE, radius=14, accent=None):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=outline, width=2)
    if accent:
        d.rounded_rectangle([x, y, x + 7, y + h], radius=3, fill=accent)


def text(x, y, s, size=26, color=TEXT, bold=False, anchor="la"):
    d.text((x, y), s, font=font(size, bold), fill=color, anchor=anchor)


def arrow(x1, y, x2, color=LINE, head=12):
    d.line([x1, y, x2 - head, y], fill=color, width=3)
    d.polygon([(x2, y), (x2 - head, y - 7), (x2 - head, y + 7)], fill=color)


def wrap(s, size, width, bold=False):
    """Greedy wrap against the real glyph widths, not a character estimate."""
    f = font(size, bold)
    words, lines, line = s.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if f.getlength(trial) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def arrow_down(x, y1, y2, color=LINE, head=12):
    d.line([x, y1, x, y2 - head], fill=color, width=3)
    d.polygon([(x, y2), (x - 7, y2 - head), (x + 7, y2 - head)], fill=color)


# ───────────────────────────── title ─────────────────────────────
d.rectangle([0, 0, 10, H], fill=RED)
text(70, 62, "F1 RACE INTELLIGENCE & STRATEGY PLATFORM", 30, RED, bold=True)
text(70, 108, "Batch lakehouse on Databricks Free Edition — public APIs to governed marts", 30, MUTED)

# ─────────────────────────── the flow ────────────────────────────
COL_W, GAP, TOP, BOX_H = 420, 45, 200, 300
xs = [70 + i * (COL_W + GAP) for i in range(5)]

stages = [
    ("SOURCES", RED, [
        ("Jolpica-F1", "results · qualifying · standings"),
        ("", "sprint · pit stops · laps"),
        ("Open-Meteo ERA5", "measured race-day weather"),
        ("", "public · keyless · rate-limited"),
    ]),
    ("INGESTION", RED, [
        ("Databricks Job", "serverless Python, no Lambda"),
        ("", "throttled 0.5 req/s, retried"),
        ("", "idempotent — closed rounds skipped"),
        ("UC Volume", "f1.raw.landing · raw JSON"),
    ]),
    ("BRONZE", BLUE, [
        ("11 streaming tables", "one per endpoint"),
        ("Auto Loader", "incremental file discovery"),
        ("read as text", "no schema inference, no drops"),
        ("", "provenance on every row"),
    ]),
    ("SILVER", BLUE, [
        ("8 facts", "MVs, deduped on natural key"),
        ("3 dimensions", "2 × SCD Type 2, Auto CDC"),
        ("9 quarantine views", "rejected rows + the rule"),
        ("", "explicit schemas, expectations"),
    ]),
    ("GOLD", TEAL, [
        ("6 marts", "dims joined as-of race date"),
        ("driver_metrics", "governed metric view"),
        ("pipeline_event_log", "data quality, queryable"),
        ("", "clustered by season, round"),
    ]),
]

for i, (title, accent, rows) in enumerate(stages):
    x = xs[i]
    box(x, TOP, COL_W, BOX_H, accent=accent)
    text(x + 28, TOP + 24, title, 27, accent, bold=True)
    y = TOP + 74
    for head, sub in rows:
        if head:
            text(x + 28, y, head, 25, TEXT, bold=True)
            y += 30
        if sub:
            text(x + 28, y, sub, 21, MUTED)
            y += 30
    if i < 4:
        arrow(x + COL_W + 6, TOP + BOX_H // 2, x + COL_W + GAP - 6, RED if i < 2 else LINE)

# ───────────────────────── side outputs ──────────────────────────
SIDE_Y = TOP + BOX_H + 55
box(xs[3], SIDE_Y, COL_W, 74, fill=CARD2, accent=AMBER)
text(xs[3] + 28, SIDE_Y + 22, "rejected rows are routed, never dropped", 22, AMBER)
arrow_down(xs[3] + COL_W // 2, TOP + BOX_H + 6, SIDE_Y - 6, AMBER)

box(xs[4], SIDE_Y, COL_W, 74, fill=CARD2, accent=AMBER)
text(xs[4] + 28, SIDE_Y + 22, "expectations per dataset, per run", 22, AMBER)
arrow_down(xs[4] + COL_W // 2, TOP + BOX_H + 6, SIDE_Y - 6, AMBER)

# ─────────────────────────── serving ─────────────────────────────
SERVE_Y = SIDE_Y + 135
box(70, SERVE_Y, W - 140, 200, accent=TEAL)
text(98, SERVE_Y + 22, "SERVING", 26, TEAL, bold=True)
arrow_down(xs[4] + COL_W // 2, SIDE_Y + 76, SERVE_Y - 6, TEAL)

serve = [
    ("AI/BI Dashboard — 6 pages, one per decision",
     "Standings · Driver Form · Constructor Benchmarking · Circuit Priors · Championship Swing · Trust"),
    ("Genie agent — natural language over Gold",
     "7 tables, 7 certified queries, governed by the same grants as the dashboard"),
    ("Metric view — one definition of a point",
     "13 measures via MEASURE(), read by the dashboard and Genie alike"),
]
SUB_W, SUB_GAP = 714, 30
for i, (head, sub) in enumerate(serve):
    sx = 98 + i * (SUB_W + SUB_GAP)
    box(sx, SERVE_Y + 66, SUB_W, 112, fill=CARD2, outline=LINE, radius=10)
    text(sx + 22, SERVE_Y + 84, head, 22, TEXT, bold=True)
    for j, ln in enumerate(wrap(sub, 19, SUB_W - 44)):
        text(sx + 22, SERVE_Y + 118 + j * 26, ln, 19, MUTED)

# ──────────────────── governance and orchestration ───────────────
GOV_Y = SERVE_Y + 235
box(70, GOV_Y, (W - 180) // 2, 130, fill=CARD2, accent=TEAL)
text(98, GOV_Y + 22, "UNITY CATALOG", 24, TEAL, bold=True)
text(98, GOV_Y + 58, "Lineage from the pipeline graph · layered grants: Gold to consumers,", 20, MUTED)
text(98, GOV_Y + 88, "raw to nobody · audit · row-level provenance on every Bronze row", 20, MUTED)

ox = 70 + (W - 180) // 2 + 40
box(ox, GOV_Y, (W - 180) // 2, 130, fill=CARD2, accent=RED)
text(ox + 28, GOV_Y + 22, "ORCHESTRATION — LAKEFLOW JOBS", 24, RED, bold=True)
text(ox + 28, GOV_Y + 58, "f1_end_to_end — unit tests → ingest → pipeline → validate", 20, MUTED)
text(ox + 28, GOV_Y + 88, "f1_ingest_incremental — weekly, same chain without the tests", 20, MUTED)

# ──────────────────────────── footer ─────────────────────────────
text(70, H - 52, "Batch, single path — not Lambda, not Kappa. F1 produces data 24 times a year, in bursts, hours after each race.",
     21, MUTED)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "assets" / "architecture.png"))
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(f"wrote {out}  ({W}x{H})")


main()
