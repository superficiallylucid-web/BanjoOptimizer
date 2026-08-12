"""
tests/test_melody_box_analysis.py

Focused tests for melody_box_analysis.py -- diagnostic-only
melody box and hand-position measurement. No scoring or "best
choice" logic exists here to test; these confirm the
measurements themselves are correct.

Uses real Open G data for the realization tests (every
realization/position number below was verified directly against
fretboard.find_positions() before being written into an
assertion), synthetic Note/Harmony sequences for the box/
position-run tests, and the real Aureolin file for the final
end-to-end case -- skips gracefully if that file isn't present
locally, matching the pattern used elsewhere in this project.
"""

from pathlib import Path

from tunings import get_tunings

from models import Note, Harmony, Score

from parser import MuseScoreFile

from melody_box_analysis import (
    positions_covering_fret,
    realize_note,
    build_melody_boxes,
    compute_position_runs,
    analyze_melody_boxes
)


OPEN_G = get_tunings()["Open G"]

AUREOLIN_EADE_PATH = (
    Path(__file__).parent.parent / "Aureolin__Bm__aEADE__.mscz"
)


# ---------------------------------------------------------
# 1 -- a pitch with exactly one playable realization
# ---------------------------------------------------------
#
# E3 (midi 52) on Open G: only string 0 fret 2 reaches it
# within the tuning -- confirmed directly against
# fretboard.find_positions() before writing this test.

def test_pitch_with_one_realization():

    note = Note(midi=52, measure=1, beat=0.0)

    box_note = realize_note(note, OPEN_G)

    assert len(box_note.realizations) == 1

    assert box_note.realizations[0].string_index == 0

    assert box_note.realizations[0].fret == 2

    assert box_note.has_open_realization is False


# ---------------------------------------------------------
# 2 -- a pitch with multiple string/fret realizations
# ---------------------------------------------------------
#
# B3 (midi 59) on Open G: three realizations (string 0 fret 9,
# string 1 fret 4, string 2 fret 0).

def test_pitch_with_multiple_realizations():

    note = Note(midi=59, measure=1, beat=0.0)

    box_note = realize_note(note, OPEN_G)

    assert len(box_note.realizations) == 3

    frets = {r.fret for r in box_note.realizations}

    assert frets == {9, 4, 0}


# ---------------------------------------------------------
# 3 -- an open-string realization
# ---------------------------------------------------------
#
# G3 (midi 55) on Open G: string 0 fret 5, and string 1 open.

def test_open_string_realization():

    note = Note(midi=55, measure=1, beat=0.0)

    box_note = realize_note(note, OPEN_G)

    assert box_note.has_open_realization is True

    open_realizations = [
        r for r in box_note.realizations if r.fret == 0
    ]

    assert len(open_realizations) == 1

    assert open_realizations[0].string_index == 1


# ---------------------------------------------------------
# 4 & 5 -- a position sustaining several consecutive notes,
# then a note it can't play
# ---------------------------------------------------------
#
# E3(52) F3(53) F#3(54) G3(55) G#3(56), all on Open G string 0
# at frets 2,3,4,5,6 (G3 also has an open realization; G#3 also
# has fret 1 on string 1). Position 2 (frets 2-5) plays the
# first four notes, then breaks on G#3 (neither fret 6 on
# string 0 nor fret 1 on string 1 falls in [2,5]).

def _rising_run_box_notes():

    notes = [
        Note(midi=midi, measure=1, beat=float(i))
        for i, midi in enumerate([52, 53, 54, 55, 56])
    ]

    return [realize_note(note, OPEN_G) for note in notes]


def test_position_sustains_several_consecutive_notes_then_breaks():

    box_notes = _rising_run_box_notes()

    runs = compute_position_runs(box_notes)

    by_position = {r.position: r for r in runs}

    position_2 = by_position[2]

    assert position_2.notes_played == 4

    assert position_2.breaks_at_note_index == 4


# ---------------------------------------------------------
# 6 -- a position change with multiple possible destinations
# ---------------------------------------------------------

def test_position_change_multiple_destinations():

    box_notes = _rising_run_box_notes()

    runs = compute_position_runs(box_notes)

    by_position = {r.position: r for r in runs}

    position_2 = by_position[2]

    # G#3's realizations are fret 6 (string 0) and fret 1
    # (string 1) -- covered by positions {3,4,5,6} and {1}
    # respectively, five candidate destinations in total.
    assert position_2.destination_positions == {1, 3, 4, 5, 6}


# ---------------------------------------------------------
# 7 -- choosing a different string/fret for the same pitch
# lets the current position continue
# ---------------------------------------------------------
#
# Position 1 (frets 1-4) survives the WHOLE 5-note run above,
# specifically because G#3's string-1/fret-1 realization falls
# in [1,4] even though its string-0/fret-6 realization doesn't.

def test_alternate_realization_allows_position_to_continue():

    box_notes = _rising_run_box_notes()

    runs = compute_position_runs(box_notes)

    by_position = {r.position: r for r in runs}

    position_1 = by_position[1]

    assert position_1.notes_played == 5

    assert position_1.breaks_at_note_index is None


# ---------------------------------------------------------
# Box construction itself (not one of the 8 numbered
# scenarios, but the foundation they all depend on)
# ---------------------------------------------------------

def test_build_melody_boxes_splits_on_chord_boundaries():

    score = Score()

    score.add_harmony(
        Harmony(
            measure=1, root_pc=0, quality_code="", symbol="C",
            tones=[0, 4, 7], beat=0.0
        )
    )

    score.add_harmony(
        Harmony(
            measure=2, root_pc=7, quality_code="", symbol="G",
            tones=[7, 11, 2], beat=0.0
        )
    )

    for measure, beat in [(1, 0.0), (1, 1.0), (2, 0.0), (2, 1.0)]:

        score.add_note(Note(midi=64, measure=measure, beat=beat))

    boxes = build_melody_boxes(score)

    assert len(boxes) == 2

    first_harmony, first_next, first_notes = boxes[0]

    assert first_harmony.symbol == "C"

    assert first_next.symbol == "G"

    assert len(first_notes) == 2

    second_harmony, second_next, second_notes = boxes[1]

    assert second_harmony.symbol == "G"

    assert second_next is None

    assert len(second_notes) == 2


# ---------------------------------------------------------
# 8 -- a real Aureolin analysis case
# ---------------------------------------------------------

def test_real_aureolin_box_analysis():

    if not AUREOLIN_EADE_PATH.exists():

        print(
            "SKIPPED: Aureolin__Bm__aEADE__.mscz not found "
            "locally"
        )

        return

    p = MuseScoreFile(AUREOLIN_EADE_PATH)

    p.open()
    p.read_time_signature()
    p.read_melody_notes()
    p.read_harmonies(6)  # reference material

    a_eade = get_tunings()["A Modal Sawmill"]

    boxes = analyze_melody_boxes(p.score, a_eade)

    assert len(boxes) == 24

    first_box = boxes[0]

    assert first_box.chord.symbol == "Bm"

    assert first_box.next_chord.symbol == "Bm"

    assert len(first_box.notes) == 11

    by_position = {
        run.position: run for run in first_box.position_runs
    }

    # Confirmed directly by running the analyzer against this
    # exact file before writing this assertion.
    assert by_position[1].notes_played == 11

    assert by_position[1].breaks_at_note_index is None

    assert by_position[3].notes_played == 0

    assert by_position[3].breaks_at_note_index == 0
