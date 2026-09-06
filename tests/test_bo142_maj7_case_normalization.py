"""
tests/test_bo142_maj7_case_normalization.py

Focused regression test for BO-142: a case-variant "maj" prefix
(e.g. "Maj7", "MAJ7") is now recognized as equivalent to the
already-established lowercase "maj7" quality code, fixing a
real, confirmed silent failure -- the real, user-supplied
Alizarin.mscz uses "Maj7" (capital M) in its own raw MuseScore
data, which previously produced tones=[] and shape=None for
every occurrence.

Deliberately narrow: only the literal "maj" prefix (3 letters,
any case) is folded -- never a bare "m" alone, since that would
dangerously collide with the existing, genuinely different "m7"
(minor 7th) quality. Confirmed real musical convention (not just
a technical choice): a capital M explicitly distinguishes major
from minor in standard chord-symbol notation, and this project's
own fix preserves that distinction exactly, rather than
case-folding everything indiscriminately.
"""

import sys

sys.path.insert(0, '.')

from parser import normalize_quality_code

from music import chord_tones


# ---------------------------------------------------------
# 1 -- the real, reported case
# ---------------------------------------------------------

def test_maj7_case_variants_normalize_to_lowercase():

    assert normalize_quality_code('Maj7') == 'maj7'

    assert normalize_quality_code('MAJ7') == 'maj7'

    assert normalize_quality_code('maj7') == 'maj7'


def test_normalized_maj7_produces_correct_chord_tones():

    normalized = normalize_quality_code('Maj7')

    tones = chord_tones(7, normalized)

    assert tones == [7, 11, 2, 6], (
        f"Expected Gmaj7's own correct tones, got {tones}."
    )


# ---------------------------------------------------------
# 2 -- critical safety: bare "m"/"M" must NEVER be touched,
# and must NEVER collide with the "maj" family
# ---------------------------------------------------------

def test_bare_minor_code_is_never_touched():

    assert normalize_quality_code('m') == 'm'

    assert normalize_quality_code('m7') == 'm7'

    assert normalize_quality_code('mb5') == 'mb5'


def test_bare_capital_m_alone_does_not_collide_with_minor():

    # "M" alone, or "M7" (no "aj"), must NOT fold to anything at
    # all -- confirmed directly: neither is a real, defined
    # quality either before or after this fix, and "M7" must
    # never be silently treated as "m7" (minor 7th), which would
    # be a genuine musical error, not merely a technical one.
    assert normalize_quality_code('M') == 'M'

    assert normalize_quality_code('M7') == 'M7'

    assert chord_tones(7, normalize_quality_code('M7')) is None, (
        "Expected 'M7' to remain unrecognized, never silently "
        "matched to the existing, different 'm7' (minor) "
        "quality."
    )


def test_minor_seventh_chord_tones_unaffected():

    # Direct confirmation the minor 7th quality itself produces
    # its own, correct, DIFFERENT tones -- unaffected by this
    # fix in any way.
    tones = chord_tones(9, normalize_quality_code('m7'))

    assert tones == [9, 0, 4, 7]


# ---------------------------------------------------------
# 3 -- existing (no5) behavior is preserved unchanged
# ---------------------------------------------------------

def test_no5_suffix_stripping_still_works():

    assert normalize_quality_code('7(no5)') == '7'

    assert normalize_quality_code('m(no5)') == 'm'


# ---------------------------------------------------------
# 4 -- only the leading "maj" token itself is touched; any
# suffix is left exactly as given (deliberately narrow scope,
# not a general case-insensitive system)
# ---------------------------------------------------------

def test_only_leading_maj_prefix_is_folded():

    # Confirmed real, current behavior: the suffix itself is
    # NOT separately case-normalized -- this fix's own,
    # deliberately narrow scope is limited to the exact,
    # reported "maj" prefix case only.
    assert normalize_quality_code('MAJ7SUS2') == 'maj7SUS2'
