"""Shared configuration for F1 ingestion.

Every name that appears in more than one place lives here. The catalog is the one
value that may change (Free Edition may force a fallback catalog), so nothing
downstream hard-codes it.
"""

CATALOG = "f1"
RAW_SCHEMA = "raw"
VOLUME = "landing"

VOLUME_ROOT = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/{VOLUME}"

BASE_URL = "https://api.jolpi.ca/ergast/f1"

# Backfill seasons are complete and immutable; the live season is re-polled.
BACKFILL_SEASONS = [2024, 2025]
LIVE_SEASON = 2026

# Jolpica publishes two limits and they bind at different scales:
#   * 4 requests/second burst  — REQUESTS_PER_SECOND handles this
#   * 500 requests/hour sustained — REQUESTS_PER_HOUR handles this
#
# Only the burst limit used to be enforced, which was fine while the endpoint
# set totalled ~200 calls per backfill. It stops being fine with `laps`: at 12
# pages per round, three seasons is ~850 requests, and 2 req/s would fire 7,200
# in an hour. The sustained limit is the real ceiling for any large backfill.
#
# 450 rather than 500 leaves headroom for the retries a long run will make.
#
# 2.0 req/s was set from Jolpica's published 4/s burst limit. Measured against
# the real API during a laps backfill it produced a 429 on roughly 37% of
# requests — the enforced burst rate is well under the documented one for
# unauthenticated clients. Worse, every retry spends the hourly budget, so a
# rate that trips throttling burns the allowance twice: once on the rejected
# request and again on the retry.
#
# 0.5 req/s spaces a race's 11 lap pages over ~22 seconds, which the API
# accepts without complaint. Slower per request, faster overall.
REQUESTS_PER_SECOND = 0.5
REQUESTS_PER_HOUR = 450
PAGE_SIZE = 100
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30

# Season-level endpoints: one call per season, no round segment.
# `sprint` is season-level on purpose: the per-round form would need a call for
# every round to find the ~6 that have a sprint, while the season form returns
# them all in two pages. Sprint points count toward the championship, so without
# this endpoint the marts understate points on every sprint weekend.
SEASON_ENDPOINTS = {
    "races": "{season}/races",
    "drivers": "{season}/drivers",
    "constructors": "{season}/constructors",
    "sprint": "{season}/sprint",
}

# Round-level endpoints: one call per (season, round).
ROUND_ENDPOINTS = {
    "results": "{season}/{round}/results",
    "qualifying": "{season}/{round}/qualifying",
    "driver_standings": "{season}/{round}/driverStandings",
    "constructor_standings": "{season}/{round}/constructorStandings",
}

ALL_ENDPOINTS = {**SEASON_ENDPOINTS, **ROUND_ENDPOINTS}

# The MRData sub-table each endpoint's records live under, and the array key
# holding the records. Used by the Silver layer; kept here so the contract is
# declared in exactly one place.
ENDPOINT_SHAPE = {
    "races": ("RaceTable", "Races"),
    "drivers": ("DriverTable", "Drivers"),
    "constructors": ("ConstructorTable", "Constructors"),
    "sprint": ("RaceTable", "Races"),
    "results": ("RaceTable", "Races"),
    "qualifying": ("RaceTable", "Races"),
    "driver_standings": ("StandingsTable", "StandingsLists"),
    "constructor_standings": ("StandingsTable", "StandingsLists"),
}