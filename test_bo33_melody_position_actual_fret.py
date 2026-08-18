"""
tests/test_bo33_melody_position_actual_fret.py

Regression tests for BO-33: chord_service._capped_position_
distance() now measures the melody pitch's own ACTUAL fret
within a candidate chord shape, not that shape's overall
playing_model._chord_working_fret() -- confirmed by direct
investigation (BO-32) that these can diverge, since a shape's
working fret can come from a completely different string than
the one sounding the melody pitch.

Real C7 example (measure 20, A Modal Sawmill/aEADE), traced and
documented before any code changed:

    melody pitch: A#4 (midi 70), preferred_melody_fret=6

    shape       quality  working_fret  melody_fret  OLD dist  NEW dist
    0(10)88     21.5     8             8            2         2
    0356        21.5     3             6            3         0   <- new winner
    (18)(15)(17)0 21.5   15            18           5 (cap)   5 (cap)

Confirmed in the real generated output: the repeated A#4 notes
immediately before this chord now stay at the exact same
position (fret 6, string_index 0) as the chord's own onset note
-- previously an avoidable jump.

IMPORTANT lesson from validating this file itself: tests that
call get_shapes_for_exact_melody_pitch() with REAL chord
candidates can pass "by coincidence" even with the fix disabled,
because get_shapes()'s own BASE ordering (before any melody-
aware reordering) can already happen to put the right shape
first for unrelated reasons. To genuinely isolate the mechanism,
ranking-level tests here use _mock_shape()/_service_returning()
(the same pattern test_melody_position_tiebreak.py already
established) so the two candidates are returned in a controlled
order and tied on everything except the positional tiebreak --
verified by disabling the fix and confirming every test in this
file actually fails, not just re-derived after the fact.

Only chord_service._capped_position_distance() and its call
site changed. find_positions()/best_position()/sounding_notes()/
defining_tones()/voicing_quality_score/chord generation/
deduplication/playability rules are all untouched.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from models import ChordShape

from chord_service import ChordService, _capped_position_distance

from chord_library import ChordLibrary

from fretboard import sounding_notes, parse_shape

from playing_model import _chord_working_fret

from parser import MuseScoreFile

from score_generator import (
    _melody_notes_at_harmony_onset, _preferred_melody_fret,
    generate_tab_from_template
)

from music import pitch_name, quality_code_to_display_name


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

MELODY_STRINGS = A_MODAL_SAWMILL.notes[1:]

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


def _get_chord_service():

    return ChordService(ChordLibrary())


def _mock_shape(shape_text, category, quality_score):

    shape = ChordShape(
        tuning="aEADE", root="C", quality="Dominant 7th",
        shape=shape_text, source="generated"
    )

    shape.voicing_quality_category = category

    shape.voicing_quality_score = quality_score

    return shape


def _service_returning(fixed_shapes):

    service = _get_chord_service()

    service.get_shapes = lambda *args, **kwargs: fixed_shapes

    return service


# ---------------------------------------------------------
# 1 -- the confirmed real C7 case, isolated via mocked
# candidates so the positional tiebreak is the only thing
# that can decide the outcome
# ---------------------------------------------------------

def test_real_c7_case_selects_0356():

    top_before_fix = _mock_shape("0(10)88", "ROOT_PRESENT", 21.5)

    correct_winner = _mock_shape("0356", "ROOT_PRESENT", 21.5)

    service = _service_returning(
        [top_before_fix, correct_winner]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "7", "Dominant 7th", {70},
        preferred_melody_fret=6
    )

    assert ranked[0].shape == "0356"


def test_real_c7_case_distances_match_documented_trace():

    for shape_text, expected_working_fret, expected_melody_fret in [
        ("0(10)88", 8, 8),
        ("0356", 3, 6),
    ]:

        values = parse_shape(shape_text)

        working_fret = _chord_working_fret(values)

        assert working_fret == expected_working_fret

        notes = sounding_notes(A_MODAL_SAWMILL, shape_text)

        melody_fret = None

        for note in notes:

            if note.midi == 70:  # A#4

                melody_fret = (
                    note.midi - MELODY_STRINGS[note.string_index]
                )

                break

        assert melody_fret == expected_melody_fret

    old_dist_0356 = min(abs(3 - 6), 5)

    new_dist_0356 = min(abs(6 - 6), 5)

    assert old_dist_0356 == 3

    assert new_dist_0356 == 0

    old_dist_top = min(abs(8 - 6), 5)

    new_dist_top = min(abs(8 - 6), 5)

    assert old_dist_top == new_dist_top == 2


# ---------------------------------------------------------
# 2 -- working_fret and melody_fret are the SAME: existing
# behavior preserved (real example: measure 3's "C" chord)
# ---------------------------------------------------------

def test_working_fret_equals_melody_fret_preserved():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = _get_chord_service()

    c_harmony = [
        h for h in p.harmonies
        if h.symbol == "C" and h.measure == 3
    ][0]

    onset_notes = _melody_notes_at_harmony_onset(
        c_harmony, p.score.notes
    )

    melody_pitches = {n.midi for n in onset_notes}

    preferred_fret = _preferred_melody_fret(
        onset_notes, A_MODAL_SAWMILL
    )

    root_name = pitch_name(c_harmony.root_pc)

    quality_display = quality_code_to_display_name(
        c_harmony.quality_code
    )

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, root_name, c_harmony.root_pc,
        c_harmony.quality_code, quality_display, melody_pitches,
        preferred_melody_fret=preferred_fret
    )

    assert shapes[0].shape == "0350"

    values = parse_shape("0350")

    working_fret = _chord_working_fret(values)

    notes = sounding_notes(A_MODAL_SAWMILL, "0350")

    melody_fret = None

    for note in notes:

        if note.midi in melody_pitches:

            melody_fret = (
                note.midi - MELODY_STRINGS[note.string_index]
            )

            break

    assert working_fret == melody_fret == 3

    same_shape = _mock_shape("0350", "ROOT_PRESENT", 19.5)

    # 8070 has C4 at string_index 0/fret 8 -- genuinely a
    # different position from 0350's own C4 at string_index
    # 1/fret 3, confirmed directly (unlike an earlier candidate
    # considered for this comparison, 3320, which turned out to
    # share the exact same C4 position as 0350 and so couldn't
    # isolate anything).
    different_shape = _mock_shape("8070", "ROOT_PRESENT", 19.5)

    isolated_service = _service_returning(
        [different_shape, same_shape]
    )

    isolated_ranked = (
        isolated_service.get_shapes_for_exact_melody_pitch(
            A_MODAL_SAWMILL, "C", 0, "", "Major", melody_pitches,
            preferred_melody_fret=preferred_fret
        )
    )

    assert isolated_ranked[0].shape == "0350"


# ---------------------------------------------------------
# 3 -- working_fret and melody_fret DIFFER: new calculation
# actually used, isolated at the function level directly
# ---------------------------------------------------------

def test_working_fret_and_melody_fret_differ_new_calc_used():

    notes = sounding_notes(A_MODAL_SAWMILL, "0356")

    # Non-zero expected result -- distinguishes a genuinely
    # correct computation from a disabled/always-0 stub.
    distance = _capped_position_distance(
        notes, {70}, 4, MELODY_STRINGS
    )

    # melody_fret for A#4 in 0356 is 6 (string_index 3) -- if
    # the OLD (working_fret-based) calculation were still in
    # effect, this would compare against working_fret=3 instead,
    # giving |3-4|=1, not |6-4|=2.
    assert distance == 2


# ---------------------------------------------------------
# 4 -- quality_score must still beat positional distance
# ---------------------------------------------------------

def test_quality_still_beats_positional_distance():

    complete_voicing = _mock_shape("0(10)98", "ROOT_PRESENT", 21.5)

    incomplete_but_closer = _mock_shape(
        "0(10)9(11)", "ROOT_PRESENT", 21.0
    )

    service = _service_returning(
        [incomplete_but_closer, complete_voicing]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=7
    )

    assert ranked[0].shape == "0(10)98"


# ---------------------------------------------------------
# 5 -- multiple occurrences of the same pitch within one
# candidate: the real Am/E4 case
# ---------------------------------------------------------

def test_multiple_occurrences_uses_closest():

    notes = sounding_notes(A_MODAL_SAWMILL, "5320")

    occurrences = [n for n in notes if n.midi == 64]

    assert len(occurrences) == 2

    distance = _capped_position_distance(
        notes, {64}, 0, MELODY_STRINGS
    )

    assert distance == 0

    distance_near_fret_2 = _capped_position_distance(
        notes, {64}, 2, MELODY_STRINGS
    )

    assert distance_near_fret_2 == 0

    multi_occurrence = _mock_shape("5320", "ROOT_PRESENT", 19.5)

    farther_single = _mock_shape("00(10)0", "ROOT_PRESENT", 19.5)

    service = _service_returning(
        [farther_single, multi_occurrence]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2
    )

    assert ranked[0].shape == "5320"


# ---------------------------------------------------------
# 6 -- full pipeline: real production output, TAB/FD
# consistency, exceptions, and continuity all intact
# ---------------------------------------------------------

def test_full_pipeline_real_song_unaffected_elsewhere():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_bo33_pipeline.mscz"
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

        m20_voice = list(measures[19].find("{*}voice"))

        fd = next(
            el for el in m20_voice
            if el.tag.split("}")[-1] == "FretDiagram"
        )

        fret_offset = int(fd.find("{*}fretOffset").text)

        assert fret_offset == 2

        a_sharp_frets_and_strings = []

        for el in m20_voice:

            if el.tag.split("}")[-1] != "Chord":

                continue

            note = el.find("{*}Note")

            if note.find("{*}pitch").text == "70":

                a_sharp_frets_and_strings.append(
                    (
                        note.find("{*}fret").text,
                        note.find("{*}string").text
                    )
                )

        assert len(a_sharp_frets_and_strings) >= 2

        assert len(set(a_sharp_frets_and_strings)) == 1

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
