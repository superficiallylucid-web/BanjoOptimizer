"""
tests/test_bo144_2_incoming_shape_temporal_limit.py

Focused tests for BO-144.2: incoming_shape (BO-54's own "which
chord immediately precedes this one" continuity signal) now
only contributes to transition-anchor scoring when the elapsed
musical time from the incoming chord's own onset to the current
harmony's own onset is <= MAX_INCOMING_SHAPE_DISTANCE_BEATS
(4.0). Beyond that, selection behaves exactly as though
incoming_shape were None.

Confirmed real, not chosen arbitrarily (BO-144.1's own
investigation): every real BO-54 use case (The Christmas Song's
own C -> Cmaj7 transitions) occurs at exactly 1.0 beat; the
real, problematic Alizarin cases this exists to fix occur at
5.0 and 6.5 beats.
"""

import sys

sys.path.insert(0, '.')

sys.path.insert(0, 'tests')

from score_generator import (
    _select_chord_shape_for_harmony, _beats_between
)

from chord_service import ChordService, MAX_INCOMING_SHAPE_DISTANCE_BEATS

from chord_library import ChordLibrary

from tunings import get_tunings

from models import Harmony, Note

from music import chord_tones

from test_bo49_playing_model_chord_quality import _load, _analyzer


def _gmaj7_harmony_and_melody():

    tuning = get_tunings()['Open G']

    harmony = Harmony(
        measure=3, root_pc=7, quality_code='maj7',
        symbol='Gmaj7', tones=chord_tones(7, 'maj7'), beat=0.0
    )

    melody_note = Note(
        midi=55, measure=3, beat=0.0, duration=1.0, voice=1
    )

    return tuning, harmony, melody_note


# ---------------------------------------------------------
# 1 -- below cutoff: continuity applies (real, confirmed
# Alizarin shapes -- 0005 -> 4005)
# ---------------------------------------------------------

def test_below_cutoff_continuity_applies():

    tuning, harmony, melody_note = _gmaj7_harmony_and_melody()

    service = ChordService(ChordLibrary())

    shape, _, _ = _select_chord_shape_for_harmony(
        harmony, tuning, service, melody_notes=[melody_note],
        next_harmony=None, incoming_shape='0005',
        incoming_shape_elapsed_beats=1.0
    )

    assert shape.shape == '4005', (
        f"Expected continuity to apply at 1.0 beat (well below "
        f"the {MAX_INCOMING_SHAPE_DISTANCE_BEATS}-beat cutoff), "
        f"got {shape.shape!r}."
    )


# ---------------------------------------------------------
# 2 -- exactly at cutoff: continuity still applies (the
# boundary is <=, not <)
# ---------------------------------------------------------

def test_exactly_at_cutoff_continuity_still_applies():

    tuning, harmony, melody_note = _gmaj7_harmony_and_melody()

    service = ChordService(ChordLibrary())

    shape, _, _ = _select_chord_shape_for_harmony(
        harmony, tuning, service, melody_notes=[melody_note],
        next_harmony=None, incoming_shape='0005',
        incoming_shape_elapsed_beats=(
            MAX_INCOMING_SHAPE_DISTANCE_BEATS
        )
    )

    assert shape.shape == '4005', (
        f"Expected continuity to still apply exactly AT the "
        f"cutoff ({MAX_INCOMING_SHAPE_DISTANCE_BEATS} beats, "
        f"the documented <= boundary), got {shape.shape!r}."
    )


# ---------------------------------------------------------
# 3 -- beyond cutoff: continuity no longer applies
# ---------------------------------------------------------

def test_beyond_cutoff_continuity_does_not_apply():

    tuning, harmony, melody_note = _gmaj7_harmony_and_melody()

    service = ChordService(ChordLibrary())

    shape, _, _ = _select_chord_shape_for_harmony(
        harmony, tuning, service, melody_notes=[melody_note],
        next_harmony=None, incoming_shape='0005',
        incoming_shape_elapsed_beats=(
            MAX_INCOMING_SHAPE_DISTANCE_BEATS + 0.01
        )
    )

    assert shape.shape == '0004', (
        f"Expected continuity to no longer apply just beyond "
        f"the {MAX_INCOMING_SHAPE_DISTANCE_BEATS}-beat cutoff, "
        f"got {shape.shape!r}."
    )


# ---------------------------------------------------------
# _beats_between() itself -- verified directly against both
# real, confirmed cases
# ---------------------------------------------------------

