"""
tests/test_bo138_3_melody_inclusion_in_chord_selection.py

Focused tests for BO-138.3: chord/FD selection prefers a
candidate that actually contains the resolved sounding melody
pitch(es), when a viable such candidate exists -- fixing the
real Moon River gap (BO-138.1/138.2) where "0012" was selected
despite containing none of the melody's own real pitches, while
a genuinely better candidate ("4555") existed but was eliminated
by deduplication and, even if it survived, by too-weak melody
support logic.

Two changes, confirmed together via the real Moon River case:
  1. chord_generator.py's own deduplication no longer lets a
     non-melody-containing candidate silently eliminate a
     melody-containing one sharing the same voicing signature.
  2. score_generator.py's own chord-selection logic now checks
     actual pitch containment (not merely working-fret height)
     -- but only overrides the EXISTING Rule A/B choice when
     that choice doesn't already achieve the best containment
     found. This second point was a real correction made during
     implementation: an earlier, unconditional-preference version
     caused a genuine regression (My Favorite Things/Open C's
     own m73), needlessly replacing an already melody-containing,
     comfortable shape with a different, higher-ranked but less
     comfortable one.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import (
    _select_chord_shape_for_harmony,
    _chord_candidate_contains_melody_pitches
)

from chord_service import ChordService

from chord_library import ChordLibrary

from chord_generator import generate_candidates

from fretboard import parse_shape, sounding_notes


def _load(path):

    p = MuseScoreFile(path)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p


def _select(p, harmony, tuning, service):

    idx = p.harmonies.index(harmony)

    next_harmony = (
        p.harmonies[idx + 1] if idx + 1 < len(p.harmonies) else None
    )

    shape, is_exception, exception_dict = (
        _select_chord_shape_for_harmony(
            harmony, tuning, service, melody_notes=p.score.notes,
            next_harmony=next_harmony, incoming_shape=None
        )
    )

    return shape


# ---------------------------------------------------------
# 1 -- Moon River real case
# ---------------------------------------------------------

def test_moon_river_4555_survives_deduplication():

    tuning = get_tunings()['C Standard']

    shapes = generate_candidates(
        tuning, 'C', 0, '', 'C', melody_pitches={52}
    )

    assert '4555' in [s.shape for s in shapes]


def test_moon_river_4555_is_selected():

    p = _load('scores/Moon River.mscz')

    tuning = get_tunings()['C Standard']

    service = ChordService(ChordLibrary())

    shape = _select(p, p.harmonies[0], tuning, service)

    assert shape.shape == '4555', (
        f"Expected '4555' to be selected at Moon River m1/b1, "
        f"got {shape.shape!r}."
    )


def test_moon_river_selected_fd_contains_melody_e3():

    p = _load('scores/Moon River.mscz')

    tuning = get_tunings()['C Standard']

    service = ChordService(ChordLibrary())

    shape = _select(p, p.harmonies[0], tuning, service)

    notes = sounding_notes(tuning, shape.shape)

    sounding_pitches = {n.midi for n in notes}

    assert 52 in sounding_pitches, (
        f"Expected the selected FD to sound the actual melody "
        f"pitch E3 (52), sounding pitches were {sounding_pitches}."
    )


# ---------------------------------------------------------
# 2 -- deduplication
# ---------------------------------------------------------

def test_dedup_prefers_melody_containing_over_non_containing():

    tuning = get_tunings()['C Standard']

    open_notes = tuning.notes[1:]

    shapes = generate_candidates(
        tuning, 'C', 0, '', 'C', melody_pitches={52}
    )

    matching = [s for s in shapes if s.shape in ('4555', '0055')]

    # "0055" must not be the one that survived in place of the
    # melody-containing "4555" -- confirmed real root cause
    # (BO-138.1): both share the same voicing signature.
    assert any(s.shape == '4555' for s in matching)

    assert not any(s.shape == '0055' for s in matching)


def test_dedup_unchanged_when_neither_candidate_contains_melody():

    # No melody context at all -- existing dedup/scoring
    # behavior (open-string bonus wins ties) must be completely
    # unaffected.
    tuning = get_tunings()['C Standard']

    shapes_no_melody = generate_candidates(tuning, 'C', 0, '', 'C')

    shapes_with_unrelated_melody = generate_candidates(
        tuning, 'C', 0, '', 'C', melody_pitches={999}
    )

    assert (
        [s.shape for s in shapes_no_melody]
        == [s.shape for s in shapes_with_unrelated_melody]
    )


# ---------------------------------------------------------
# 3 -- non-chord-tone fallback (real Moon River m3/m12)
# ---------------------------------------------------------

def test_moon_river_m3_f_chord_melody_b_unchanged():

    p = _load('scores/Moon River.mscz')

    tuning = get_tunings()['C Standard']

    service = ChordService(ChordLibrary())

    m3 = next(h for h in p.harmonies if h.measure == 3)

    shape = _select(p, m3, tuning, service)

    # Real, confirmed pre-BO-138.3 result -- melody B (pitch
    # class 11) is not one of F's own tones ([5,9,0]) at all, so
    # no candidate could ever contain it; behavior must be
    # completely unchanged.
    assert shape.shape == '0213'


def test_moon_river_m12_bb7_melody_g_unchanged():

    p = _load('scores/Moon River.mscz')

    tuning = get_tunings()['C Standard']

    service = ChordService(ChordLibrary())

    m12 = next(h for h in p.harmonies if h.measure == 12)

    shape = _select(p, m12, tuning, service)

    # Real, confirmed pre-BO-138.3 result -- melody G (pitch
    # class 7) is not one of Bb7's own tones ([10,2,5,8]).
    assert shape.shape == '5336'


# ---------------------------------------------------------
# 4 -- dyad (direct function test, mirroring real BO-135 data)
# ---------------------------------------------------------

def test_dyad_containment_prefers_both_notes_over_one():

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    # Real, confirmed Gamboge D7sus2 shape "5500" sounds
    # 57, 62, 60, 64 -- contains both dyad pitches (57, 62).
    values = parse_shape('5500')

    count_both = _chord_candidate_contains_melody_pitches(
        values, open_notes, [57, 62]
    )

    assert count_both == 2

    # Same shape, but only one of the two "melody" pitches is
    # actually present -- confirms partial containment is
    # correctly distinguished from full containment.
    count_one = _chord_candidate_contains_melody_pitches(
        values, open_notes, [57, 999]
    )

    assert count_one == 1


def test_my_favorite_things_open_c_m73_regression_preserved():

    # The exact case that surfaced BO-138.3's own implementation
    # correction: melody G (55) at the G chord, m73. "7777"
    # (working_fret=7, comfortable) already contains the melody
    # pitch and must NOT be replaced by a different, higher-
    # ranked, also-melody-containing but less comfortable
    # candidate.
    p = _load('scores/My Favorite Things.mscz')

    tuning = get_tunings()['Open C']

    service = ChordService(ChordLibrary())

    m73 = next(h for h in p.harmonies if h.measure == 73)

    shape = _select(p, m73, tuning, service)

    assert shape.shape == '7777', (
        f"Expected the existing, already melody-containing, "
        f"comfortable shape '7777' to be preserved, got "
        f"{shape.shape!r}."
    )


# ---------------------------------------------------------
# 5 -- octave substitution uses the resolved pitch
# ---------------------------------------------------------

def test_containment_uses_resolved_not_source_pitch():

    # Real, explicit octave substitution (BO-133.4's own
    # existing mechanism): Moon River m1's own source melody
    # (E3=52) shifted up one octave to E4=64 -- confirmed
    # directly reachable in C Standard tuning. If chord selection
    # mistakenly used the ORIGINAL source pitch (52) instead of
    # the resolved one (64), it would still select "4555" (built
    # for 52). The correct, resolved-pitch-aware behavior must
    # instead select "0012" -- confirmed directly, "0012" already
    # contains 64, so the existing Rule A/B choice is correctly
    # preserved (not overridden), demonstrating the resolved
    # pitch, not the source pitch, drives the decision.
    p = _load('scores/Moon River.mscz')

    p.apply_octave_substitutions(3, [
        {
            "measure": 1, "beat": 0.0,
            "original_midi": 52, "new_midi": 64
        }
    ])

    tuning = get_tunings()['C Standard']

    service = ChordService(ChordLibrary())

    shape = _select(p, p.harmonies[0], tuning, service)

    assert shape.shape == '0012', (
        f"Expected the RESOLVED pitch (64, already contained by "
        f"the existing Rule A/B choice '0012') to drive "
        f"selection, not the original source pitch (52, which "
        f"would incorrectly select '4555'). Got {shape.shape!r}."
    )


# ---------------------------------------------------------
# 6 -- tie: BO-137's inherited result is not independently
# re-evaluated (chord selection and tie inheritance operate in
# genuinely separate passes -- confirmed directly, this BO's own
# investigation -- so this is a regression check, not new
# integration)
# ---------------------------------------------------------

def test_tie_inheritance_still_authoritative_after_bo138_3():

    from score_generator import generate_tab_from_template

    import os

    p = MuseScoreFile('scores/Gamboge.mscz') \
        if os.path.exists('scores/Gamboge.mscz') else None

    if p is None:

        # Real Gamboge fixture not present in this environment --
        # skip gracefully rather than fail on an absent file,
        # matching this project's own existing SKIPPED convention
        # elsewhere in the suite.
        return

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo138_3_tie_check.mscz',
            hp_trace_sink=trace
        )
    )

    os.remove(output_path)

    note_events = [
        e for e in trace
        if e.event_type in ('fretted_note', 'open_note')
    ]

    start = [
        e for e in note_events
        if e.measure == 1 and abs(e.beat - 3.0) < 0.01
    ]

    continuation = [
        e for e in note_events
        if e.measure == 2 and abs(e.beat - 0.0) < 0.01
    ]

    assert len(start) >= 1 and len(continuation) >= 1

    start_pitches = {(e.pitch, e.fret, e.string) for e in start}

    continuation_pitches = {
        (e.pitch, e.fret, e.string) for e in continuation
    }

    assert start_pitches == continuation_pitches, (
        f"Expected the tie continuation to still exactly "
        f"inherit the tie-start's own resolved result "
        f"({start_pitches}), unaffected by BO-138.3, got "
        f"{continuation_pitches}."
    )
