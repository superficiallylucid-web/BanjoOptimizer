"""
BO-163 -- independent 5th-string control for a user-specific
tuning (main.run_optimizer()'s own tuning_symbol/capo path).

These tests exist because, before BO-163, run_optimizer() had no
way to represent a 5th string retuned independently of capo --
capo has always correctly shifted strings 1-4 only (that part was
never wrong and stays covered here as a regression guard), but the
5th string simply couldn't be set to anything but the base
tuning's own open pitch.

The three acceptance examples below are not arbitrary: they were
chosen, during this feature's own investigation, specifically
because no formula relating the 5th string to the capo value can
reproduce all three simultaneously -- proving the 5th string must
be an independent input, not something derived from capo. See
run_optimizer()'s own fifth_string docstring entry for the full
reasoning.
"""

import main
from tunings import get_tunings

# BO-163 fix (after a real-machine failure report): every
# run_optimizer() call below now pins score_filename explicitly.
# Without it, run_optimizer() silently falls back to globbing
# whatever happens to be in the real scores/ folder at test-run
# time -- which genuinely differs between environments (this
# sandbox ships sample scores; a real deployed install's scores/
# folder may be empty), so a test relying on that implicit state
# is not properly isolated. "White Christmas.mscz" is used
# throughout the rest of this test suite already and confirmed
# present in both environments.
FIXTURE_SCORE = "White Christmas.mscz"


def test_double_c_capo_2_fifth_a_matches_named_double_d():
    """
    The primary acceptance example. Double C + capo 2 + an
    explicit 5th string of "A" must produce exactly the same
    symbol as the real, named "Double D" built-in tuning --
    confirming this feature reproduces a known-correct, already-
    shipped result, not just an internally-consistent one.
    """

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gCGCD", capo=2, fifth_string="A"
    )

    produced_symbol = (
        result["scores"][0]["recommendations"][0].symbol
    )

    assert produced_symbol == "aDADE"

    double_d = get_tunings()["Double D"]

    assert produced_symbol == double_d.symbol


def test_c_standard_capo_5_fifth_a_disproves_capo_offset_formula():
    """
    Disproves any "5th string = base 5th + capo" formula directly:
    C Standard's own open 5th string is "g"; naively shifting it
    by capo 5 would give "C" (g + 5 semitones), not "A". The
    correct result below can only come from treating the 5th
    string as a fully independent input.
    """

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gCGBD", capo=5, fifth_string="A"
    )

    produced_symbol = (
        result["scores"][0]["recommendations"][0].symbol
    )

    assert produced_symbol == "aFCEG"


def test_open_g_capo_3_fifth_f_is_a_lowering_not_a_raise():
    """
    A capo can only ever raise a pitch. This example's 5th string
    ("F") is LOWER than Open G's own open 5th string ("g") --
    reachable only if the 5th string is independent of capo, never
    derivable from any capo-based raise-only formula.

    _notes_to_symbol()'s own sharp-only convention (confirmed
    separately, pre-existing, unrelated to this feature) means the
    real result is written "A#", not "Bb" -- same pitch class,
    different letter.
    """

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gDGBD", capo=3, fifth_string="F"
    )

    produced_symbol = (
        result["scores"][0]["recommendations"][0].symbol
    )

    assert produced_symbol == "fFA#DF"


def test_fifth_string_none_preserves_capo_only_behavior():
    """
    fifth_string=None (the default) must reproduce exactly the
    pre-BO-163 behavior: capo shifts strings 1-4 only, the 5th
    string stays at the base tuning's own open pitch, completely
    unaffected by capo. This is the regression guard for BO-163
    not having changed anything about the *existing* behavior.
    """

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gDGBD", capo=2, fifth_string=None
    )

    tuning = result["scores"][0]["requested_tuning"]

    assert tuning.symbol == "gEAC#E"

    # 5th string pitch class unchanged (g == g), strings 1-4 each
    # shifted by exactly capo (2) semitones from Open G's own open
    # notes -- explicit, direct proof, not just symbol comparison.
    open_g_notes = main._parse_tuning_symbol("gDGBD")

    assert tuning.notes[0] == open_g_notes[0]
    assert tuning.notes[1:] == [n + 2 for n in open_g_notes[1:]]


def test_fifth_string_can_lower_below_the_base_open_pitch():
    """
    Explicit, direct proof (beyond the symbol-level assertion in
    the Open-G/capo-3/5th-F test above) that a fifth_string value
    is not silently clamped or rejected when it's lower than the
    base tuning's own open 5th string.
    """

    open_g_notes = main._parse_tuning_symbol("gDGBD")

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gDGBD", capo=3, fifth_string="F"
    )

    tuning = result["scores"][0]["requested_tuning"]

    assert tuning.notes[0] < open_g_notes[0]


def test_named_tunings_unchanged_including_double_d():
    """
    BO-163 must not alter tunings.py's own static catalog in any
    way. Confirms every named tuning -- Double D included, since
    it's the one most directly related to this feature -- is
    byte-for-byte identical to known-good values.

    BO-166 note: the total count (12, not 13) and Double D's own
    base_tuning format (plain symbol "gCGCD", not the display
    string "Double C (gCGCD)") both reflect BO-166 changes --
    Triple D Darling Cora removed from the catalog, and
    base_tuning's format standardized to a raw symbol everywhere.
    Neither is a BO-163 regression; this test was updated to match.
    """

    tunings = get_tunings()

    assert len(tunings) == 12

    double_d = tunings["Double D"]

    assert double_d.symbol == "aDADE"
    assert double_d.notes == [69, 50, 57, 62, 64]
    assert double_d.base_tuning == "gCGCD"
    assert double_d.capo == 2
    assert double_d.fifth_string_note == "A"

    double_c = tunings["Double C"]

    assert double_c.symbol == "gCGCD"
    assert double_c.notes == [67, 48, 55, 60, 62]
    assert double_c.capo == 0


def test_fifth_string_sets_fifth_string_note_on_result():
    """
    Tuning.fifth_string_note should reflect the caller-supplied
    value directly, for display consistency with how the named
    "Double D" tuning already represents itself (fifth_string_note
    == "A", matching its own capo-independent 5th string).
    """

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gCGCD", capo=2, fifth_string="A"
    )

    tuning = result["scores"][0]["requested_tuning"]

    assert tuning.fifth_string_note == "A"


def test_fifth_string_none_leaves_fifth_string_note_none():

    result = main.run_optimizer(
        score_filename=FIXTURE_SCORE,
        tuning_symbol="gDGBD", capo=2, fifth_string=None
    )

    tuning = result["scores"][0]["requested_tuning"]

    assert tuning.fifth_string_note is None