def test_beats_between_matches_real_alizarin_case():

    # G chord (m1 b1.5) -> Gmaj7 #2 onset (m3 b0.0), confirmed
    # real, BO-144.1's own investigation.
    assert _beats_between(1, 1.5, 3, 0.0, '4/4') == 6.5


def test_beats_between_matches_real_bo54_case():

    # C (m2 b0.0) -> Cmaj7 (m2 b1.0), confirmed real, The
    # Christmas Song's own original BO-54 use case.
    assert _beats_between(2, 0.0, 2, 1.0, '4/4') == 1.0


# ---------------------------------------------------------
# 4/5/6 -- real Alizarin cases, end to end
# ---------------------------------------------------------

def _load_alizarin_gmaj7_results():

    import score_generator as sg

    original_select = sg._select_chord_shape_for_harmony

    captured = {}

    def patched(harmony, tuning, chord_service, melody_notes=None,
                next_harmony=None, incoming_shape=None,
                incoming_shape_elapsed_beats=None):

        result = original_select(
            harmony, tuning, chord_service,
            melody_notes=melody_notes, next_harmony=next_harmony,
            incoming_shape=incoming_shape,
            incoming_shape_elapsed_beats=(
                incoming_shape_elapsed_beats
            )
        )

        if harmony.symbol == 'Gmaj7':

            key = (harmony.measure, harmony.beat)

            if key not in captured:

                captured[key] = result[0].shape if result[0] else None

        return result

    sg._select_chord_shape_for_harmony = patched

    try:

        p = _load('scores/Alizarin.mscz')

        p.read_time_signature()

        staff_used = p.read_melody_notes()

        p.estimate_key()

        p.read_harmonies(staff_used)

        tuning = get_tunings()['Open G']

        service = ChordService(ChordLibrary())

        import os

        output_path, _, _, _ = sg.generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo144_2_test_alizarin.mscz'
        )

        os.remove(output_path)

    finally:

        sg._select_chord_shape_for_harmony = original_select

    return captured


def test_real_alizarin_all_four_gmaj7_produce_0004():

    import os

    if not os.path.exists('scores/Alizarin.mscz'):

        # Real fixture not present in this environment -- skip
        # gracefully rather than fail on an absent file, matching
        # this project's own existing convention elsewhere.
        return

    results = _load_alizarin_gmaj7_results()

    assert len(results) == 4, (
        f"Expected 4 real Gmaj7 occurrences, found {len(results)}."
    )

    for (measure, beat), shape in results.items():

        assert shape == '0004', (
            f"Expected m{measure} b{beat} Gmaj7 to select '0004' "
            f"once its own incoming continuity is correctly "
            f"excluded as too old, got {shape!r}."
        )


# ---------------------------------------------------------
# 7 -- real BO-54 Christmas Song case: unchanged
# ---------------------------------------------------------

def test_real_christmas_song_cmaj7_unchanged():

    import os

    if not os.path.exists('scores/The Christmas Song.mscz'):

        return

    import score_generator as sg

    original_select = sg._select_chord_shape_for_harmony

    captured = {}

    def patched(harmony, tuning, chord_service, melody_notes=None,
                next_harmony=None, incoming_shape=None,
                incoming_shape_elapsed_beats=None):

        result = original_select(
            harmony, tuning, chord_service,
            melody_notes=melody_notes, next_harmony=next_harmony,
            incoming_shape=incoming_shape,
            incoming_shape_elapsed_beats=(
                incoming_shape_elapsed_beats
            )
        )

        if harmony.symbol == 'Cmaj7':

            key = (harmony.measure, harmony.beat)

            if key not in captured:

                captured[key] = result[0].shape if result[0] else None

        return result

    sg._select_chord_shape_for_harmony = patched

    try:

        p = _load('scores/The Christmas Song.mscz')

        tuning = get_tunings()['A Modal Sawmill']

        service = ChordService(ChordLibrary())

        import os as os_module

        output_path, _, _, _ = sg.generate_tab_from_template(
            p, tuning, 2,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo144_2_test_xmas.mscz'
        )

        os_module.remove(output_path)

    finally:

        sg._select_chord_shape_for_harmony = original_select

    assert len(captured) == 3, (
        f"Expected 3 real Cmaj7 occurrences, found {len(captured)}."
    )

    for (measure, beat), shape in captured.items():

        assert shape == '0(10)98', (
            f"Expected the real, original BO-54 Cmaj7 result "
            f"(0(10)98) to remain unchanged at m{measure} "
            f"b{beat}, got {shape!r}."
        )
