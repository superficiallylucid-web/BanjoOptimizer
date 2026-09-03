"""
tests/test_7sus4_maj7sus4_support.py

Focused regression test for adding "7sus4" and "maj7sus4" chord
quality support, following the exact same pattern as
test_7sus2_maj7sus2_support.py -- both are real, standard chord
qualities (a dominant 7th or major 7th chord with the 3rd
replaced by the 4th) that were previously entirely unrecognized.

Only chord_tones() needed a new entry this time -- the
quality_code_to_display_name() fallback added for the 7sus2/
maj7sus2 fix is generic (falls back to CHORD_QUALITIES' own
"display" field for any quality_code with no library-specific
mapping), so it already, correctly handles these two new
qualities with no further change.
"""

import sys

sys.path.insert(0, '.')

from music import chord_tones, quality_code_to_display_name


# ---------------------------------------------------------
# chord_tones recognizes the new qualities
# ---------------------------------------------------------

def test_7sus4_chord_tones_recognized():

    tones = chord_tones(2, '7sus4')  # D7sus4

    assert tones is not None

    # D, G, A, C (root, 4th, 5th, flat 7th)
    assert set(tones) == {2, 7, 9, 0}


def test_maj7sus4_chord_tones_recognized():

    tones = chord_tones(7, 'maj7sus4')  # Gmaj7sus4

    assert tones is not None

    # G, C, D, F# (root, 4th, 5th, major 7th)
    assert set(tones) == {7, 0, 2, 6}


# ---------------------------------------------------------
# quality_code_to_display_name falls back correctly, with no
# additional change needed beyond the generic fallback already
# in place
# ---------------------------------------------------------

def test_7sus4_display_name_falls_back_to_chord_qualities():

    assert quality_code_to_display_name('7sus4') == '7sus4'


def test_maj7sus4_display_name_falls_back_to_chord_qualities():

    assert quality_code_to_display_name('maj7sus4') == 'maj7sus4'
