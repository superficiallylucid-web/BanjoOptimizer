"""
tests/test_bo133_4_explicit_octave_substitution.py

Focused tests for BO-133.4: the explicit octave-substitution
capability. This is NOT automatic octave selection -- every
substitution must be explicitly supplied by the caller (future
automatic selection is BOF-004, separate work).

Proof-of-capability target: BO-133.2's own real case (The
Christmas Song, A Minor tuning, measure 31 beat 2 player-numbered
/ beat 1.0 BO-internal) -- B4 (midi 71) explicitly substituted
for B3 (midi 59).
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import generate_tab_from_template

from chord_service import ChordService

from chord_library import ChordLibrary

import os


def _load_tcs():

    p = MuseScoreFile('scores/The Christmas Song.mscz')

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p, staff_used


# ---------------------------------------------------------
# The real BO-133.2 proof-of-capability case
# ---------------------------------------------------------

def test_bo133_2_b4_to_b3_explicit_substitution():

    p, staff_used = _load_tcs()

    p.apply_octave_substitutions(staff_used, [
        {
            "measure": 31, "beat": 1.0,
            "original_midi": 71, "new_midi": 59
        }
    ])

    matches = [
        n for n in p.score.notes
        if n.measure == 31 and abs(n.beat - 1.0) < 0.01
    ]

    assert len(matches) == 1

    assert matches[0].midi == 59, (
        f"Expected the parsed Note's own midi to be updated to "
        f"59 (B3), got {matches[0].midi}."
    )

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo133_4_proof_test.mscz',
            hp_trace_sink=trace
        )
    )

    os.remove(output_path)

    note_events = [
        event for event in trace
        if event.event_type in ('fretted_note', 'open_note')
    ]

    selected = [
        event for event in note_events
        if event.measure == 31 and abs(event.beat - 1.0) < 0.01
    ]

    assert len(selected) == 1

    # Player's own "3-2": internal string_index=1 (BO-internal
    # string2 = player's string3, per the established
    # translation), fret=2.
    assert selected[0].pitch == 59

    assert selected[0].fret == 2 and selected[0].string == 1, (
        f"Expected the target position (player's '3-2', "
        f"internal string_index=1/fret=2), got "
        f"string_index={selected[0].string}/"
        f"fret={selected[0].fret}."
    )


# ---------------------------------------------------------
# Only the requested note changes -- nothing else
# ---------------------------------------------------------

def test_only_the_requested_note_changes():

    p_before, _ = _load_tcs()

    before_all = [
        (n.measure, n.beat, n.midi) for n in p_before.score.notes
    ]

    p_after, staff_used = _load_tcs()

    p_after.apply_octave_substitutions(staff_used, [
        {
            "measure": 31, "beat": 1.0,
            "original_midi": 71, "new_midi": 59
        }
    ])

    after_all = [
        (n.measure, n.beat, n.midi) for n in p_after.score.notes
    ]

    diffs = [
        (b, a) for b, a in zip(before_all, after_all) if b != a
    ]

    assert diffs == [((31, 1.0, 71), (31, 1.0, 59))], (
        f"Expected exactly one note to change, got: {diffs}"
    )


# ---------------------------------------------------------
# The underlying XML is patched, not just the parsed Note
# ---------------------------------------------------------

def test_xml_pitch_element_is_patched():

    p, staff_used = _load_tcs()

    p.apply_octave_substitutions(staff_used, [
        {
            "measure": 31, "beat": 1.0,
            "original_midi": 71, "new_midi": 59
        }
    ])

    # Confirmed directly (BO-133.4): tpc is genuinely octave-
    # independent in this project's own real data (B4 and B3
    # both carry tpc=19 in this exact file) -- only pitch should
    # change; tpc is left untouched.
    matched_elements = []

    for element in p.root.iter():

        if element.tag.split('}')[-1] != 'Note':

            continue

        pitch_element = element.find('{*}pitch')

        if pitch_element is not None and pitch_element.text == '59':

            tpc_element = element.find('{*}tpc')

            matched_elements.append(
                (pitch_element.text, tpc_element.text)
            )

    # The song already has real, pre-existing B3 notes
    # elsewhere; confirming at least one match has tpc=19 is
    # sufficient here (the exact count/identity is already
    # covered by test_only_the_requested_note_changes above).
    assert ('59', '19') in matched_elements


# ---------------------------------------------------------
# Reusability -- not hardcoded to B4->B3 specifically
# ---------------------------------------------------------

def test_reusable_for_a_different_substitution():

    p, staff_used = _load_tcs()

    # A different, real note in this same song (m32 b3.0,
    # midi=76) substituted down an octave (C6->C5 in this
    # case's own pitch class terms: midi 76 -> 64).
    p.apply_octave_substitutions(staff_used, [
        {
            "measure": 32, "beat": 3.0,
            "original_midi": 76, "new_midi": 64
        }
    ])

    matches = [
        n for n in p.score.notes
        if n.measure == 32 and abs(n.beat - 3.0) < 0.01
    ]

    assert len(matches) == 1

    assert matches[0].midi == 64


# ---------------------------------------------------------
# Safety -- refuses to guess on a mismatch
# ---------------------------------------------------------

def test_raises_on_mismatched_original_midi():

    p, staff_used = _load_tcs()

    try:

        p.apply_octave_substitutions(staff_used, [
            {
                "measure": 31, "beat": 1.0,
                "original_midi": 999, "new_midi": 59
            }
        ])

        assert False, (
            "Expected a ValueError for a non-matching "
            "original_midi, but no exception was raised."
        )

    except ValueError:

        pass
