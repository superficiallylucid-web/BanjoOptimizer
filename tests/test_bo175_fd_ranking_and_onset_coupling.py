"""
tests/test_bo175_fd_ranking_and_onset_coupling.py

Regression tests for BO-175, two independent, additive pieces:

Part 1 -- chord_generator.py's own _score_candidate(): the open-
string coefficient was reduced from 10 to 3.3 (span/avg/muted_
count weights all deliberately left unchanged). Root cause: with
melody note D4 at its open position, Aureolin's own Dm chord (Key
D, Double C/gCGCD) tied through every earlier ranking priority
between shapes "2250" (one open string, 3-fret span, a little-
finger reach) and "2223" (zero open strings, a comfortable 1-fret
barre), and _score_candidate()'s prior +10-per-open-string bonus
let the harder-to-play "2250" win purely on the open string, even
though playability.evaluate()'s own separate accept/reject scorer
already rated "2223" far higher (91 vs 73). This task's own
investigation confirmed a full switch to playability._score()'s
weights was too broad (broke 8 existing cases); 3.3 is the
smallest safe reduction, chosen by direct calculation against
every real tied-quality case this coefficient affects -- not just
the Aureolin example alone (see chord_generator.py's own updated
docstring on _score_candidate for the full derivation).

Part 2 -- score_generator.py's own new _choose_onset_melody_fret_
with_fd_coupling(): for a chord whose harmony onset coincides with
exactly one melody note, and where that chord's own box (the
melody immediately following it) is genuinely empty -- so there is
no subsequent-note continuity behavior (BO-54/BO-125) to disturb
-- every one of that note's own playable TAB positions is tried
against the existing FD-ranking machinery, and the position whose
own best FD genuinely ranks highest is preferred, instead of
always defaulting to the lowest fret. Deliberately scoped OFF
whenever box_notes is non-empty, so BO-54's own hp_notes_played()
continuity anchor (which reuses this same preferred_melody_fret
value) is never altered by this task -- confirmed directly in this
file's own non-onset regression test below.
"""

import sys

sys.path.insert(0, '.')

from fretboard import parse_shape

from chord_generator import _score_candidate

from chord_service import ChordService

from chord_library import ChordLibrary

from tunings import get_tunings

from models import Note

from score_generator import (
    _choose_onset_melody_fret_with_fd_coupling,
    _select_chord_shape_for_harmony
)


# ---------------------------------------------------------
# 1 -- Aureolin Dm / Double C: 2223 preferred over 2250
# (direct scoring behavior, the real tied-quality case)
# ---------------------------------------------------------

def test_aureolin_dm_2223_preferred_over_2250():

    shape_2250 = parse_shape("2250")

    shape_2223 = parse_shape("2223")

    assert _score_candidate(shape_2223) > _score_candidate(
        shape_2250
    )


# ---------------------------------------------------------
# 2 -- the chosen coefficient's own exact raw values, so any
# future change to this coefficient is caught explicitly
# rather than only through the ranking-order assertion above
# ---------------------------------------------------------

def test_score_candidate_raw_values_for_aureolin_shapes():

    shape_2250 = parse_shape("2250")

    shape_2223 = parse_shape("2223")

    assert _score_candidate(shape_2250) == -5.7

    assert _score_candidate(shape_2223) == -5.5


# ---------------------------------------------------------
# 3 -- same-onset coupling chooses the melody position whose
# own FD genuinely ranks highest (direct unit test on the new
# helper, real Aureolin Dm/Double C data)
# ---------------------------------------------------------

def test_onset_coupling_selects_fd_optimal_fret():

    tuning = get_tunings()["Double C"]

    service = ChordService(ChordLibrary())

    d4 = Note(midi=62, measure=1, beat=0.0)

    chosen_fret = _choose_onset_melody_fret_with_fd_coupling(
        d4, tuning, service, "D", 2, "m", "Minor",
        incoming_shape=None
    )

    # D4 is playable at fret 0 (open, string index 3) or fret 2
    # (string index 2) in Double C. The coupling must choose 2 --
    # the position whose own best Dm FD ("2223") genuinely
    # outranks the open position's own best FD ("2250") -- not
    # simply the lowest fret.
    assert chosen_fret == 2


