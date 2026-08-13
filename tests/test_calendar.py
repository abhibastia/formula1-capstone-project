"""The race calendar drives everything downstream.

It decides which rounds exist, whether each is closed, and — once weather is
added — supplies the coordinates the archive is queried at. A malformed entry
must be skipped, not fatal: one bad race should not abort a season's harvest.
"""
import datetime as dt

import ingest


def payload(races):
    return {"MRData": {"RaceTable": {"Races": races}}}


class TestParseRaceCalendar:
    def test_maps_round_to_date(self):
        cal = ingest.parse_race_calendar(payload([
            {"round": "1", "date": "2024-03-02"},
            {"round": "2", "date": "2024-03-09"},
        ]))
        assert cal == {1: dt.date(2024, 3, 2), 2: dt.date(2024, 3, 9)}

    def test_skips_a_malformed_entry_without_losing_the_rest(self):
        cal = ingest.parse_race_calendar(payload([
            {"round": "1", "date": "2024-03-02"},
            {"round": "2", "date": "not-a-date"},
            {"round": "3"},
            {"round": "4", "date": "2024-03-23"},
        ]))
        assert set(cal) == {1, 4}, "one bad race must not abort the season"

    def test_an_empty_season_is_empty_not_an_error(self):
        assert ingest.parse_race_calendar(payload([])) == {}
