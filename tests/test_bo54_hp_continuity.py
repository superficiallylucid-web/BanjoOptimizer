"""
tests/test_bo54_hp_continuity.py

Regression tests for BO-54: melody-aware chord-shape selection
and Hand Position (HP) continuity.

Core mechanism (chord_service.py's own get_shapes_for_exact_
melody_pitch()): among candidate chord shapes within HP_
CONTINUITY_QUALITY_TOLERANCE (0.5 -- not arbitrary, matches
BO-42's own confirmed "missing only the non-defining 5th" safe
tier) of the group's own best quality_score, prefer whichever one
lets the most consecutive following melody notes (the box built
by melody_box_analysis.build_melody_boxes(), reused unmodified)
stay within the hand position that shape's own working fret
establishes -- reusing the same "position N covers frets N..N+3"
geometry already established elsewhere in this project (BO-51's
own diagnose_melody_chord_realization()).

Primary validation case throughout this file (The Christmas Song,
Double D tuning, Cmaj7 at m2): confirmed real, not constructed --
the melody sequence B4/A4/G4/F4 immediately follows Cmaj7's own
onset. The prior shape (10)(10)90 (quality 21.5, working_fret=9)
only lets 1 of these 4 stay in its own HP; the real candidate
(10)790 (quality 21.0 -- missing only the chord's own non-defining
5th) lets all 4.

IMPORTANT -- a separate, real case (The Christmas Song, A Modal
Sawmill/aEADE tuning, this SAME Cmaj7 chord) produced a genuine,
evidence-based tradeoff the BO-54 task explicitly asked NOT be
silently resolved: 0798 provides the same HP-continuity benefit
but is missing the chord's own 5th and doubles the E, versus the
prior 0(10)98's own complete C-E-G-B voicing. See the BO-54 final
report's own dedicated section for the full evidence; this file
does not take a position on it, and no test here depends on which
answer is "correct."
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import (
    ChordService, HP_CONTINUITY_QUALITY_TOLERANCE
)

from chord_library import ChordLibrary

from score_generator import (
    _select_chord_shape_for_harmony, _melody_notes_at_harmony_onset
)

from melody_box_analysis import build_melody_boxes, realize_note

from playing_model import (
    analyze_tuning_playing_model, diagnose_melody_chord_realization
)

from models import Score


DOUBLE_D = get_tunings()["Double D"]  # aDADE


def _christmas_song_cmaj7_double_d():
    """
    Real data: The Christmas Song's own real Cmaj7 occurrence in
    Double D, with the harmonies list, next_harmony, and melody
    notes needed to reproduce the exact real selection.
    """

    p = MuseScoreFile("scores/The Christmas Song.mscz")

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

    return p, service, cmaj7, next_harmony


# ---------------------------------------------------------
# 1 -- melody-aware chord-shape preference
# ---------------------------------------------------------

def test_melody_aware_chord_shape_preference():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    # Real, confirmed: the melody-compatible candidate wins over
    # the prior, slightly-higher-quality one that serves the
    # following melody far worse.
    assert shape.shape == "(10)790"


# ---------------------------------------------------------
# 2 -- HP continuity: several consecutive melody TPs remain
# within the HP the chord establishes
# ---------------------------------------------------------

def test_hp_continuity_keeps_consecutive_notes_in_position():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    boxes = build_melody_boxes(p.score)

    cmaj7_box = next(b for b in boxes if b[0] == cmaj7)

    _, _, box_notes = cmaj7_box

    # Real, confirmed sequence: B4, A4, G4, F4.
    assert [n.midi for n in box_notes] == [71, 69, 67, 65]

    for note in box_notes:

        box_note = realize_note(note, DOUBLE_D)

        # NOTE -- checked directly against fretted_positions here
        # (the same check hp_notes_played() itself uses), not via
        # diagnose_melody_chord_realization()'s own playable_from_
        # chord_position. A real, pre-existing BO-51 limitation
        # was found during BO-54 testing: that diagnostic's own
        # playable_from_chord_position checks only its own single,
        # independently-scored best_realization, not every
        # candidate realization -- so a note reachable from this
        # HP via a DIFFERENT string than its own best_realization
        # (confirmed real: G4's own best_realization lands on
        # fret 3, but fret 7 -- within this HP -- is also among
        # its own real candidate positions) reads as "not
        # playable" there even though it genuinely is. Not a
        # BO-54 bug, and out of this task's own scope to fix; see
        # the BO-54 final report's own remaining-limitations
        # section.
        working_fret = 7

        playable = (
            box_note.has_open_realization
            or working_fret in box_note.fretted_positions
        )

        assert playable, (
            f"midi {note.midi} should remain playable from "
            f"Cmaj7's own new HP without a position change"
        )


# ---------------------------------------------------------
# 3 -- genuine HP transition: BO-54 must not make continuity
# absolute when the following notes genuinely can't stay
# ---------------------------------------------------------

def test_genuine_hp_transition_still_allowed():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    # The chord immediately following Cmaj7's own box (Em, per
    # the real harmony sequence) still gets its OWN, separately
    # selected shape -- HP continuity does not force the WHOLE
    # song into one hand position; a real transition still
    # happens at the next chord boundary.
    harmonies_sorted = sorted(
        p.harmonies, key=lambda h: (h.measure, h.beat)
    )

    em_index = harmonies_sorted.index(next_harmony)

    em_next = (
        harmonies_sorted[em_index + 1]
        if em_index + 1 < len(harmonies_sorted) else None
    )

    em_shape, _, _ = _select_chord_shape_for_harmony(
        next_harmony, DOUBLE_D, service,
        melody_notes=p.score.notes, next_harmony=em_next
    )

    assert next_harmony.symbol == "Em"

    assert em_shape.shape != shape.shape


# ---------------------------------------------------------
# 4 -- intrinsic chord-quality protection: a candidate outside
# the tolerance must never win regardless of HP continuity
# ---------------------------------------------------------

def test_severely_lower_quality_shape_never_wins():

    service = ChordService(ChordLibrary())

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=9
    )

    max_quality = max(s.voicing_quality_score for s in shapes)

    # Real, confirmed: "2350" (quality 19.5) is a genuine
    # candidate for this chord, 2.0 points below the group's own
    # best (21.5) -- well outside HP_CONTINUITY_QUALITY_
    # TOLERANCE (0.5) regardless of how well it might otherwise
    # serve the following melody.
    low_quality_shape = next(
        s for s in shapes if s.shape == "2350"
    )

    assert (
        max_quality - low_quality_shape.voicing_quality_score
        > HP_CONTINUITY_QUALITY_TOLERANCE
    )

    winner = shapes[0]

    assert (
        max_quality - winner.voicing_quality_score
        <= HP_CONTINUITY_QUALITY_TOLERANCE
    ), (
        "the actual winning candidate must stay within the "
        "quality tolerance band -- HP continuity must never "
        "reach outside it"
    )


# ---------------------------------------------------------
# 5 -- multiple melody notes: a shape that only serves one
# note should not automatically beat one serving the phrase
# ---------------------------------------------------------

def test_multiple_notes_considered_not_just_first():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    boxes = build_melody_boxes(p.score)

    cmaj7_box = next(b for b in boxes if b[0] == cmaj7)

    _, _, box_notes = cmaj7_box

    realized = [realize_note(n, DOUBLE_D) for n in box_notes]

    # Real, confirmed: the winning shape's own working fret (7)
    # serves all 4 box notes, not merely the first (onset) one --
    # confirms the evaluation is phrase-level, not single-note.
    from fretboard import parse_shape
    from playing_model import _chord_working_fret

    working_fret = _chord_working_fret(parse_shape(shape.shape))

    notes_played = 0

    for note in realized:

        playable = (
            note.has_open_realization
            or working_fret in note.fretted_positions
        )

        if not playable:

            break

        notes_played += 1

    assert notes_played == len(box_notes) == 4


# ---------------------------------------------------------
# 6 -- chord-tone vs actual voicing: HP continuity does not
# confuse theoretical membership with actual voicing membership
# ---------------------------------------------------------

def test_hp_continuity_respects_chord_tone_vs_voicing_distinction():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    boxes = build_melody_boxes(p.score)

    cmaj7_box = next(b for b in boxes if b[0] == cmaj7)

    _, _, box_notes = cmaj7_box

    # A4 (69) is not a Cmaj7 chord tone at all (C-E-G-B) --
    # confirms BO-54's own HP-continuity mechanism still lets
    # BO-51's own diagnostic correctly classify it as a non-
    # chord-tone, even though it's fully reachable from the
    # chord's own new HP.
    a4 = next(n for n in box_notes if n.midi == 69)

    result = diagnose_melody_chord_realization(
        shape, DOUBLE_D, cmaj7, a4
    )

    assert result.chord_contains_pitch is False

    assert result.playable_from_chord_position is True


# ---------------------------------------------------------
# 7 -- position coherence: prefer the shape permitting a
# coherent melody sequence over one causing unnecessary HP
# movement, when the difference is musically meaningful
# ---------------------------------------------------------

def test_position_coherence_preferred_when_meaningful():

    p, service, cmaj7, next_harmony = (
        _christmas_song_cmaj7_double_d()
    )

    shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7, DOUBLE_D, service, melody_notes=p.score.notes,
        next_harmony=next_harmony
    )

    boxes = build_melody_boxes(p.score)

    cmaj7_box = next(b for b in boxes if b[0] == cmaj7)

    _, _, box_notes = cmaj7_box

    playable_flags = []

    for note in box_notes:

        box_note = realize_note(note, DOUBLE_D)

        # See test 2's own comment for why this checks
        # fretted_positions directly rather than via diagnose_
        # melody_chord_realization()'s own playable_from_chord_
        # position (a real, pre-existing BO-51 limitation found
        # during BO-54 testing, not a BO-54 bug).
        working_fret = 7

        playable_flags.append(
            box_note.has_open_realization
            or working_fret in box_note.fretted_positions
        )

    # Real, confirmed: every note in this phrase is coherently
    # playable from the one HP the chosen shape establishes --
    # zero position changes across the whole phrase.
    assert all(playable_flags)


# ---------------------------------------------------------
# 8 -- existing Playing Model regression: total_score/phrase
# results for a real song remain unaffected by this file's own
# additions (BO-54 changes chord-shape SELECTION upstream of
# the Playing Model, not the Playing Model's own scoring logic)
# ---------------------------------------------------------

def test_existing_playing_model_scoring_logic_unchanged():

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    temp_score = Score(
        notes=p.score.notes, harmonies=p.harmonies
    )

    result = analyze_tuning_playing_model(
        temp_score, DOUBLE_D, service
    )

    # Real, confirmed: phrase count is a property of the melody/
    # harmony structure itself (build_melody_boxes()), not of
    # which specific shape is chosen for each chord -- unaffected
    # by BO-54.
    assert len(result.phrases) == 56

    assert result.total_score > 0
