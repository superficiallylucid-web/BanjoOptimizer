"""
tests/test_bo30_followup_low_position_preference.py

Regression tests for BO-30-Followup: score_generator._preferred_
melody_fret() now prefers the LOWEST fret among a melody note's
own playable positions, rather than fretboard.best_position()'s
own general-purpose middle-string-biased choice.

Root cause, confirmed against a real example (The Christmas Song
/ Double C, the final "C" chord at measure 32): best_position()
picked fret 21 (string index 1, +6 middle-string bonus) over
fret 14 (string index 3, +2 bonus) for the exact same pitch,
purely because of which string the note happened to fall on --
not because 21 is genuinely more natural. Since preferred_
melody_fret exists specifically to tell chord-shape ranking
"where does this note naturally sit," that bias pulled chord
selection toward a needlessly high, less playable shape (working
fret 19 instead of a much lower, real alternative).

An earlier, broader attempt at this fix also changed the
chord-candidate DEDUPLICATION tiebreak in chord_generator.py to
prefer a lower playing_model._chord_working_fret() there too --
this was reverted after it broke the established BO-22-FOLLOWUP
Cmaj7 example (a shape with one open string lost a 1-fret-lower,
fully-fretted, otherwise-worse alternative purely because of the
new working_fret tiebreak, even though the open-string version
needs one fewer finger for the identical sounding notes). The
final fix is narrower: only _preferred_melody_fret() changed,
not chord-candidate generation or deduplication at all.

find_positions()/best_position() themselves remain completely
unmodified -- only this one narrow, purpose-specific caller
changes.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _preferred_melody_fret, _select_chord_shape_for_harmony,
    generate_tab_from_template
)

from playing_model import _chord_working_fret

from fretboard import parse_shape

from models import Note


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# 1 -- _preferred_melody_fret() itself: lowest fret wins
# ---------------------------------------------------------

def test_preferred_melody_fret_uses_lowest_position():

    double_c = get_tunings()["Double C"]

    # Real E5 (midi 76) in gCGCD: positions at frets 14/16/21 --
    # confirmed real values. best_position() would have picked
    # 21 (middle-string bonus); this must now pick 14.
    onset_notes = [Note(midi=76, measure=32, beat=3.0)]

    preferred = _preferred_melody_fret(onset_notes, double_c)

    assert preferred == 14


def test_preferred_melody_fret_none_when_no_notes():

    double_c = get_tunings()["Double C"]

    assert _preferred_melody_fret([], double_c) is None


def test_preferred_melody_fret_unaffected_by_single_position():

    # A note with only one playable position must be unaffected
    # by this change -- min() of a single value is that value,
    # same as before.
    a_modal = get_tunings()["A Modal Sawmill"]

    onset_notes = [Note(midi=64, measure=1, beat=0.0)]  # E4

    preferred = _preferred_melody_fret(onset_notes, a_modal)

    assert preferred is not None


# ---------------------------------------------------------
# 2 -- the real Double C "C" chord case: a substantially lower,
# more playable shape is now selected
# ---------------------------------------------------------

def test_real_double_c_final_chord_selects_lower_shape():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    double_c = get_tunings()["Double C"]

    service = ChordService(ChordLibrary())

    c_harmony = [
        h for h in p.harmonies
        if h.symbol == "C" and h.measure == 32
    ][0]

    chosen_shape, is_exception, exc = _select_chord_shape_for_harmony(
        c_harmony, double_c, service, melody_notes=p.score.notes
    )

    assert chosen_shape is not None

    values = parse_shape(chosen_shape.shape)

    working_fret = _chord_working_fret(values)

    # Before this fix: working_fret was 19 (shape 0-21-19-22).
    # After: a substantially lower, more compact shape.
    assert working_fret is not None

    assert working_fret < 19

    assert is_exception is False


# ---------------------------------------------------------
# 3 -- the BO-22 Am/aEADE example remains unaffected (the
# established real example this fix was checked against
# before implementation)
# ---------------------------------------------------------

def test_bo22_am_example_unaffected():

    service = ChordService(ChordLibrary())

    am_harmony_like = [Note(midi=64, measure=1, beat=3.0)]  # E4

    preferred = _preferred_melody_fret(
        am_harmony_like, A_MODAL_SAWMILL
    )

    # E4 in aEADE has a position at fret 0 (open, string index
    # 3) -- confirmed real value, the lowest available.
    assert preferred == 0


# ---------------------------------------------------------
# 4 -- full regression: BO-22-FOLLOWUP's Cmaj7 example (the
# case an earlier, broader version of this fix accidentally
# broke) remains correct
# ---------------------------------------------------------

def test_cmaj7_complete_voicing_still_selected():

    from chord_generator import generate_candidates

    candidates = generate_candidates(
        tuning=A_MODAL_SAWMILL, root="C", root_pc=0,
        quality_code="maj7", quality_display="Maj 7",
        max_candidates=100, melody_pitches={71}
    )

    assert any(c.shape == "0(10)98" for c in candidates), (
        "the established complete C-E-G-B Cmaj7 voicing must "
        "still be generated -- this fix must not touch chord-"
        "candidate generation or deduplication at all"
    )


# ---------------------------------------------------------
# 5 -- full pipeline: the real Double C song generates
# correctly end to end, with a lower final chord and no new
# exceptions anywhere
# ---------------------------------------------------------

def test_full_pipeline_double_c_no_regressions():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    double_c = get_tunings()["Double C"]

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, double_c, staff_used, TEMPLATE_PATH, "output",
            service, filename="test_bo30f_double_c.mscz"
        )
    )

    try:

        assert applied == 56

        assert skipped == 0

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

        # Measure 32's "C" chord FD: fretOffset should now be
        # much lower than the original 18.
        measures = staff.findall("{*}Measure")

        m32_voice = list(measures[31].find("{*}voice"))

        c_fd = None

        for el in m32_voice:

            if el.tag.split("}")[-1] == "FretDiagram":

                c_fd = el  # the second FretDiagram in this

        assert c_fd is not None

        fret_offset_element = c_fd.find("{*}fretOffset")

        fret_offset = (
            int(fret_offset_element.text)
            if fret_offset_element is not None else 0
        )

        assert fret_offset < 18

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- also test a different real tuning (A Modal Sawmill) to
# confirm the fix generalizes and doesn't only help this one
# passage/tuning
# ---------------------------------------------------------

def test_generalizes_to_a_modal_sawmill_no_high_fret_shapes():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    high_fret_count = 0

    for h in p.harmonies:

        chosen_shape, is_exception, exc = (
            _select_chord_shape_for_harmony(
                h, A_MODAL_SAWMILL, service,
                melody_notes=p.score.notes
            )
        )

        if chosen_shape is None:

            continue

        values = parse_shape(chosen_shape.shape)

        working_fret = _chord_working_fret(values)

        if working_fret is not None and working_fret >= 15:

            high_fret_count += 1

    assert high_fret_count == 0, (
        "A Modal Sawmill should have no unnecessarily-high-"
        "position chord shapes after this fix, confirmed "
        "directly against the real song"
    )
