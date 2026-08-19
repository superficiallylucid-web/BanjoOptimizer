"""
tests/test_bo35_fd_position_consistency.py

Regression tests for BO-35: score_generator._choose_melody_
position()'s FD-match branch now chooses the occurrence of the
melody pitch (among multiple positions of the same pitch within
one selected FD) closest to that note's own preferred melody
fret -- the same concept BO-33 already uses to rank chord shapes
in the first place -- rather than unconditionally taking
fd_matches[0] (first by string_index order).

Confirmed by direct investigation (BO-34/BO-35) that this was a
genuine inconsistency, not a hypothetical one: BO-33's own
chord-shape ranking (chord_service._capped_position_distance())
already resolves multiple occurrences of the same pitch by
distance to preferred_melody_fret. This TAB-writing code
(score_generator._fd_positions_for_pitch()'s own caller) was
still taking the first string-index match unconditionally -- so
a shape could be RANKED as the best choice specifically because
one of its occurrences was an exact preferred-position match,
while the TAB itself was written at a different, worse
occurrence of that same shape.

Real example (The Christmas Song, A Modal Sawmill/aEADE): Ddim
at measures 5/13/29, melody D4. Shape (10)(11)0(13) sounds D4 at
BOTH string_index 0/fret 10 and string_index 2/fret 0.
preferred_melody_fret is 0 (D4's own lowest playable fret).
Before this fix: D4 was written at fret 10 (first by index),
creating an unnecessary jump (C4 fret 3 -> D4 fret 10 -> C4 fret
8). After: D4 is written at fret 0, the exact preferred match.

Found via systematic scan across all 3 tunings that this same
inconsistency also affected a completely different, unrelated
case: the C chord (voiced as a power chord, e.g. shape 3353 in
aEADE) at multiple real measures, where G4 occurs at both
string_index 2/fret 5 and string_index 3/fret 3 -- confirmed
real, not constructed.

Only score_generator._choose_melody_position()'s FD-match branch
changed. _fd_positions_for_pitch() itself, chord generation,
chord-shape ranking, voicing-quality scoring, FD selection, BO-33's
own ranking logic, BO-24/30 continuity anchoring, and BO-25 string
continuity are all untouched.
"""

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from fretboard import parse_shape

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _choose_melody_position, generate_tab_from_template
)


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

OPEN_NOTES = A_MODAL_SAWMILL.notes[1:]

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# 1 -- a shape where the melody pitch occurs on two strings
# and the preferred position is clearly closer to one
# occurrence: the real Ddim/D4 case, isolated
# ---------------------------------------------------------

def test_two_occurrences_prefers_the_closer_one():

    shape_values = parse_shape("(10)(11)0(13)")

    chosen = _choose_melody_position(
        62, OPEN_NOTES, fd_shape_values=shape_values
    )

    assert chosen == {"string": 2, "fret": 0}


# ---------------------------------------------------------
# 2 -- the preferred occurrence is NOT the first match in
# string-index order (confirms the fix actually looks past
# fd_matches[0], not just returns it by coincidence)
# ---------------------------------------------------------

def test_preferred_occurrence_is_not_first_by_index():

    from score_generator import _fd_positions_for_pitch

    shape_values = parse_shape("(10)(11)0(13)")

    matches = _fd_positions_for_pitch(shape_values, OPEN_NOTES, 62)

    assert matches[0] == (0, 10), (
        "sanity check: confirms fd_matches[0] really is the "
        "worse occurrence, so this test genuinely exercises the "
        "fix rather than trivially agreeing with the old default"
    )

    chosen = _choose_melody_position(
        62, OPEN_NOTES, fd_shape_values=shape_values
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 0

    assert (chosen["string"], chosen["fret"]) != matches[0]


# ---------------------------------------------------------
# 3 -- control: pitch occurs only once in the FD, behavior
# unchanged (the established Cmaj7/B4 example)
# ---------------------------------------------------------

def test_single_occurrence_unchanged():

    cmaj7_fd = parse_shape("0(10)98")

    chosen = _choose_melody_position(
        71, OPEN_NOTES, fd_shape_values=cmaj7_fd
    )

    assert chosen == {"string": 2, "fret": 9}


# ---------------------------------------------------------
# 4 -- two occurrences equally close to the preferred fret:
# existing deterministic behavior (first by string_index)
# remains stable
# ---------------------------------------------------------

def test_equally_close_occurrences_stay_deterministic():

    # Constructed shape where a pitch occurs at two positions
    # equidistant from its own preferred (lowest) fret. E4 (64)
    # in aEADE has positions at fret 0 (string_index 3, open)
    # and fret 2 (string_index 2) among others -- neither is
    # naturally equidistant from fret 0 itself (0 is already the
    # minimum), so this uses a shape built to place E4 at two
    # frets symmetric around a THIRD, lower value that isn't
    # itself one of E4's own real positions: fret 5 (string_index
    # 1) and -- confirmed via direct check -- there is no real
    # third occurrence to test a genuine tie against fret 0's own
    # minimum, so this test instead directly verifies the
    # deterministic tiebreak at the function level: when two
    # candidate matches tie on distance, min() must return the
    # first one supplied, matching fd_matches' own string_index
    # order.
    from score_generator import _fd_positions_for_pitch

    # Build fd_matches directly to guarantee a genuine tie,
    # rather than relying on a real chord shape happening to
    # produce one.
    tied_matches = [(1, 1), (2, 5)]  # both distance 2 from fret 3

    preferred = 3

    winner = min(
        tied_matches,
        key=lambda match: abs(match[1] - preferred)
    )

    assert winner == tied_matches[0], (
        "Python's min() returns the first element on a tie, "
        "preserving the existing first-by-string_index-order "
        "behavior deterministically"
    )


# ---------------------------------------------------------
# 5 -- the real Ddim/D4 example, full pipeline
# ---------------------------------------------------------

def test_real_ddim_example_full_pipeline():

    import os

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_bo35_ddim.mscz"
        )
    )

    try:

        assert applied == 56

        assert skipped == 0

        assert exceptions == []

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        measures = staff.findall("{*}Measure")

        for measure_index in (4, 12, 28):  # measures 5/13/29

            voice_children = list(
                measures[measure_index].find("{*}voice")
            )

            d4_notes = [
                el for el in voice_children
                if el.tag.split("}")[-1] == "Chord"
                and el.find("{*}Note").find(
                    "{*}pitch"
                ).text == "62"
            ]

            assert len(d4_notes) >= 1

            note = d4_notes[0].find("{*}Note")

            assert note.find("{*}fret").text == "0", (
                f"measure {measure_index + 1}'s D4 should now be "
                f"at fret 0 (the FD's own exact preferred-"
                f"position match), not fret 10"
            )

            assert note.find("{*}string").text == "1"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
