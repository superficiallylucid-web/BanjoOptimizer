"""
tests/test_bo40_fifth_string_transition.py

Regression tests for BO-40: a narrow, separate 5th-string
transition mechanism -- NOT a normal melody-position candidate
and NOT folded into _choose_melody_position()'s own sort key at
all. Applied only AFTER the normal four-string choice is already
made, only when ALL THREE conditions hold:

  1. the note's own exact pitch equals tuning.notes[0] (the open
     5th string's own pitch) -- the ONLY way this can ever apply;
  2. the note is not itself a chord onset (FD compatibility at a
     chord onset remains completely untouched -- this check never
     even runs for an onset note);
  3. the normal four-string choice is genuinely far (string_
     distance >= 2) from the next chord onset's own REAL position.

Encoding verified against a real, genuine MuseScore-created
reference file (The Christmas Song (with TAB and composer).mscz,
its own original TAB before BO-17's own "strip the banjo part"
process, containing 27 real 5th-string notes) -- NOT inferred
from the existing muse_string = 3 - internal_index formula, which
is invalid for the 5th string (3-4=-1). Confirmed directly:
<pitch>67</pitch><fret>0</fret><string>4</string> for an open
5th-string G4, full Chord/Note structure otherwise identical to
every other note.

Threshold (string_distance >= 2 to the next chord onset's own
real position) empirically verified against every one of the 19
real non-onset G4 occurrences across the whole song before
implementing: uniquely identifies the real, confirmed measure-22
case and correctly excludes every other one, including a second
candidate (measure 31) that turned out to already be well-
positioned once checked precisely.

IMPORTANT bug found and fixed during validation: the first
version computed "the next chord onset's own real position" via
a raw _fd_positions_for_pitch()[0] call (first match by string_
index order), which does not correctly reproduce the real
position when a pitch sounds on multiple strings within a chord's
own shape -- BO-35 already resolves that same situation by
picking the CLOSEST occurrence to the pitch's own preferred fret.
This caused a real, confirmed false positive at measure 16 (Ddim's
own shape sounds D4 on two strings; the raw first-match approach
reported the wrong one, incorrectly triggering BO-40 there). Fixed
by calling _choose_melody_position() directly for the onset note,
reusing the exact same logic the real TAB-writing loop itself
uses, rather than a second, diverging approximation of it.

Real examples confirmed in the actual generated output: Double C
measure 22 (G4 -> open 5th string, before the A#maj7 chord onset,
whose own B4/F4-driven high position makes the normal four-string
choice a 2-string jump away) and A Modal Sawmill measure 31 (A4 ->
open 5th string, before the G7 chord onset, an analogous B4-driven
high-position situation in a different tuning) -- confirming the
mechanism generalizes correctly, not overfit to one example.
Crucially, the immediately following note in both real cases
(F4 in Double C, B4 itself in A Modal Sawmill) is untouched --
still its own, correct pitch, never silently replaced by the
open drone.

Only score_generator.generate_tab_from_template()'s own pre-
computation (a new next_chord_onset_position_by_event_id dict)
and the post-choice override at the call to _choose_melody_
position() changed. find_positions(), the existing four-string
candidate pool, BO-24/25/30/33/35/37/38/39 established behavior,
and FD compatibility at chord onsets are all untouched.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_C = get_tunings()["Double C"]  # gCGCD

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


def _generate(tuning, filename):

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    return generate_tab_from_template(
        p, tuning, staff_used, TEMPLATE_PATH, "output", service,
        filename=filename
    )


def _staff_from(output_path):

    with zipfile.ZipFile(output_path) as archive:

        mscx_name = [
            n for n in archive.namelist() if n.endswith(".mscx")
        ][0]

        xml_bytes = archive.read(mscx_name)

    root = ET.fromstring(xml_bytes)

    return root.find('.//{*}Score/{*}Staff[@id="1"]')


# ---------------------------------------------------------
# 1 -- the real Double C measure 22 case
# ---------------------------------------------------------

def test_real_measure22_g4_uses_fifth_string():

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo40_m22.mscz"
    )

    try:

        staff = _staff_from(output_path)

        measures = staff.findall("{*}Measure")

        m22_voice = list(measures[21].find("{*}voice"))

        g4_chord = next(
            el for el in m22_voice
            if el.tag.split("}")[-1] == "Chord"
            and el.find("{*}Note").find("{*}pitch").text == "67"
        )

        g4_note = g4_chord.find("{*}Note")

        assert g4_note.find("{*}string").text == "4"

        assert g4_note.find("{*}fret").text == "0"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- the immediately following note keeps its OWN pitch --
# never silently replaced by the open drone
# ---------------------------------------------------------

def test_following_note_keeps_its_own_pitch():

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo40_m22_following.mscz"
    )

    try:

        staff = _staff_from(output_path)

        measures = staff.findall("{*}Measure")

        m22_voice = list(measures[21].find("{*}voice"))

        chords = [
            el for el in m22_voice
            if el.tag.split("}")[-1] == "Chord"
        ]

        pitches = [
            c.find("{*}Note").find("{*}pitch").text
            for c in chords
        ]

        # G#4(68), G4(67, ->5th string), F4(65), D#4(63),
        # then the A#maj7 chord onset's own F4(65)
        assert pitches == ["68", "67", "65", "63", "65"]

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- control: pitch does NOT equal the open 5th string --
# must never trigger, regardless of any upcoming jump
# ---------------------------------------------------------

def test_control_wrong_pitch_never_uses_fifth_string():

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo40_wrong_pitch.mscz"
    )

    try:

        staff = _staff_from(output_path)

        for note in staff.findall(".//{*}Note"):

            pitch = int(note.find("{*}pitch").text)

            string = note.find("{*}string").text

            if string == "4":

                assert pitch == 67, (
                    "only G4 (67, the real 5th-string pitch in "
                    "Double C) may ever appear on string=4"
                )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- control: chord-onset notes never use the 5th string,
# even when their own pitch matches it (FD compatibility
# stays authoritative)
# ---------------------------------------------------------

def test_control_chord_onset_never_uses_fifth_string():

    from score_generator import _melody_notes_at_harmony_onset

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    onset_g4_positions = [
        (h.measure, h.beat)
        for h in p.harmonies
        for n in _melody_notes_at_harmony_onset(h, p.score.notes)
        if n.midi == 67
    ]

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo40_onset_control.mscz"
    )

    try:

        assert exceptions == []

        staff = _staff_from(output_path)

        measures = staff.findall("{*}Measure")

        for measure_number, beat in onset_g4_positions:

            beat_accum = 0.0

            for el in measures[measure_number - 1].find(
                "{*}voice"
            ):

                tag = el.tag.split("}")[-1]

                if tag == "Chord" and abs(
                    beat_accum - beat
                ) < 0.001:

                    note = el.find("{*}Note")

                    if note.find("{*}pitch").text == "67":

                        assert (
                            note.find("{*}string").text != "4"
                        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- control: most real G4 occurrences (no significant
# upcoming jump) never use the 5th string -- 26 of the 27
# real G4 occurrences in Double C must remain on the normal
# four-string pool
# ---------------------------------------------------------

def test_control_most_g4_occurrences_stay_four_string():

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo40_most_g4.mscz"
    )

    try:

        staff = _staff_from(output_path)

        total_g4 = 0

        fifth_string_g4 = 0

        for note in staff.findall(".//{*}Note"):

            if note.find("{*}pitch").text == "67":

                total_g4 += 1

                if note.find("{*}string").text == "4":

                    fifth_string_g4 += 1

        assert total_g4 == 27

        assert fifth_string_g4 == 1, (
            "only the real measure-22 case should trigger BO-40 "
            "in Double C -- the mechanism must not fire "
            "indiscriminately merely because a pitch matches"
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- the real A Modal Sawmill measure 31 case -- confirms
# the mechanism generalizes to a different tuning correctly,
# not overfit to Double C
# ---------------------------------------------------------

def test_real_a_modal_sawmill_measure31_uses_fifth_string():

    output_path, applied, skipped, exceptions = _generate(
        A_MODAL_SAWMILL, "test_bo40_amodal_m31.mscz"
    )

    try:

        staff = _staff_from(output_path)

        measures = staff.findall("{*}Measure")

        m31_voice = list(measures[30].find("{*}voice"))

        a4_chord = next(
            el for el in m31_voice
            if el.tag.split("}")[-1] == "Chord"
            and el.find("{*}Note").find("{*}pitch").text == "69"
        )

        a4_note = a4_chord.find("{*}Note")

        assert a4_note.find("{*}string").text == "4"

        assert a4_note.find("{*}fret").text == "0"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 7 -- full pipeline: FD/TAB consistency and exceptions
# intact across all 3 tunings
# ---------------------------------------------------------

def test_full_pipeline_all_tunings_consistency():

    for tuning in (
        DOUBLE_C, A_MODAL_SAWMILL, get_tunings()["Double D"]
    ):

        output_path, applied, skipped, exceptions = _generate(
            tuning, f"test_bo40_full_{tuning.symbol}.mscz"
        )

        try:

            assert applied == 56

            assert skipped == 0

            assert exceptions == []

            staff = _staff_from(output_path)

            fret_diagrams = staff.findall(".//{*}FretDiagram")

            assert len(fret_diagrams) == 56

            for fd in fret_diagrams:

                assert fd.find("{*}color") is None

        finally:

            if os.path.exists(output_path):

                os.remove(output_path)
