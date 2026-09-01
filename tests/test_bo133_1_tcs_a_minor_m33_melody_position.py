"""
tests/test_bo133_1_tcs_a_minor_m33_melody_position.py

Focused regression test for BO-133.1: The Christmas Song, A
Minor tuning (symbol aEACE -- not to be confused with "A Modal
Sawmill", symbol aEADE, a different real tuning), measure 33
beat 4.5 (the player's own 1-indexed beat numbering; BO's
internal 0-indexed beat is 3.5).

Root cause, confirmed directly: all three real candidate
positions for this note (frets 15, 19, 22) fell into the single,
undifferentiated fretboard.best_position() ">12" fret-band tier,
so the "favor middle strings" bonus (+2 to +4) decided the
outcome instead of the real 7-fret spread between the best and
worst option. string_distance (the mechanism that could have
otherwise rewarded staying on the same string as the immediately
preceding, repeated-pitch run) was itself deliberately disabled
here per the existing BO-123 no-chord-anchor-plus-phrase gate.
The fix adds one new intermediate fret-band tier (13-17, value
0) to fretboard.best_position() -- a direct extension of the
same graduated structure already in place for lower frets, not a
new scoring mechanism.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import generate_tab_from_template

from chord_service import ChordService

from chord_library import ChordLibrary

import os


def test_tcs_a_minor_m33_beat_4_5_selects_string1_fret15():

    p = MuseScoreFile('scores/The Christmas Song.mscz')

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
            'templates/TAB_linked_Treble_Example.mscz', 'output',
            service, filename='bo133_1_test_output.mscz',
            hp_trace_sink=trace
        )
    )

    os.remove(output_path)

    note_events = [
        event for event in trace
        if event.event_type in ('fretted_note', 'open_note')
    ]

    # BO's own internal, 0-indexed beat -- the player's own
    # 1-indexed "beat 4.5" minus 1.
    matches = [
        event for event in note_events
        if event.measure == 33 and abs(event.beat - 3.5) < 0.01
    ]

    assert len(matches) == 1, (
        f"Expected exactly one melody note at TCS measure 33, "
        f"beat 3.5 (internal) -- found {len(matches)}."
    )

    selected = matches[0]

    assert selected.pitch == 79, (
        f"Expected the real melody pitch (G5, midi 79) at this "
        f"beat, got midi={selected.pitch}."
    )

    # find_positions()/trace's own string index (0-indexed,
    # BO-internal ascending pitch): index 3 = BO-internal string
    # 4 = the player's own string 1, per the established
    # translation (BO-132.2). fret 15 is the player's own "1-15".
    assert selected.fret == 15 and selected.string == 3, (
        f"Expected the target position (player's '1-15', "
        f"internal string_index=3/fret=15), got "
        f"string_index={selected.string}/fret={selected.fret} "
        f"(player's own bad position '3-22' would be "
        f"string_index=1/fret=22)."
    )
