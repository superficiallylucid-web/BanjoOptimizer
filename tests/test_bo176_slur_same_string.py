"""
tests/test_bo176_slur_same_string.py

Focused tests for BO-176: a slur physically requires both
connected notes to be played on the same string (hammer-on/
pull-off/slide -- there is no way to slur across strings on a
fretted instrument). _choose_melody_position() had no awareness
of slurs at all before this change.

Implementation: a new slur_from_string parameter, checked at the
absolute top of _choose_melody_position() -- before even the
existing fd_shape_values exact-inclusion fast path -- returning
immediately with the first candidate on that exact string, when
one exists. Per explicit instruction, this outweighs every other
mechanism in the function, including an exact chord-shape match.
The caller (generate_tab_from_template()) supplies slur_from_
string only when the current event's own slur_elements contains
a Spanner with a <prev> child (confirmed via real source XML:
this is how MuseScore marks the SECOND note of a slur), using the
immediately preceding melody note's own actual chosen string --
never a recomputed or assumed value.
"""

import sys

sys.path.insert(0, '.')

import main

from parser import MuseScoreFile

from score_generator import _choose_melody_position

from conftest import fixture_path, TEST_OUTPUT_DIR


def _generate():

    result = main.run_optimizer(
        score_path=str(fixture_path("BO-174_input_score.mscz")),
        tuning_symbol="gCGCD",
        capo=2,
        fifth_string="A",
        output_folder=str(TEST_OUTPUT_DIR),
        output_key="D"
    )

    return result["scores"][0]["generated_files"][0]["tab_path"]


def _positions_by_measure_beat(tab_path):

    p = MuseScoreFile(tab_path)

    p.open()

    staff = p.root.find('.//{*}Staff[@id="1"]')

    measures = staff.findall("{*}Measure")

    positions = {}

    for m_idx, measure in enumerate(measures, start=1):

        for voice in measure.findall("{*}voice"):

            beat = 0.0

            for element in voice:

                tag = element.tag.split("}")[-1]

                if tag in ("Chord", "Rest"):

                    duration = p._duration_value(element)

                    if tag == "Chord":

                        for note in element.findall("{*}Note"):

                            pitch_el = note.find("{*}pitch")

                            fret_el = note.find("{*}fret")

                            string_el = note.find("{*}string")

                            if (
                                pitch_el is not None
                                and fret_el is not None
                            ):

                                positions[
                                    (m_idx, round(beat + 1, 4))
                                ] = (
                                    int(string_el.text) + 1,
                                    int(fret_el.text)
                                )

                    beat += duration

    return positions


# ---------------------------------------------------------
# 1 -- production-path regression: a real slur (measure 3, beat
# 1 -> beat 1.5, confirmed via the raw source XML's own <Spanner
# type="Slur"><prev> element) forces the second note onto the
# first note's own actual string.
# ---------------------------------------------------------

def test_slurred_note_lands_on_slur_start_string():

    positions = _positions_by_measure_beat(_generate())

    slur_start = positions[(3, 1.0)]

    slur_end = positions[(3, 1.5)]

    assert slur_start[0] == slur_end[0], (
        f"Slurred notes must share a string -- slur-start is on "
        f"string {slur_start[0]}, slur-end landed on "
        f"{slur_end[0]}."
    )

    # Real, confirmed values: string 3, frets 4 and 5.
    assert slur_start == (3, 4)

    assert slur_end == (3, 5)


# ---------------------------------------------------------
# 2 -- a note NOT part of any slur is genuinely unaffected (the
# very next note, same pitch, no slur element at all).
# ---------------------------------------------------------

def test_unslurred_note_unaffected():

    positions = _positions_by_measure_beat(_generate())

    # Real, confirmed unchanged value -- this note has no slur
    # element at all in the source, so it is decided entirely by
    # the existing, pre-BO-176 mechanisms (here, the Bm chord's
    # own exact-inclusion match).
    assert positions[(3, 2.0)] == (2, 0)


# ---------------------------------------------------------
# 3 -- unit-level: the slur constraint outweighs even an exact
# fd_shape_values match on a different string, confirming the
# priority ordering specified explicitly (this constraint "can
# outweigh anything else").
# ---------------------------------------------------------

def test_slur_constraint_outranks_exact_fd_match():

    # A synthetic shape that exactly matches pitch 67 (F#4) on
    # string_index 1 only (fret 10) -- confirmed directly against
    # find_positions(67, ...), which also has a real candidate on
    # string_index 3 (fret 3), letting this test force the slur
    # constraint toward a DIFFERENT string than the one the exact-
    # inclusion match would otherwise win.
    from tunings import get_tunings

    tuning = get_tunings()["Double D"]  # aDADE

    open_notes = tuning.notes[1:]

    fd_shape_values = [0, 10, 0, 0]

    result_without_slur = _choose_melody_position(
        67, open_notes, fd_shape_values=fd_shape_values
    )

    result_with_slur = _choose_melody_position(
        67, open_notes, fd_shape_values=fd_shape_values,
        slur_from_string=3
    )

    # Without the slur constraint, the exact-inclusion fast path
    # wins (confirming this synthetic setup genuinely exercises
    # the priority conflict this test is checking).
    assert result_without_slur["string"] == 1

    # With it, the slur constraint wins instead -- string 3,
    # regardless of the exact fd match available elsewhere.
    assert result_with_slur["string"] == 3



# ---------------------------------------------------------
# 4 -- unit-level: when the forced string is genuinely
# unreachable for this pitch, the function falls through to
# existing behavior unchanged rather than returning None.
# ---------------------------------------------------------

def test_slur_constraint_falls_through_when_string_unreachable():

    from tunings import get_tunings

    tuning = get_tunings()["Double D"]

    open_notes = tuning.notes[1:]

    # string_index 99 can never be a real candidate -- confirms
    # the fallback path is genuinely reached rather than
    # returning None or raising.
    result = _choose_melody_position(
        62, open_notes, slur_from_string=99
    )

    assert result is not None

    assert result["string"] != 99
