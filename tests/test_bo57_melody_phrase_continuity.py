"""
tests/test_bo57_melody_phrase_continuity.py

Regression tests for BO-57: melody-only hand-position (HP)
continuity, for phrases with NO chord anchor of any kind.

Root cause (BO-57 investigation, fully traced against real code):
Cousin Sally Brown has zero harmonies at all, so BO-54's chord-
shape HP-continuity mechanism never activates for it -- the
entire melody sequence was decided by _choose_melody_position()'s
own chord-less fallback path alone. That fallback was found to
prefer staying on the same string as the two immediately
preceding notes UNCONDITIONALLY -- with no bound on how far up
the neck that string's own next candidate fret could be -- via
three separate, stacked mechanisms (pattern_continuity_bonus,
then string_distance, each still deciding the tie the other
left behind): confirmed directly, a demonstrably worse-scored
high-fret candidate would still beat the target low-fret one that
best_position() itself already correctly ranked higher.

Fix: a new, bounded lookahead (_melody_phrase_notes_played(),
MELODY_PHRASE_LOOKAHEAD=6 notes) reusing the exact same open/
fretted-position check already established in chord_service.py's
own BO-54 mechanism -- scoped to fire ONLY when no chord anchor
of any kind applies, so chord-anchored songs are structurally
guaranteed unaffected (confirmed directly below, not merely
assumed).

All real fret/string values in this file are taken directly from
BO's own actual generated output for Cousin Sally Brown / C
Standard (gCGBD), cross-checked against the user's own real CSV
testing evidence.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _choose_melody_position, generate_tab_from_template
)

from melody_box_analysis import realize_note

from models import Note


C_STANDARD = get_tunings()["C Standard"]  # gCGBD

OPEN_NOTES = C_STANDARD.notes[1:]


def _generate_csb():

    p = MuseScoreFile("scores/Cousin Sally Brown.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, C_STANDARD, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo57_csb.mscz"
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith(".mscx")
        ][0]

        content = z.read(mscx_name)

    return output_path, ET.fromstring(content)


def _notes_in_measure(root, measure_index):

    score_el = root.find(".//{*}Score")

    staves = [
        c for c in score_el if c.tag.split("}")[-1] == "Staff"
    ]

    tab_staff = next(
        s for s in staves if s.attrib.get("id") == "1"
    )

    measures = tab_staff.findall("{*}Measure")

    result = []

    for element in measures[measure_index].iter():

        if element.tag.split("}")[-1] == "Chord":

            note = element.find("{*}Note")

            pitch = int(note.find("{*}pitch").text)

            fret = int(note.find("{*}fret").text)

            string = int(note.find("{*}string").text)

            result.append((pitch, fret, string))

    return result


# ---------------------------------------------------------
# 1 -- real CSB case: C4->E4 (measure 1). BO-54's HP-continuity
# does not apply here (no chord data at all); the fix must still
# select the low, comfortable target position.
# ---------------------------------------------------------

def test_csb_measure_1_c4_to_e4_stays_low():

    import os

    output_path, root = _generate_csb()

    try:

        notes = _notes_in_measure(root, 0)  # measure 1

        c4 = next(n for n in notes if n[0] == 60)

        e4 = next(n for n in notes if n[0] == 64)

        # Real, confirmed target (user's own CSV): C4 at fret 1
        # (string_index 2, MuseScore string "1"), E4 at fret 2
        # (string_index 3, MuseScore string "0").
        assert c4 == (60, 1, 1)

        assert e4 == (64, 2, 0)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- real CSB case: the G4 run (measure 7). Confirms the
# mechanism correctly anticipates a MULTI-note run, not just the
# single immediately-following note.
# ---------------------------------------------------------

def test_csb_measure_7_g4_run_stays_in_one_position():

    import os

    output_path, root = _generate_csb()

    try:

        notes = _notes_in_measure(root, 6)  # measure 7

        g4_notes = [n for n in notes if n[0] == 67]

        assert len(g4_notes) == 3

        # Real, confirmed: all 3 G4 occurrences now land at the
        # low position (fret 5, string_index 0) instead of the
        # prior fret 12 -- a direct, real fix for the reported
        # 3-12 (x3) behavior.
        for pitch, fret, string in g4_notes:

            assert fret == 5

            assert string == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- direct mechanism test: _melody_phrase_notes_played()
# genuinely distinguishes what best_position() alone, combined
# with the OLD pattern_continuity_bonus/string_distance
# mechanisms, could not
# ---------------------------------------------------------

def test_phrase_lookahead_overrides_same_string_preference():

    # Real, confirmed chain from Cousin Sally Brown / C Standard:
    # G3 -> A3 -> C4, all landing on the same string (string_
    # index 1), establishing exactly the pattern the OLD
    # mechanism would keep climbing indefinitely.
    g3 = _choose_melody_position(55, OPEN_NOTES)

    a3 = _choose_melody_position(
        57, OPEN_NOTES, previous_position=g3
    )

    c4 = _choose_melody_position(
        60, OPEN_NOTES, previous_position=a3,
        second_previous_position=g3
    )

    assert g3["string"] == a3["string"] == c4["string"] == 1

    # The real following phrase after this C4 (E4, D4, C4 from
    # measure 2) -- the fix's own real, confirmed window.
    window = [
        Note(midi=64), Note(midi=62), Note(midi=60),
        Note(midi=57), Note(midi=55), Note(midi=64)
    ]

    realized_window = [
        realize_note(n, C_STANDARD) for n in window
    ]

    e4 = _choose_melody_position(
        64, OPEN_NOTES, previous_position=c4,
        second_previous_position=a3,
        melody_phrase_notes=realized_window
    )

    # Real, confirmed: WITHOUT melody_phrase_notes, this same
    # call would return string_index 1 (fret 9) -- the same
    # string as c4/a3/g3, matching the exact regression this
    # test exists to catch. WITH it, the genuinely better-scored,
    # phrase-coherent low position wins instead.
    assert e4["string"] == 3

    assert e4["fret"] == 2

    # Confirms the OLD mechanism alone (no melody_phrase_notes)
    # still reproduces the original, real regression -- proving
    # this test genuinely distinguishes old from new behavior,
    # not merely a directional property both would satisfy.
    e4_without_fix = _choose_melody_position(
        64, OPEN_NOTES, previous_position=c4,
        second_previous_position=a3
    )

    assert e4_without_fix["string"] == 1

    assert e4_without_fix["fret"] == 9

    assert e4_without_fix != e4


# ---------------------------------------------------------
# 4 -- chord-anchored songs remain completely unaffected
# ---------------------------------------------------------

def test_chord_anchored_song_unaffected():

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    double_d = get_tunings()["Double D"]

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, double_d, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo57_chord_anchored.mscz"
        )
    )

    import os

    try:

        # Real, confirmed values -- unchanged from every BO-54/
        # BO-54-revision confirmation earlier in this project.
        assert applied == 56

        assert skipped == 0

        assert exceptions == []

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        notes = _notes_in_measure(root, 1)  # measure 2, Cmaj7

        b4 = next(n for n in notes if n[0] == 71)

        a4 = next(n for n in notes if n[0] == 69)

        g4 = next(n for n in notes if n[0] == 67)

        f4 = next(n for n in notes if n[0] == 65)

        # Real, confirmed values -- exactly matching the BO-54-
        # revision's own already-verified output, unchanged.
        assert b4 == (71, 9, 1)

        assert a4 == (69, 7, 1)

        assert g4 == (67, 10, 2)

        assert f4 == (65, 8, 2)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- a genuine, evidence-based divergence from the CSV's own
# literal target is expected and correct in at least one real
# case (measure 12's final C4)
# ---------------------------------------------------------

def test_csb_measure_12_c4_anticipates_following_g4_run():

    import os

    output_path, root = _generate_csb()

    try:

        notes = _notes_in_measure(root, 11)  # measure 12

        c4_notes = [n for n in notes if n[0] == 60]

        final_c4 = c4_notes[-1]

        # BO-117 -- this specific C4 is a 2.0-beat half note,
        # immediately followed by the real 3-note G4 run (measure
        # 13). Prior to BO-117, fret 5 was deliberately preferred
        # here because it let all 6 notes of the following phrase
        # (this C4 plus the G4 run and its own continuation) stay
        # in one hand position -- a duration-blind reading of
        # phrase coverage. BO-117 established that a note >= 1.5
        # beats provides a genuine, natural opportunity to move
        # the hand afterward, so phrase lookahead no longer looks
        # past this C4 at all -- it now correctly matches the
        # CSV's own literal target (fret 1), and the following G4
        # run remains correctly handled by the existing HP/
        # position logic once the hand actually moves for it.
        assert final_c4 == (60, 1, 1)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- real CSB case: measure 2's E4 pair, through the FULL
# generation pipeline. This is the specific real case that
# genuinely requires BOTH the pattern_continuity_bonus AND
# string_distance fixes (unlike measure 1, where C4 itself
# already breaks the established-string pattern before E4 is
# reached) -- confirmed the true established-pattern scenario
# (G3->A3, both string_index 1, immediately before this E4).
# ---------------------------------------------------------

def test_csb_measure_2_e4_pair_real_pipeline():

    import os

    output_path, root = _generate_csb()

    try:

        notes = _notes_in_measure(root, 1)  # measure 2

        e4_notes = [n for n in notes if n[0] == 64]

        assert len(e4_notes) == 2

        for pitch, fret, string in e4_notes:

            assert (fret, string) == (2, 0)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
