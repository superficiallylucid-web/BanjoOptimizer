"""
tests/test_fret_diagram_parsing.py

Tests for read_harmonies()'s new FretDiagram capture
(Harmony.shape) -- ground-truth fingerings read directly from
a score's own <FretDiagram> data.

Uses the real My Favorite Things (aEADE) file. Skips gracefully
if that file isn't present locally, matching the pattern
already used for other real-data checks in this project (the
file was uploaded to chat, not committed to the tracked
scores/ folder).
"""

from pathlib import Path

from parser import MuseScoreFile


MFT_PATH = (
    Path(__file__).parent.parent
    / "My_Favorite_Things__Em__aEADE__.mscz"
)


def _load_mft():

    if not MFT_PATH.exists():

        return None

    p = MuseScoreFile(MFT_PATH)

    p.open()
    p.read_melody_notes()
    p.read_harmonies(4)

    return p


def _harmony_at(score, measure, symbol):

    for h in score.harmonies:

        if h.measure == measure and h.symbol == symbol:

            return h

    return None


# ---------------------------------------------------------
# The known real examples, decoded correctly
# ---------------------------------------------------------

def test_known_examples_decode_correctly():

    p = _load_mft()

    if p is None:

        print(
            "SKIPPED: My_Favorite_Things__Em__aEADE__.mscz "
            "not found locally"
        )

        return

    expected = {
        (9, "Em"): "0220",
        (31, "Em"): "0220",
        # Was "2314" before fretOffset support was added --
        # confirmed wrong: that reading didn't even spell a
        # valid B7 (missing the root and 7th, containing notes
        # that aren't B7 tones at all). "5647" is B-D#-F#-A,
        # the complete, correct chord.
        (38, "B7"): "5647",
        (49, "Em"): "0220",
        (59, "A7"): "3425",
        (72, "Em"): "0223",
    }

    for (measure, symbol), expected_shape in expected.items():

        harmony = _harmony_at(p.score, measure, symbol)

        assert harmony is not None, (
            f"expected a {symbol} at measure {measure}"
        )

        assert harmony.shape == expected_shape, (
            f"m{measure} {symbol}: expected shape "
            f"{expected_shape!r}, got {harmony.shape!r}"
        )


# ---------------------------------------------------------
# The same chord symbol can have different shapes at
# different occurrences -- "Em" is 0220 in most places but
# 0223 at measure 72
# ---------------------------------------------------------

def test_same_symbol_different_shapes():

    p = _load_mft()

    if p is None:

        print(
            "SKIPPED: My_Favorite_Things__Em__aEADE__.mscz "
            "not found locally"
        )

        return

    em_shapes = {
        h.shape for h in p.score.harmonies
        if h.symbol == "Em" and h.shape
    }

    assert "0220" in em_shapes

    assert "0223" in em_shapes

    assert len(em_shapes) > 1, (
        "expected more than one distinct shape across all Em "
        "occurrences -- same chord symbol, different actual "
        "fingering"
    )


# ---------------------------------------------------------
# The bidirectional-ordering fix: a FretDiagram appearing
# BEFORE its Harmony (confirmed real case, measure 38) must
# still be paired correctly, not silently dropped
# ---------------------------------------------------------

def test_fret_diagram_before_harmony_still_pairs_correctly():

    p = _load_mft()

    if p is None:

        print(
            "SKIPPED: My_Favorite_Things__Em__aEADE__.mscz "
            "not found locally"
        )

        return

    # Measure 38's B7 is the confirmed real case where
    # <FretDiagram> precedes <Harmony> in the raw XML -- if
    # pairing only handled the usual (Harmony-then-diagram)
    # order, this would come back empty.
    harmony = _harmony_at(p.score, 38, "B7")

    assert harmony is not None

    assert harmony.shape == "5647"


# ---------------------------------------------------------
# Most chord symbols in this particular file DO have a shape
# attached (confirmed: 62/62) -- a coverage sanity check,
# not an assumption about every score
# ---------------------------------------------------------

def test_shape_coverage_for_this_file():

    p = _load_mft()

    if p is None:

        print(
            "SKIPPED: My_Favorite_Things__Em__aEADE__.mscz "
            "not found locally"
        )

        return

    total = len(p.score.harmonies)

    with_shape = sum(1 for h in p.score.harmonies if h.shape)

    assert total > 0

    assert with_shape == total, (
        f"expected every harmony in this specific file to have "
        f"a shape (confirmed 62/62 previously); got "
        f"{with_shape}/{total}"
    )
