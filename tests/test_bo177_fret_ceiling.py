"""
tests/test_bo177_fret_ceiling.py

Regression tests for BO-177: user-configurable maximum playable
fret ("fret ceiling"), replacing find_positions()'s and chord_
generator.py's own previously-hardcoded 22.

Real fixtures/mechanism used: fretboard.set_max_fret()/
get_max_fret() (the shared module-level value both find_
positions() and chord_generator.py's own melody-tone widening
now read), and main.py's own load_settings()/save_settings()
(BO-160's pre-existing persisted-settings mechanism, reused here
for "fret_ceiling" rather than building a second one).
"""

import sys

sys.path.insert(0, '.')

import pytest

from fretboard import (
    set_max_fret,
    get_max_fret,
    find_positions,
    DEFAULT_MAX_FRET,
    MIN_ALLOWED_MAX_FRET,
    MAX_ALLOWED_MAX_FRET
)

import main


@pytest.fixture(autouse=True)
def _restore_max_fret():

    # Every test in this file changes the shared module value --
    # restore it afterward so tests in other files (which never
    # expect this module-level state) always see the same
    # default a fresh interpreter would.
    original = get_max_fret()

    yield

    set_max_fret(original)


# ---------------------------------------------------------
# 1 -- default is 15, not the old hardcoded 22
# ---------------------------------------------------------

def test_default_max_fret_is_15():

    assert DEFAULT_MAX_FRET == 15


# ---------------------------------------------------------
# 2 -- valid range is enforced
# ---------------------------------------------------------

def test_set_max_fret_rejects_below_minimum():

    with pytest.raises(ValueError):

        set_max_fret(MIN_ALLOWED_MAX_FRET - 1)


def test_set_max_fret_rejects_above_maximum():

    with pytest.raises(ValueError):

        set_max_fret(MAX_ALLOWED_MAX_FRET + 1)


def test_set_max_fret_accepts_full_valid_range():

    for value in (MIN_ALLOWED_MAX_FRET, 15, MAX_ALLOWED_MAX_FRET):

        set_max_fret(value)

        assert get_max_fret() == value


# ---------------------------------------------------------
# 3 -- find_positions() genuinely respects the configured
# ceiling, not just get_max_fret() reporting the right number
# ---------------------------------------------------------

def test_find_positions_excludes_frets_beyond_ceiling():

    set_max_fret(15)

    open_notes = [43, 50, 55, 59]  # gDGBD-style open notes

    # A pitch reachable only via fret 17 on every string in this
    # tuning (43+17=60, etc. -- chosen so no string reaches it
    # within 15 frets).
    positions = find_positions(60, open_notes)

    assert all(p["fret"] <= 15 for p in positions)

    assert not any(p["fret"] == 17 for p in positions)


def test_find_positions_includes_the_same_fret_when_ceiling_raised():

    open_notes = [43, 50, 55, 59]

    set_max_fret(15)

    positions_low = find_positions(60, open_notes)

    set_max_fret(22)

    positions_high = find_positions(60, open_notes)

    assert len(positions_high) > len(positions_low)


# ---------------------------------------------------------
# 4 -- settings round-trip: save_settings()/load_settings()
# genuinely persists fret_ceiling (BO-160's own mechanism,
# confirmed to carry this new key correctly)
# ---------------------------------------------------------

def test_fret_ceiling_settings_round_trip(tmp_path):

    main.save_settings({"fret_ceiling": 17}, tmp_path)

    loaded = main.load_settings(tmp_path)

    assert loaded["fret_ceiling"] == 17


def test_missing_settings_file_has_no_fret_ceiling_key(tmp_path):

    # No settings file has ever been saved in this fresh tmp_path
    # -- load_settings() must return {} (BO-160's own established
    # "never configured" contract), so run_optimizer()'s own
    # `"fret_ceiling" in _settings` check correctly falls back to
    # DEFAULT_MAX_FRET rather than defaulting to 0 or raising.
    loaded = main.load_settings(tmp_path)

    assert "fret_ceiling" not in loaded
