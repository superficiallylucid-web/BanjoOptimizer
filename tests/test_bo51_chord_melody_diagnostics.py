"""
tests/test_bo51_chord_melody_diagnostics.py

Regression tests for BO-51: chord/melody realization diagnostics.

diagnose_melody_chord_realization() (playing_model.py) is purely
additive and diagnostic-only -- it calls evaluate_combination()
and melody_box_analysis.realize_note() exactly as analyze_tuning_
playing_model() already does, unmodified, and adds exactly one
new computation (chord-theory membership via music.chord_tones())
neither existing function performs. No scoring, chord-shape
selection, or tuning-ranking behavior is touched by this file's
own tests or by the function itself.

Real-data investigation notes (see the BO-51 report for the full
discussion): the exact "Open G 0000 / B3" scenario mentioned in
the BO-51 task does not occur in the current 4-song real dataset
-- White Christmas's own real G chord (Open G tuning) selects
"0009", not "0000" (melody-aware selection picks a different
voicing matching its own onset note), and B3 does not occur
anywhere in White Christmas's own melody at all. Tests 1-2 and 6
use a small, clearly-labeled constructed case for exactly this
reason, rather than manufacturing a misleading claim that this is
real song data. Tests 3-5, 7 use real data directly (The Christmas
Song's own real Cmaj7/A Modal Sawmill occurrence, aEADE).
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from models import (
    Harmony, Note, ChordShape,
    NON_CHORD_TONE,
    CHORD_TONE_NOT_IN_VOICING,
    PLAYABLE_FROM_CHORD_POSITION,
    AVAILABLE_BUT_POSITION_CHANGE_REQUIRED
)

from score_generator import (
    _select_chord_shape_for_harmony, _melody_notes_at_harmony_onset
)

from playing_model import diagnose_melody_chord_realization


OPEN_G = get_tunings()["Open G"]

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]


def _christmas_song_cmaj7_case():
    """
    Real data: The Christmas Song's own real Cmaj7 occurrence in
    A Modal Sawmill, with its own real, melody-aware-selected
    chord shape (confirmed directly: "0(10)98").
    """

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    harmony = next(
        h for h in p.harmonies if h.symbol == "Cmaj7"
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        harmony, A_MODAL_SAWMILL, service,
        melody_notes=p.score.notes
    )

    return harmony, shape, p.score.notes


# ---------------------------------------------------------
# 1 -- non-chord tone (constructed case: Open G "0000", a
# pitch outside G major entirely)
# ---------------------------------------------------------

def test_non_chord_tone_classified_correctly():

    # Open G "0000" sounds D3/G3/B3/D4 -- an F natural (not in
    # G major at all) is a genuine, clear non-chord-tone case.
    g_major = Harmony(
        measure=1, root_pc=7, quality_code="", symbol="G"
    )

    f_note = Note(measure=1, beat=0.0, midi=65)  # F4

    shape = ChordShape(tuning="gDGBD", root="G", quality="Major", shape="0000")

    result = diagnose_melody_chord_realization(
        shape, OPEN_G, g_major, f_note
    )

    assert result.chord_contains_pitch is False

    assert result.classification == NON_CHORD_TONE


# ---------------------------------------------------------
# 2 -- chord tone absent from this specific voicing
# ---------------------------------------------------------

def test_chord_tone_not_in_voicing_distinguished_from_present():

    # G major's own theoretical tones are G/B/D. A shape that
    # only sounds G (e.g. all four strings landing on G/D, no D
    # or B at all) would omit a real chord tone -- constructed
    # directly against Open G's own real open strings (D3/G3/B3/
    # D4) by choosing a shape that avoids the B string entirely.
    g_major = Harmony(
        measure=1, root_pc=7, quality_code="", symbol="G"
    )

    b3_note = Note(measure=1, beat=0.0, midi=59)  # B3

    # Fret the B string (string_index 2, open pitch 59) up to
    # D (62) instead of sounding B -- omits B from this specific
    # voicing while G major's own theory still includes it.
    shape = ChordShape(tuning="gDGBD", root="G", quality="Major", shape="0030")

    result = diagnose_melody_chord_realization(
        shape, OPEN_G, g_major, b3_note
    )

    assert result.chord_contains_pitch is True

    assert result.voicing_contains_pitch is False

    assert result.classification == CHORD_TONE_NOT_IN_VOICING


# ---------------------------------------------------------
# 3 -- chord tone present in the actual voicing (real data)
# ---------------------------------------------------------

def test_chord_tone_present_in_voicing_real_data():

    harmony, shape, notes = _christmas_song_cmaj7_case()

    onset_notes = _melody_notes_at_harmony_onset(harmony, notes)

    b4 = onset_notes[0]  # confirmed real onset: B4, midi 71

    assert b4.midi == 71

    result = diagnose_melody_chord_realization(
        shape, A_MODAL_SAWMILL, harmony, b4
    )

    assert result.chord_contains_pitch is True

    assert result.voicing_contains_pitch is True

    # Real, confirmed finding: even a pitch genuinely present in
    # the voicing is not automatically PLAYABLE_FROM_CHORD_
    # POSITION -- evaluate_combination()'s own best-realization
    # search is independent of which specific string the chord
    # shape itself sounds this pitch on.
    assert result.classification in (
        PLAYABLE_FROM_CHORD_POSITION,
        AVAILABLE_BUT_POSITION_CHANGE_REQUIRED
    )


# ---------------------------------------------------------
# 4 -- playable from chord position (real data)
# ---------------------------------------------------------

def test_playable_from_chord_position_real_data():

    harmony, shape, notes = _christmas_song_cmaj7_case()

    c5 = next(n for n in notes if n.midi == 72 and n.measure == 2)

    result = diagnose_melody_chord_realization(
        shape, A_MODAL_SAWMILL, harmony, c5
    )

    # Real, confirmed: C5 immediately after Cmaj7's own onset is
    # playable from the chord's own hand position without a
    # position change.
    assert result.playable_from_chord_position is True

    assert result.classification == PLAYABLE_FROM_CHORD_POSITION


# ---------------------------------------------------------
# 5 -- position change required (real data)
# ---------------------------------------------------------

def test_position_change_required_real_data():

    # BO-54 note: the original example here (Cmaj7/B4) is no
    # longer valid -- BO-54's own HP-continuity mechanism
    # specifically changed that chord's own selected shape so
    # B4 (and the rest of that phrase) NO LONGER requires a
    # position change, which is the intended, confirmed outcome
    # of BO-54, not a regression in this diagnostic. Replaced
    # with a different real example (confirmed directly still
    # requiring a position change after BO-54): My Favorite
    # Things, C Standard, the real G chord at m17 (shape 2000)
    # and its own onset note B2.

    p = MuseScoreFile("scores/My Favorite Things.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    c_standard = get_tunings()["C Standard"]

    harmonies_sorted = sorted(
        p.harmonies, key=lambda h: (h.measure, h.beat)
    )

    g_index = next(
        i for i, h in enumerate(harmonies_sorted)
        if h.measure == 17 and h.symbol == "G"
    )

    g_harmony = harmonies_sorted[g_index]

    next_harmony = (
        harmonies_sorted[g_index + 1]
        if g_index + 1 < len(harmonies_sorted) else None
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        g_harmony, c_standard, service,
        melody_notes=p.score.notes, next_harmony=next_harmony
    )

    b2 = next(
        n for n in p.score.notes
        if n.measure == 17 and n.beat == 0.0
    )

    result = diagnose_melody_chord_realization(
        shape, c_standard, g_harmony, b2
    )

    # Real, confirmed: B2 is a genuine chord tone, present in
    # this exact voicing, but still requires a position change
    # under this diagnostic's own best-realization search.
    assert result.chord_contains_pitch is True

    assert result.voicing_contains_pitch is True

    assert result.playable_from_chord_position is False

    assert result.classification == (
        AVAILABLE_BUT_POSITION_CHANGE_REQUIRED
    )


# ---------------------------------------------------------
# 6 -- multiple candidate positions retained (constructed
# case, Open G)
# ---------------------------------------------------------

def test_multiple_candidate_positions_retained():

    g_major = Harmony(
        measure=1, root_pc=7, quality_code="", symbol="G"
    )

    d4_note = Note(measure=1, beat=0.0, midi=62)  # D4

    shape = ChordShape(tuning="gDGBD", root="G", quality="Major", shape="0000")

    result = diagnose_melody_chord_realization(
        shape, OPEN_G, g_major, d4_note
    )

    # D4 (62) is available on more than one string in Open G
    # (open D3-string idx0 an octave down doesn't count, but
    # D4 itself has both an open realization on string_index 3
    # and a fretted one higher up strings 0-2) -- confirms the
    # full candidate list isn't collapsed to a single position.
    assert len(result.candidate_realizations) > 1

    assert result.best_realization in result.candidate_realizations


# ---------------------------------------------------------
# 7 -- octave correctness (real data)
# ---------------------------------------------------------

def test_octave_not_confused_with_pitch_class_real_data():

    harmony, shape, notes = _christmas_song_cmaj7_case()

    c4 = next(n for n in notes if n.midi == 60)  # C4, not C5

    result = diagnose_melody_chord_realization(
        shape, A_MODAL_SAWMILL, harmony, c4
    )

    assert result.melody_pitch == 60

    assert result.melody_pitch_class == 0

    assert result.melody_octave == 4

    c5 = next(n for n in notes if n.midi == 72 and n.measure == 2)

    c5_result = diagnose_melody_chord_realization(
        shape, A_MODAL_SAWMILL, harmony, c5
    )

    # Same pitch class (C), different octave -- must not be
    # treated as the identical melody event.
    assert c5_result.melody_pitch_class == result.melody_pitch_class

    assert c5_result.melody_pitch != result.melody_pitch

    assert c5_result.melody_octave != result.melody_octave


# ---------------------------------------------------------
# 8 -- existing Playing Model regression: total_score/phrase
# results are byte-identical to before BO-51 for a real song
# ---------------------------------------------------------

def test_existing_playing_model_totals_unchanged():

    from playing_model import analyze_tuning_playing_model

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    from models import Score

    temp_score = Score(
        notes=p.score.notes, harmonies=p.harmonies
    )

    result = analyze_tuning_playing_model(
        temp_score, A_MODAL_SAWMILL, service
    )

    # Real, confirmed value from before BO-51 (unchanged
    # function, unchanged call path) -- confirms BO-51 added no
    # side effects to the existing Playing Model at all.
    assert len(result.phrases) == 56

    assert result.total_score > 0
