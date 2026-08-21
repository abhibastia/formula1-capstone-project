"""Architecture Decision Records must exist, and stay honest.

ADRs are the documentation most likely to rot, because nothing breaks when they
do. These checks are deliberately structural — they cannot judge whether a
decision is right, only that each record still states what a reader needs:
context, the decision, what it cost, and what else was considered.

The "alternatives considered" section is the one worth enforcing. A decision
record without it is a justification, and a justification written after the fact
is worth very little.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADR_DIR = ROOT / "docs" / "adr"
ADRS = sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")
INDEX = ADR_DIR / "README.md"

REQUIRED_SECTIONS = ("## Context", "## Decision", "## Consequences",
                     "## Alternatives considered")


def test_adr_directory_exists_and_is_populated():
    """The capstone criteria require ADRs in docs/adr/."""
    assert ADR_DIR.is_dir(), "docs/adr/ is required by the project criteria"
    assert len(ADRS) >= 5, f"only {len(ADRS)} ADRs — the decisions here are worth recording"


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_adr_has_the_required_sections(path):
    text = path.read_text()
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{path.name} is missing '{section}'"


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_adr_has_a_title(path):
    """Date and Status lines were dropped deliberately — git history is the
    date, and every ADR here is a decision that shipped, so a status field
    with one value in ten records was not carrying its weight."""
    text = path.read_text()
    assert re.match(r"^# \d+\. \S", text), f"{path.name} must open with '# N. Title'"


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_adr_body_starts_right_after_the_title(path):
    """No stray blank-heavy header block should survive the Date/Status removal."""
    lines = path.read_text().split("\n")
    assert lines[1] == "", f"{path.name}: line after the title must be blank"
    assert lines[2] == "## Context", (
        f"{path.name}: expected '## Context' immediately after the title, "
        f"got {lines[2]!r} — a leftover Date/Status fragment?"
    )


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_adr_number_matches_its_filename(path):
    number = int(path.name.split("-")[0])
    heading = int(re.match(r"^# (\d+)\.", path.read_text()).group(1))
    assert number == heading, f"{path.name} is numbered {heading} in its heading"


def test_adr_numbers_are_unique_and_contiguous():
    numbers = sorted(int(p.name.split("-")[0]) for p in ADRS)
    assert numbers == list(range(1, len(numbers) + 1)), \
        f"ADR numbers should run 1..N with no gaps or duplicates, got {numbers}"


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_every_adr_is_listed_in_the_index(path):
    assert path.name in INDEX.read_text(), \
        f"{path.name} is not linked from docs/adr/README.md"


@pytest.mark.parametrize("path", ADRS, ids=lambda p: p.stem)
def test_consequences_are_not_all_positive(path):
    """A record with only upsides has not been thought about.

    Every decision here cost something — a rejected capability, a wider
    dependency graph, a local development gap. If a future ADR lists only
    benefits, that is the signal to look harder, not a sign of a good decision.
    """
    consequences = path.read_text().split("## Consequences", 1)[1]
    consequences = consequences.split("## Alternatives considered", 1)[0]
    assert "**Bad" in consequences or "**Neutral" in consequences, (
        f"{path.name} lists no downside — every decision in this project cost "
        f"something, and a record that says otherwise is marketing"
    )
