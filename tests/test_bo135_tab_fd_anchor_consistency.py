"""
tests/test_bo135_tab_fd_anchor_consistency.py

Focused tests for BO-135: multi-note melody TAB positions reuse
the already-selected chord shape (FD) at the same onset when it
genuinely covers both pitches, instead of independently searching
for a possibly-different compact voicing.

Root cause confirmed directly (BO-135's own investigation
report): fretboard.choose_simultaneous_positions() previously
never received the already-computed FD anchor
(fd_anchor_by_event_id), even though the neighboring single-note
_choose_melody_position() call already did. The information
needed to make TAB and FD agree already existed in memory at the
exact point of the call; it simply wasn't being passed through.
"""

import sys

sys.path.insert(0, '.')

from fretboard import choose_simultaneous_positions, parse_shape

from tunings import get_tunings

from parser import MuseScoreFile

from score_generator import generate_tab_from_template

from chord_service import ChordService

from chord_library import ChordLibrary

import zipfile

import xml.etree.ElementTree as ET

import os


# ---------------------------------------------------------
# 1 -- real Gamboge case, full pipeline
# ---------------------------------------------------------

def test_real_gamboge_tab_matches_fd():

    p = MuseScoreFile('scores/Gamboge.mscz')

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo135_test_output.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    first_measure = root.find('.//{*}Measure')

    first_fd = first_measure.find('.//{*}FretDiagram')

    first_chord = first_measure.find('.//{*}Chord')

    # Real, confirmed FD: fretOffset=4, strings 0/1 fretted at
    # relative fret 1 (absolute 5), strings 2/3 open -- i.e.
    # "5500" in BO-internal order.
    offset = int(first_fd.find('{*}fretOffset').text)

    assert offset == 4

    # Real TAB: both notes must now land on the SAME absolute
    # fret (5) the FD itself represents, not an independently
    # -chosen, different compact voicing.
    note_elements = first_chord.findall('{*}Note')

    assert len(note_elements) == 2

    frets = {
        int(note.find('{*}fret').text) for note in note_elements
    }

    assert frets == {5}, (
        f"Expected both TAB notes at fret 5, matching the "
        f"already-selected FD shape '5500', got frets {frets}."
    )


# ---------------------------------------------------------
# 2 -- direct unit test of the anchor-matching helper
# ---------------------------------------------------------

def test_anchor_used_when_it_covers_both_pitches():

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    anchor_values = parse_shape('5500')

    # Real, original source pitches (57, 74) -- NOT the octave-
    # shifted 62 the anchor itself sounds. The match must still
    # succeed via pitch-class comparison.
    result = choose_simultaneous_positions(
        [57, 74], open_notes, fd_anchor_shape_values=anchor_values
    )

    assert result is not None

    assert {r["fret"] for r in result} == {5}

    # The returned "pitch" reflects the anchor's own actual
    # sounding pitch (62), not the original 74 passed in -- the
    # TAB must represent the same voicing the FD does.
    assert {r["pitch"] for r in result} == {57, 62}


# ---------------------------------------------------------
# 3 -- fallback when the anchor doesn't cover both pitches
# ---------------------------------------------------------

def test_falls_back_when_anchor_does_not_cover_both_pitches():

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    # A shape that doesn't sound either of these two pitches at
    # all (a simple open-G-style shape, no D or A content).
    anchor_values = parse_shape('2000')

    result_with_anchor = choose_simultaneous_positions(
        [57, 74], open_notes, fd_anchor_shape_values=anchor_values
    )

    result_without_anchor = choose_simultaneous_positions(
        [57, 74], open_notes
    )

    assert result_with_anchor == result_without_anchor, (
        "Expected an anchor that doesn't cover both pitches to "
        "fall back to the exact same result as no anchor at "
        "all."
    )


# ---------------------------------------------------------
# 4 -- no anchor at all -- existing behavior fully preserved
# ---------------------------------------------------------

def test_no_anchor_argument_unaffected():

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    # Confirmed real, pre-BO-135 result for this exact pair.
    result = choose_simultaneous_positions([60, 64], open_notes)

    assert result is not None

    pitches_used = [r["pitch"] for r in result]

    assert pitches_used == [60, 64]
