"""
tests/test_bo38_open_string_and_pattern_continuity.py

Regression tests for BO-38 Groups A and C: score_generator.
_choose_melody_position() gained two new sort-key tiebreak
layers, both positioned between BO-37's own preceding_fd_
violation and BO-24/30's own fret_distance:

Group A -- open_string_bonus: an open-string candidate that is
already the best-(or tied-for-best-)scored option on playability
grounds alone should not lose to a worse-scored, fretted
candidate purely because a FOLLOWING chord anchor happens to sit
closer to that fretted candidate. Scoped to working_fret_anchor
is None (no PRECEDING anchor) -- a genuine, established preceding
hand position is real continuity and must still win legitimately.

Real example (The Christmas Song, Double C/gCGCD): measure 1's
opening C4 has no preceding chord at all; measure 32's D4 sits
immediately before a high "C" chord (working fret 14). In both
cases the open string (fret 0) is already best_position()'s own
top-or-tied-top choice, but the following anchor was previously
overpowering it entirely (even pulling toward the WORST-scored
candidate in measure 32's case, score -3 vs the open string's
12).

Group C -- pattern_continuity_bonus: once a phrase has settled
onto a string for TWO consecutive melody notes (a genuine,
established pattern -- not a single coincidental match), staying
there is preferred over chasing a following chord's own raw
fret-distance, provided the same-string candidate remains
reasonably playable (score >= 0). Also scoped to working_fret_
anchor is None, and requires BOTH previous_position and second_
previous_position to independently share the candidate's string.

Real example: measure 23's D#4 breaks an established string-2
pattern (F4/D#4/F4 all on string_index 2) to chase a following
Dsus2 anchor whose own onset note actually resolves to an open
string within its own shape -- making the anchor's raw fret-
distance an unreliable signal of where the hand needs to be.

IMPORTANT validation lesson from developing this fix: the first
version of pattern_continuity_bonus used only a SINGLE previous_
position (no second_previous_position requirement) and broke 4
of BO-25's own established tests, since a single coincidental
same-string match is not the same thing as a genuine established
pattern. Requiring both preceding notes to share the string was
the correction. A second, more subtle regression then appeared:
a chord onset's own Rule-#1-resolved position can coincidentally
land on the same string as a later, unrelated surrounding note,
which looked like a genuine two-note pattern without one actually
existing -- fixed by excluding chord-onset positions from ever
propagating into second_previous_melody_position in generate_tab_
from_template()'s own sequential tracking.

Only score_generator._choose_melody_position()'s sort key and its
own new second_previous_position parameter, plus the corresponding
pre-computation/tracking in generate_tab_from_template(), changed.
BO-24/25/30/33/35/37 established behavior is untouched.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _choose_melody_position, generate_tab_from_template
)


DOUBLE_C = get_tunings()["Double C"]  # gCGCD

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# Group A -- 1: the real measure 1 case (no preceding anchor
# at all)
# ---------------------------------------------------------

def test_real_c4_measure1_open_string_wins():

    open_notes = DOUBLE_C.notes[1:]

    chosen = _choose_melody_position(
        60, open_notes,  # C4
        following_working_fret_anchor=7  # the "C" chord, high
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 0


# ---------------------------------------------------------
# Group A -- 2: the real measure 32 case, where the open
# string is tied for best score, not the outright best
# ---------------------------------------------------------

def test_real_d4_measure32_open_string_wins():

    open_notes = DOUBLE_C.notes[1:]

    chosen = _choose_melody_position(
        62, open_notes,  # D4
        preceding_chord_shape_values=[0, 0, 0, 5],  # C5, no D4 match
        following_working_fret_anchor=14  # extreme high anchor
    )

    assert chosen["string"] == 3

    assert chosen["fret"] == 0


# ---------------------------------------------------------
# Group A -- 3: control -- a preceding anchor must still win
# legitimately, even over an open string
# ---------------------------------------------------------

def test_open_string_does_not_override_genuine_preceding_anchor():

    open_notes = DOUBLE_C.notes[1:]

    # C4's own open-string candidate (idx2/fret0, score 14) is
    # the best-scored option, but a genuine PRECEDING anchor
    # (working_fret_anchor) must still be able to pull toward a
    # different, fretted candidate when that anchor is real
    # continuity -- open_string_bonus must not apply here at all.
    without_preceding = _choose_melody_position(60, open_notes)

    with_preceding = _choose_melody_position(
        60, open_notes, working_fret_anchor=5
    )

    assert with_preceding["fret"] == 5, (
        "a genuine preceding anchor must still win over the open "
        "string -- open_string_bonus is scoped to working_fret_"
        "anchor is None specifically"
    )

    assert with_preceding != without_preceding


# ---------------------------------------------------------
# Group C -- 4: the real measure 23 D#4 case
# ---------------------------------------------------------

def test_real_ds4_measure23_pattern_continuity_wins():

    open_notes = DOUBLE_C.notes[1:]

    chosen = _choose_melody_position(
        63, open_notes,  # D#4
        preceding_chord_shape_values=[9, 10, 10, 0],  # A#maj7
        following_working_fret_anchor=2,  # Dsus2
        previous_position={"string": 1, "fret": 10},
        second_previous_position={"string": 1, "fret": 10}
    )

    assert chosen["string"] == 1

    assert chosen["fret"] == 8


# ---------------------------------------------------------
# Group C -- 5: control -- a SINGLE coincidental same-string
# match (no genuine two-note pattern) must NOT override a
# real fret_distance improvement (the real measure-4 A4 case
# that broke the first version of this bonus)
# ---------------------------------------------------------

def test_single_same_string_match_does_not_override_fret_distance():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    chosen = _choose_melody_position(
        69, open_notes,  # A4
        preceding_chord_shape_values=[0, 3, 5, 0],
        following_working_fret_anchor=3,
        previous_position={"string": 1, "fret": 3},
        second_previous_position=None
        # only ONE preceding note shares string_index 1 -- not a
        # genuine established pattern
    )

    assert chosen["string"] == 3

    assert chosen["fret"] == 5


# ---------------------------------------------------------
# Group C -- 6: control -- a genuine preceding anchor still
# wins over pattern continuity (BO-25's own established
# examples, confirmed still passing directly)
# ---------------------------------------------------------

def test_pattern_continuity_does_not_override_preceding_anchor():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    # Real BO-25 example: A4 with a genuine preceding anchor
    # (working_fret_anchor=13) must reach string_index1/fret12
    # regardless of a same-string previous_position pointing
    # elsewhere.
    chosen = _choose_melody_position(
        69, open_notes,  # A4
        working_fret_anchor=13,
        previous_position={"string": 3, "fret": 3},
        second_previous_position={"string": 3, "fret": 3}
    )

    assert chosen["string"] == 1

    assert chosen["fret"] == 12


# ---------------------------------------------------------
# 7: full pipeline -- all three real examples, end to end,
# plus FD/TAB consistency intact
# ---------------------------------------------------------

def test_full_pipeline_real_examples_and_consistency():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="test_bo38_pipeline.mscz"
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

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(fret_diagrams) == 56

        for fd in fret_diagrams:

            assert fd.find("{*}color") is None

        measures = staff.findall("{*}Measure")

        # measure 1: real, confirmed C4 open-string case
        m1_voice = list(measures[0].find("{*}voice"))

        c4_chord = next(
            el for el in m1_voice
            if el.tag.split("}")[-1] == "Chord"
        )

        c4_note = c4_chord.find("{*}Note")

        assert c4_note.find("{*}fret").text == "0"

        assert c4_note.find("{*}string").text == "1"

        # measure 32: real, confirmed D4 open-string case
        m32_voice = list(measures[31].find("{*}voice"))

        d4_chord = next(
            el for el in m32_voice
            if el.tag.split("}")[-1] == "Chord"
            and el.find("{*}Note").find("{*}pitch").text == "62"
        )

        d4_note = d4_chord.find("{*}Note")

        assert d4_note.find("{*}fret").text == "0"

        assert d4_note.find("{*}string").text == "0"

        # measure 23: real, confirmed D#4 pattern-continuity case
        m23_voice = list(measures[22].find("{*}voice"))

        ds4_chords = [
            el for el in m23_voice
            if el.tag.split("}")[-1] == "Chord"
            and el.find("{*}Note").find("{*}pitch").text == "63"
        ]

        assert len(ds4_chords) == 2

        for ds4_chord in ds4_chords:

            ds4_note = ds4_chord.find("{*}Note")

            assert ds4_note.find("{*}fret").text == "8"

            assert ds4_note.find("{*}string").text == "2"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
