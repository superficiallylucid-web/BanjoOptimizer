"""
tests/test_bo187_anchor_at_or_above.py

Regression tests for BO-187: a chord anchor (working_fret_
anchor/following_working_fret_anchor in _choose_melody_position())
represents "at or above the chord's own lowest (working) fret",
not a symmetric target distance -- per direct correction. A
candidate BELOW the anchor is genuinely out of range of it, not
merely "some distance away" the same way a candidate above it is.

Before this, the symmetric distance abs(fret - anchor) let a
melody note land on a fret BELOW the chord's own working fret
whenever that fret happened to be numerically closer to the
anchor than a preferred, at-or-above alternative -- even though
"below the chord" is a genuinely worse hand-position outcome than
"a little above it". Real, reported case: Let It Snow / aEADE
(gDGCD capo 2, 5th string A, key F) -- 4 melody notes (measures
1, 3, 4) were written on a fret below their own chord's working
fret purely because it was closer, when the preferred position
(matching the tab actually surrounding each note) was further
above the chord instead.

The fix (_anchor_distance(), inside _choose_melody_position()'s
own _sort_key()) keeps the exact prior min(distance, CAP)
behavior for at-or-above candidates, and scores a below-anchor
candidate as CAP + min(how far below, CAP) -- always strictly
worse than every at-or-above candidate, but still capped (not
unbounded) so an anchor far beyond every real candidate still
lets best_position()'s own static score decide among them, per
BO-24's own established guarantee.

This is a genuine, deliberate semantic change to the anchor
mechanism, not a narrow bug fix -- it breaks a substantial number
of pre-existing tests across several earlier BO areas (24, 25,
30, 57, 60, 62, 174) that asserted the OLD symmetric behavior.
Per direct instruction, those are left as-is rather than updated
here (same handling as BO-183).
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

from score_generator import (
    _choose_melody_position, MELODY_ANCHOR_DISTANCE_CAP
)

from tunings import get_tunings

from conftest import fixture_path, TEST_OUTPUT_DIR

import main


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

OPEN_NOTES = A_MODAL_SAWMILL.notes[1:]  # 4th to 1st


# ---------------------------------------------------------
# 1 -- the asymmetric distance metric itself, in isolation
# ---------------------------------------------------------

def test_below_anchor_candidate_loses_to_farther_above_anchor():

    # midi 65 (E4): reachable at fret 8 on the 3rd string (open
    # 57), and also at other, lower positions. Anchor 5: any
    # candidate below fret 5 is now out of range of it; fret 8
    # (3 away, at-or-above) must win even though a below-anchor
    # candidate could be numerically closer under the old
    # symmetric rule.
    chosen = _choose_melody_position(
        65, OPEN_NOTES, working_fret_anchor=5
    )

    assert chosen["fret"] == 8


def test_at_or_above_anchor_still_uses_plain_distance():

    # Confirms the at-or-above side is genuinely unchanged: a
    # candidate exactly AT the anchor (distance 0) still beats a
    # farther at-or-above alternative, exactly as before this BO.
    chosen = _choose_melody_position(
        67, OPEN_NOTES, working_fret_anchor=5
    )

    # 67 is reachable at fret 5 (2nd string, open 62) -- exactly
    # at the anchor.
    assert chosen["fret"] == 5


def test_extreme_anchor_still_capped_both_directions():

    # BO-24's own established guarantee (test_large_chord_
    # position_change_is_capped_not_forced): an anchor far beyond
    # every real candidate must not keep distinguishing
    # candidates from each other by raw fret value forever --
    # confirms the below-anchor penalty is capped at
    # MELODY_ANCHOR_DISTANCE_CAP, not unbounded, so this still
    # degrades to best_position()'s own static preference for a
    # sufficiently extreme anchor, matching the un-anchored case
    # exactly.
    far_anchor = 19

    chosen = _choose_melody_position(
        64, OPEN_NOTES, working_fret_anchor=far_anchor
    )

    unanchored = _choose_melody_position(64, OPEN_NOTES)

    assert chosen == unanchored

    assert MELODY_ANCHOR_DISTANCE_CAP < far_anchor


# ---------------------------------------------------------
# 2 -- the real, reported case: Let It Snow / aEADE
# ---------------------------------------------------------

def _generate():

    return main.run_optimizer(
        score_path=str(fixture_path("Let_It_Snow.mscz")),
        tuning_symbol="gDGCD",
        capo=2,
        fifth_string="A",
        output_key="F",
        output_folder=str(TEST_OUTPUT_DIR)
    )


def _notes_by_measure(tab_path):

    with zipfile.ZipFile(tab_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith(".mscx")
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    for staff in root.iter():

        if (
            staff.tag.split("}")[-1] == "Staff"
            and staff.attrib.get("id") == "1"
        ):

            measures = staff.findall("{*}Measure")

            result = []

            for measure in measures:

                notes = []

                for note in measure.iter():

                    if note.tag.split("}")[-1] != "Note":

                        continue

                    fret_el = note.find("{*}fret")

                    string_el = note.find("{*}string")

                    if fret_el is not None:

                        notes.append(
                            (
                                int(fret_el.text),
                                int(string_el.text)
                            )
                        )

                result.append(notes)

            return result

    return None


def test_real_let_it_snow_measure1_repeated_pitch_moved_to_string1(
):

    # This BO's own fix does not address the very first note of
    # the piece (measure 1, beat 1): it has no chord anchor at
    # all yet (nothing precedes it), so _anchor_distance() never
    # applies there -- BO-188 (a separate, later fix: propagates
    # a following note's own anchor backward through a chain of
    # identical-pitch notes) addresses this specific case
    # instead. See tests/test_bo188_following_note_anchor.py.
    result = _generate()

    gen = result["scores"][0]["generated_files"][0]

    measures = _notes_by_measure(gen["tab_path"])

    # measure 1 (index 0): both the first note and the second,
    # identical-pitch (60) note now land on fret 8 -- BO-188's
    # own fix, not this BO's.
    assert (8, 3) in measures[0]


def test_real_let_it_snow_measures_1_3_4_stay_at_or_above_anchor(
):

    result = _generate()

    gen = result["scores"][0]["generated_files"][0]

    measures = _notes_by_measure(gen["tab_path"])

    # Row 2 (CSV): measure 1, the pitch-70 note -- preferred
    # "2-8" (external 2nd string, fret 8) -- XML string 1.
    assert (8, 1) in measures[0]

    # Row 3 (CSV): measure 3, the pitch-65 passing note --
    # preferred "3-8" (external 3rd string, fret 8) -- XML
    # string 2.
    assert (8, 2) in measures[2]

    # Row 4/5 (CSV): measure 4, the pitch-65 and pitch-60 notes
    # -- preferred "3-8" and "4-8" -- XML strings 2 and 3.
    assert (8, 2) in measures[3]

    assert (8, 3) in measures[3]