# ---------------------------------------------------------
# 4 -- non-onset / subsequent melody behavior is unchanged:
# when a chord's own box (the melody immediately following its
# onset) is non-empty, the coupling must never activate, and
# BO-54's own hp_notes_played() continuity anchor must still be
# the plain lowest-fret value -- confirmed directly against the
# real Christmas Song Cmaj7/Double D case BO-54 itself
# established, by forcing the coupling off entirely and
# confirming the result is identical either way.
# ---------------------------------------------------------

def test_coupling_never_activates_when_box_notes_present():

    from conftest import fixture_path

    from parser import MuseScoreFile

    DOUBLE_D = get_tunings()["Double D"]

    p = MuseScoreFile(str(fixture_path("The Christmas Song.mscz")))

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    harmonies_sorted = sorted(
        p.harmonies, key=lambda h: (h.measure, h.beat)
    )

    cmaj7_index = next(
        i for i, h in enumerate(harmonies_sorted)
        if h.symbol == "Cmaj7"
    )

    cmaj7 = harmonies_sorted[cmaj7_index]

    next_harmony = (
        harmonies_sorted[cmaj7_index + 1]
        if cmaj7_index + 1 < len(harmonies_sorted) else None
    )

    # This chord's own box is genuinely non-empty (B4/A4/G4/F4
    # immediately follow, per BO-54's own established data), so
    # the coupling must never be consulted for it -- confirmed by
    # comparing the real result against the same call with the
    # coupling helper forced to always return None.
    shape_real, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    import score_generator as sg

    original_helper = sg._choose_onset_melody_fret_with_fd_coupling

    sg._choose_onset_melody_fret_with_fd_coupling = (
        lambda *args, **kwargs: None
    )

    try:

        shape_forced_off, _, _ = _select_chord_shape_for_harmony(
            cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
            next_harmony=next_harmony
        )

    finally:

        sg._choose_onset_melody_fret_with_fd_coupling = (
            original_helper
        )

    assert shape_real.shape == shape_forced_off.shape


# ---------------------------------------------------------
# 5 -- ordinary existing behavior stays intact: BO-18's own
# lexicographic quality-first architecture is untouched by
# Part 1's coefficient change -- a lower-quality but more
# "playable" voicing must still never outrank a complete one.
# ---------------------------------------------------------

def test_bo18_quality_first_architecture_still_protects_complete_voicing():

    tuning = get_tunings()["A Modal Sawmill"]

    service = ChordService(ChordLibrary())

    shapes = service.get_shapes(tuning, "C", 0, "", "Major")

    from fretboard import sounding_notes

    notes = sounding_notes(tuning, shapes[0].shape)

    # The top-ranked C major shape must still sound all three of
    # C major's own defining pitch classes (C, E, G) -- BO-18's
    # own protection, unaffected by Part 1's reweighting since it
    # only participates as a tiebreaker among equal-quality
    # voicings, never as an override of quality itself.
    coverage = {note.midi % 12 for note in notes}

    assert {0, 4, 7}.issubset(coverage)


# ---------------------------------------------------------
# 6 -- an existing validated BO-148.4 case remains protected:
# finger count must still not decide between the D7/Open G
# candidates this test already established, now confirmed safe
# at the chosen coefficient (3.3, inside the required (3.1667,
# 3.5) window this exact case's own quality-tied shapes define).
# ---------------------------------------------------------

def test_bo148_4_d7_open_g_case_still_protected():

    open_g = get_tunings()["Open G"]

    service = ChordService(ChordLibrary())

    shapes = service.get_shapes_for_exact_melody_pitch(
        open_g, "D", 2, "7", "Dominant 7th", melody_pitches={72}
    )

    ranked_shapes = [s.shape for s in shapes]

    assert ranked_shapes.index("0(11)(10)(10)") < (
        ranked_shapes.index("777(10)")
    )
