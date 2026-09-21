"""
tests/test_bo185_capo_aware_max_fret.py

Regression tests for BO-185: the user's own configured "Maximum
playable fret" is a PHYSICAL fretboard limit. A capo shortens
the physically usable neck by its own fret count -- a 15-fret
ceiling with a capo at fret 2 means the highest WRITTEN fret
(relative to the capo, which every tuning.notes value in this
project already is) must not exceed 13, not 15 (fret 13 relative
to the capo is the real, physical 15th fret). Before this,
neither find_positions() nor chord_generator.py's own chord-
shape search had any capo awareness at all.

Two real gaps found and fixed here:
1. fretboard.find_positions() itself (and chord_generator.py's
   own melody-tone widening, which already called get_max_fret()
   directly).
2. A SEPARATE, pre-existing gap in chord_generator.py's own main
   chord-shape search: a hardcoded FRET_CEILING=7 "loose
   computational bound", entirely independent of the user's own
   configured ceiling. Confirmed real via a direct production
   run: with a 6-fret ceiling and a capo of 2 (effective 4), a
   chord shape reaching fret 5 was still generated and written
   into actual output via that note's own melody-position anchor
   to the chord's shape -- 1 fret beyond the real physical limit.
   This surfaces whenever the effective ceiling drops below 7,
   which a low ceiling plus a real capo makes far more likely
   than a bare low ceiling alone.
"""

import sys

sys.path.insert(0, '.')

from fretboard import (
    set_max_fret, set_capo, get_max_fret, get_effective_max_fret,
    find_positions, parse_shape
)

import chord_generator


def test_effective_max_fret_subtracts_capo():

    set_max_fret(15)

    set_capo(2)

    try:

        assert get_effective_max_fret() == 13

    finally:

        set_capo(0)


def test_get_max_fret_stays_raw_not_capo_adjusted():

    # get_max_fret() must stay the exact inverse of set_max_fret()
    # -- score_generator.py's own BO-179 fallback logic reads it,
    # temporarily overrides it, then restores it via set_max_fret
    # (get_max_fret()); a capo-adjusted return here would have
    # that restore silently shift the real ceiling down by the
    # capo amount every time the fallback runs.
    set_max_fret(15)

    set_capo(2)

    try:

        assert get_max_fret() == 15

    finally:

        set_capo(0)


def test_effective_max_fret_clamped_at_zero():

    set_max_fret(5)

    set_capo(5)

    try:

        assert get_effective_max_fret() == 0

    finally:

        set_capo(0)


def test_find_positions_respects_capo():

    set_max_fret(15)

    set_capo(2)

    try:

        open_notes = [50]

        # fret 13 relative to capo 2 -- the real physical 15th
        # fret -- must still be reachable.
        assert find_positions(63, open_notes) != []

        # fret 14 relative to capo 2 -- the real physical 16th
        # fret -- must now be rejected.
        assert find_positions(64, open_notes) == []

    finally:

        set_capo(0)


def test_chord_generator_search_ceiling_respects_low_effective_max(
):

    # The real gap found during this BO's own investigation:
    # chord_generator.py's main shape search used a hardcoded
    # FRET_CEILING=7 regardless of the user's own configured
    # ceiling or capo. With an effective ceiling below 7, the
    # search must now be bounded by the LOWER of the two.
    set_max_fret(6)

    set_capo(2)

    try:

        assert get_effective_max_fret() == 4

        tuning_notes = [67, 52, 57, 62, 64]  # A Modal Sawmill

        candidates = chord_generator.generate_candidates(
            type(
                "T", (), {"notes": tuning_notes}
            )(),
            "E", 4, "m", "Minor"
        )

        for shape in candidates:

            frets = [
                f for f in parse_shape(shape.shape)
                if f is not None
            ]

            assert all(f <= 4 for f in frets), (
                f"shape {shape.shape!r} exceeds effective "
                f"ceiling 4"
            )

    finally:

        set_capo(0)


def test_chord_generator_search_ceiling_unaffected_when_generous(
):

    # When the effective ceiling is above FRET_CEILING (7) --
    # the common case for most real users -- the search range is
    # exactly the same 0..7 it always was; this change never
    # WIDENS the search, only narrows it when the effective
    # ceiling is the stricter of the two.
    set_max_fret(15)

    set_capo(2)

    try:

        assert get_effective_max_fret() == 13

        tuning_notes = [67, 52, 57, 62, 64]  # A Modal Sawmill

        candidates = chord_generator.generate_candidates(
            type(
                "T", (), {"notes": tuning_notes}
            )(),
            "E", 4, "m", "Minor"
        )

        assert candidates != []

    finally:

        set_capo(0)
