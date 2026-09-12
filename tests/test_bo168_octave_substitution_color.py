"""
tests/test_bo168_octave_substitution_color.py

Minimal focused tests for BO-168: a TAB <Note> whose actual
written pitch is a different octave of the source melody note's
own pitch (due to fretboard.py's existing, unmodified octave-
selection behavior) is marked red
(<color r="255" g="0" b="4" a="255" />).
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import (
    generate_tab_from_template, _is_octave_substituted
)

from fretboard import choose_simultaneous_positions

from chord_service import ChordService

from chord_library import ChordLibrary

import zipfile

import xml.etree.ElementTree as ET

import os

from conftest import fixture_path


def test_octave_selection_behavior_unchanged():

    # Confirms fretboard.py's existing octave-selection algorithm
    # is genuinely untouched: the real, reported source pair (63,
    # 70) in Open G still produces an octave-shifted pitch (58),
    # not the original 70.
    open_g = get_tunings()['Open G']

    open_notes = open_g.notes[1:]

    result = choose_simultaneous_positions([63, 70], open_notes)

    assert result is not None

    pitches_used = [r["pitch"] for r in result]

    assert pitches_used == [63, 58], (
        f"Expected the existing octave-selection behavior to be "
        f"unchanged -- got {pitches_used}."
    )


def test_changed_octave_is_red_in_real_generated_output():

    p = MuseScoreFile(str(fixture_path('BO-168_example_score.mscz')))

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo168_regression_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    tab_staff = root.find('.//{*}Staff[@id="1"]')

    notes = tab_staff.findall('.//{*}Note')

    colored = [
        n for n in notes if n.find('{*}color') is not None
    ]

    assert len(colored) == 3, (
        f"Expected exactly 3 red notes (the octave-substituted "
        f"Bb3/58 notes) -- got {len(colored)}."
    )

    for note in colored:

        pitch = int(note.find('{*}pitch').text)

        color = note.find('{*}color')

        assert pitch == 58, (
            f"Expected the colored note's pitch to remain the "
            f"existing, selected octave-shift result (58) -- "
            f"got {pitch}. The selected pitch/position must "
            f"never change, only its color."
        )

        assert color.get("r") == "255"

        assert color.get("g") == "0"

        assert color.get("b") == "4"

        assert color.get("a") == "255"


def test_same_pitch_as_source_not_red():

    # Same real output as above -- the D#4 (63) notes paired in
    # the same three dyads as the red Bb3 notes have the same
    # pitch as their own source note and must not be colored.
    p = MuseScoreFile(str(fixture_path('BO-168_example_score.mscz')))

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo168_regression_test_2.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    tab_staff = root.find('.//{*}Staff[@id="1"]')

    notes = tab_staff.findall('.//{*}Note')

    d_sharp_4_notes = [
        n for n in notes
        if int(n.find('{*}pitch').text) == 63
    ]

    assert len(d_sharp_4_notes) == 6

    for note in d_sharp_4_notes:

        assert note.find('{*}color') is None, (
            "Expected every D#4 (63) note to remain uncolored -- "
            "its own written pitch matches its own source pitch."
        )


def test_different_string_fret_same_pitch_not_red():

    # Unit-level: _is_octave_substituted() only ever receives
    # pitches, never string/fret -- confirming a different
    # string/fret producing the identical pitch cannot possibly
    # be flagged by this mechanism, regardless of position.
    assert _is_octave_substituted(60, 60) is False

    assert _is_octave_substituted(65, 65) is False
