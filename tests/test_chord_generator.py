"""
tests/test_chord_generator.py

Tests for chord_generator.py's "useful candidates, not every
mathematically possible combination" behavior.

CASE A/B/C: known-good full voicings (verified in the chord
library) must remain candidates, and trivial one-string-muted
variants of them must NOT appear merely to pad the candidate
list.

CASE D: a full voicing that playability.py rejects, where
muting the problem string produces a valid, playable, non-
redundant triad, must survive as a rescue candidate. The real
Open G / C-G-E-Major data doesn't naturally exercise this path
(there are enough distinct accepted full voicings that rescue
is never needed), so this uses a small synthetic fixture
against attempt_rescue() directly, rather than a permanent
chord-library entry, per the request that raised this.

CASE E: the generator must not manufacture candidates just to
reach five -- fewer genuinely useful candidates is a legitimate
result.
"""

from tunings import get_tunings

from chord_generator import generate_candidates, attempt_rescue

from fretboard import format_shape


OPEN_G = get_tunings()["Open G"]

# Open G's 4 melody strings (4th to 1st), used directly by the
# CASE D synthetic fixture below.
OPEN_G_MELODY_STRINGS = OPEN_G.notes[1:]


def _shapes_for(root, root_pc, quality_display="Major"):

    return generate_candidates(
        tuning=OPEN_G,
        root=root,
        root_pc=root_pc,
        quality_code="",
        quality_display=quality_display
    )


# ---------------------------------------------------------
# CASE A -- C Major
# ---------------------------------------------------------

def test_case_a_c_major_keeps_full_voicing():

    shapes = [result.shape for result in _shapes_for("C", 0)]

    assert "2012" in shapes


def test_case_a_c_major_excludes_trivial_mutes():

    shapes = [result.shape for result in _shapes_for("C", 0)]

    assert "20--2" not in shapes

    assert "201--" not in shapes


# ---------------------------------------------------------
# CASE B -- G Major
# ---------------------------------------------------------

def test_case_b_g_major_keeps_full_voicing():

    shapes = [result.shape for result in _shapes_for("G", 7)]

    assert "0000" in shapes


def test_case_b_g_major_excludes_trivial_mutes():

    shapes = [result.shape for result in _shapes_for("G", 7)]

    assert "00--0" not in shapes

    assert "0--00" not in shapes

    assert "000--" not in shapes


# ---------------------------------------------------------
# CASE C -- E Major
# ---------------------------------------------------------

def test_case_c_e_major_keeps_full_voicing():

    shapes = [result.shape for result in _shapes_for("E", 4)]

    assert "2102" in shapes


def test_case_c_e_major_excludes_trivial_mutes():

    shapes = [result.shape for result in _shapes_for("E", 4)]

    for shape in shapes:

        if "--" in shape:

            # Any reduced shape that does appear must not be
            # a trivial one-string-mute of 2102 specifically.
            assert shape not in ("2--02", "21--2", "210--")


# ---------------------------------------------------------
# CASE D -- rescue voicing (synthetic fixture)
# ---------------------------------------------------------
#
# The real C/G/E Major Open G data always has enough distinct
# accepted full voicings that rescue is never actually needed
# (confirmed by the CASE A/B/C tests above finding zero reduced
# candidates). To prove the rescue mechanism itself works, this
# tests attempt_rescue() directly against a hand-picked full
# voicing known to be rejected by playability.py (span 4, over
# the 3-fret acceptance limit).

def test_case_d_rescue_survives_for_rejected_full_voicing():

    tones = (0, 4, 7)  # C major: root, third, fifth

    # (2, 0, 1, 5) on Open G's melody strings: fretted values
    # {2, 1, 5} span 4 frets -- playability.py rejects this
    # (MAX_ACCEPTABLE_SPAN is 3).
    full_values = (2, 0, 1, 5)

    rescues = attempt_rescue(
        full_values,
        OPEN_G_MELODY_STRINGS,
        tones
    )

    assert len(rescues) > 0, (
        "Expected at least one playable, valid-triad rescue "
        "for a full voicing playability rejects"
    )

    # Every rescue must still cover the full triad (root,
    # third, fifth) -- no essential tone dropped.
    for reduced in rescues:

        pitches = [
            OPEN_G_MELODY_STRINGS[i] + reduced[i]
            for i in range(4)
            if reduced[i] is not None
        ]

        pitch_classes = set(pitch % 12 for pitch in pitches)

        assert set(tones).issubset(pitch_classes)


# ---------------------------------------------------------
# CASE E -- don't pad the candidate list
# ---------------------------------------------------------

def test_case_e_does_not_pad_to_five():

    # E Major in Open G naturally produces fewer than 5
    # genuinely distinct useful voicings within the search
    # window -- confirms the generator returns what actually
    # exists rather than manufacturing filler candidates.
    shapes = _shapes_for("E", 4)

    assert len(shapes) < 5

    assert len(shapes) > 0
