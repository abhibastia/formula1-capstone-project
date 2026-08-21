"""The architecture diagram must exist, and its counts must match the repository.

A diagram is the artefact most likely to go stale, because nothing breaks when it
does — it is read by people least able to check it, and it looks equally
confident whether or not it is true. These assertions are the cheap half of
keeping it honest: the numbers on the picture are compared against what the
repository actually contains.

They cannot check the layout. `docs/deck/build_architecture.py` renders it, so
regenerating and looking at it is still part of changing it.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL", reason="Pillow not installed; diagram tests skipped")

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "docs" / "deck" / "build_architecture.py"
DIAGRAM = ROOT / "docs" / "assets" / "architecture.png"
SOURCE = BUILDER.read_text()


def test_the_diagram_is_committed():
    """README embeds it, so a missing file is a broken README on GitHub."""
    assert DIAGRAM.exists(), "docs/assets/architecture.png is missing"
    assert "architecture.png" in (ROOT / "README.md").read_text()


def test_it_still_builds():
    result = subprocess.run([sys.executable, str(BUILDER), "--out", "/tmp/arch-test.png"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr[-1500:]


@pytest.mark.parametrize("label,pattern,counter", [
    ("Bronze streaming tables", r"(\d+) streaming tables",
     lambda: len(re.findall(r'^\s+"(\w+)":\s+"http',
                            (ROOT / "src" / "pipeline" / "01_bronze.py").read_text(), re.M))),
    ("Silver facts", r"(\d+) facts",
     lambda: len(set(re.findall(r'name=f"\{SILVER\}\.(fact_\w+)"', _pipeline())))),
    ("Silver dimensions", r"(\d+) dimensions",
     lambda: len(set(re.findall(r'\{SILVER\}\.(dim_\w+)"', _pipeline())))),
    ("quarantine views", r"(\d+) quarantine views",
     lambda: len(set(re.findall(r'name=f"\{SILVER\}\.(quarantine_\w+)"', _pipeline())))),
    ("Gold marts", r"(\d+) marts",
     lambda: len(set(re.findall(r'name=f"\{GOLD\}\.(\w+)"', _pipeline())))),
])
def test_diagram_counts_match_the_repository(label, pattern, counter):
    claimed = re.search(pattern, SOURCE)
    assert claimed, f"the diagram no longer states a count for {label}"
    assert int(claimed.group(1)) == counter(), (
        f"diagram says {claimed.group(1)} {label}, repository has {counter()}"
    )


def _pipeline():
    return "\n".join(p.read_text() for p in (ROOT / "src" / "pipeline").glob("*.py"))


def test_dashboard_page_count_matches():
    import json
    pages = len(json.loads((ROOT / "dashboards" / "f1_race_intelligence.lvdash.json").read_text())["pages"])
    claimed = re.search(r"(\d+) pages, one per decision", SOURCE)
    assert claimed and int(claimed.group(1)) == pages, (
        f"diagram claims {claimed.group(1) if claimed else '?'} dashboard pages, there are {pages}"
    )
