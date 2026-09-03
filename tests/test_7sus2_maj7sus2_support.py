"""
tests/test_7sus2_maj7sus2_support.py

Focused regression test for adding "7sus2" and "maj7sus2" chord
quality support. Both are real, standard chord qualities (a
dominant 7th or major 7th chord with the 3rd replaced by the
2nd) that were previously entirely unrecognized -- confirmed
directly against a real, user-provided Gamboge score containing
D7sus2 and Gmaj7sus2 chords, which received no FD at all before
this fix, while every other chord in the same file (D, D7, A)
worked correctly.

Two separate gaps were found and fixed:
1. music.CHORD_QUALITIES had no "7sus2"/"maj7sus2" entries at
   all -- chord_tones() returned None for both.
2. Even after fixing (1), music.quality_code_to_display_name()
   still failed -- it only ever consulted
   QUALITY_CODE_TO_DISPLAY_NAME (a mapping to chord_library.py's
   own verified-CSV naming convention specifically), which has
   no entry for either quality either, since the library has no
   verified shapes for them. This caused
   _select_chord_shape_for_harmony() to hard-fail before ever
   reaching chord_service.get_shapes() -- confirmed directly
   that get_shapes() itself already, correctly generates real
   candidates with no library match at all. Fixed by falling
   back to CHORD_QUALITIES' own "display" field when no
   library-specific mapping exists.
"""

import sys

sys.path.insert(0, '.')

from music import chord_tones, quality_code_to_display_name


# ---------------------------------------------------------
# Gap 1 -- chord_tones recognizes the new qualities
# ---------------------------------------------------------

def test_7sus2_chord_tones_recognized():

    tones = chord_tones(2, '7sus2')  # D7sus2

    assert tones is not None

    # D, E, A, C (root, 2nd, 5th, flat 7th)
    assert set(tones) == {2, 4, 9, 0}


def test_maj7sus2_chord_tones_recognized():

    tones = chord_tones(7, 'maj7sus2')  # Gmaj7sus2

    assert tones is not None

    # G, A, D, F# (root, 2nd, 5th, major 7th)
    assert set(tones) == {7, 9, 2, 6}


# ---------------------------------------------------------
# Gap 2 -- quality_code_to_display_name falls back correctly
# ---------------------------------------------------------

def test_7sus2_display_name_falls_back_to_chord_qualities():

    # No chord_library.py CSV entry exists for this quality --
    # confirmed directly. Must still return a usable display
    # name via the CHORD_QUALITIES fallback, not None.
    assert quality_code_to_display_name('7sus2') == '7sus2'


def test_maj7sus2_display_name_falls_back_to_chord_qualities():

    assert quality_code_to_display_name('maj7sus2') == 'maj7sus2'


def test_existing_library_mapped_quality_unaffected():

    # A quality that DOES have a real library mapping must
    # still return that mapping, not the CHORD_QUALITIES
    # fallback -- confirms the fallback only activates when
    # genuinely needed.
    assert quality_code_to_display_name('maj7') == 'Maj 7'


def test_genuinely_unrecognized_quality_still_returns_none():

    # A quality_code recognized by neither mapping must still
    # correctly return None -- the fallback doesn't turn every
    # possible string into a valid quality.
    assert quality_code_to_display_name('not_a_real_quality') is None
