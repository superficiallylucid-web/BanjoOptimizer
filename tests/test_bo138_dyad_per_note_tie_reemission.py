"""
tests/test_bo138_dyad_per_note_tie_reemission.py

Focused test for BO-138: both notes of a tied dyad get their own,
independent tie Spanner re-emitted in the output, not just the
first (pitch_index 0) one.

Root cause: BO-133.5's own dyad-writing block only ever re-emitted
tie_elements (a flat, non-per-note list) for pitch_index 0 --
already documented as a known limitation in that BO's own report.
The real Gamboge dyad (A3 + F#4, both independently tied) exposed
this directly once BO-137.3 made both notes' TAB positions agree:
the A3 tie rendered, the F# tie silently did not.

Fixed via a new, per-note-parallel list (tie_elements_by_note_index,
built alongside all_pitches during the same, existing Note-parsing
loop) so each note in the dyad gets its own, correct Tie Spanner(s),
independent of the other.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import generate_tab_from_template

from chord_service import ChordService

from chord_library import ChordLibrary

import zipfile

import xml.etree.ElementTree as ET

import os


def _load_gamboge():

    p = MuseScoreFile('scores/Gamboge (treble).mscz')

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p, staff_used


def test_both_dyad_notes_get_own_tie_reemitted():

    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo138_test_output.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    measures = root.findall('.//{*}Measure')

    # m1 (index 0) -- the tie-start dyad; m2 (index 1) -- its
    # own continuation. Filter by tie presence specifically,
    # since pitch 57 also occurs earlier and untied within m1.
    m1_notes = []

    for chord in measures[0].findall('.//{*}Chord'):

        for note in chord.findall('{*}Note'):

            pitch_el = note.find('{*}pitch')

            if (
                pitch_el is not None
                and pitch_el.text in ('57', '54')
                and note.find('{*}Spanner') is not None
            ):

                m1_notes.append(note)

    m2_notes = []

    for chord in measures[1].findall('.//{*}Chord'):

        for note in chord.findall('{*}Note'):

            pitch_el = note.find('{*}pitch')

            if (
                pitch_el is not None
                and pitch_el.text in ('57', '54')
                and note.find('{*}Spanner') is not None
            ):

                m2_notes.append(note)

    assert len(m1_notes) == 2 and len(m2_notes) == 2

    for note in m1_notes + m2_notes:

        pitch_text = note.find('{*}pitch').text

        tie_spanner = note.find('{*}Spanner')

        assert tie_spanner is not None, (
            f"Expected pitch {pitch_text} to have its own tie "
            f"Spanner re-emitted -- both notes of a dyad must "
            f"be tied independently, not just the first."
        )


def test_single_note_tie_unaffected():

    # Real, single-note tie (m7->m8, pitch 62) -- must still
    # work exactly as before this fix.
    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo138_test_single.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    measures = root.findall('.//{*}Measure')

    m7_note = None

    for chord in measures[6].findall('.//{*}Chord'):

        for note in chord.findall('{*}Note'):

            pitch_el = note.find('{*}pitch')

            if pitch_el is not None and pitch_el.text == '62':

                m7_note = note

    assert m7_note is not None

    tie_spanner = m7_note.find('{*}Spanner')

    assert tie_spanner is not None
