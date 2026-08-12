"""
melody_box_analysis.py

Diagnostic-only measurement of "melody boxes" -- the melody
passage between one chord occurrence and the next -- and which
strict four-fret hand positions can play through that passage
without moving. This is measurement infrastructure only: no
scoring, no "best" realization or position chosen, and nothing
here affects tuning recommendations or chord ranking.

MUSICAL BOX DEFINITION (do not reinterpret elsewhere):
A box begins at the melody note occurring at the same musical
position as a chord occurrence, continues through every
subsequent melody note, and ends with the last melody note
immediately before the NEXT chord occurrence. The next chord
begins the next box. The score's last chord's box runs through
the end of the melody.

HAND POSITION MODEL (strict four-fret, first implementation):
A position is identified by its index-finger fret N, covering
frets N through N+3 (middle=N+1, ring=N+2, pinky=N+3). A
fretted note is only playable in position N if its fret falls
in [N, N+3] -- no stretches, no thumb-over, no five-fret
reaches; that's a deliberate simplification for this first
version, not an oversight. Open strings (fret 0) are playable
from ANY position and never force a position change.

Reuses existing primitives throughout -- no new pitch-to-fret
theory or chord logic is added here:
- fretboard.find_positions() for every pitch's realizations
- Score.notes / Score.harmonies (already-parsed, including real
  beat tracking -- see parser.read_staff_notes()/
  read_harmonies())
- ChordService.select_shape_for_melody() for a box's starting
  chord shape, when a chord service is supplied (optional --
  boxes can be built and analyzed without one)
"""

from fretboard import find_positions

from music import (
    midi_to_note_name,
    quality_code_to_display_name,
    pitch_name
)

from models import (
    BoxMelodyNote,
    NoteRealization,
    PositionRun,
    MelodyBox
)


def positions_covering_fret(fret):
    """
    Which four-fret hand positions (identified by their index-
    finger fret) can play a given fretted note. fret must be
    greater than 0 -- open strings are handled separately
    (playable from any position, not governed by this).

    Position N covers frets N..N+3. A fret F is covered by
    every N from max(1, F-3) through F, inclusive.
    """

    if fret <= 0:

        return set()

    return set(range(max(1, fret - 3), fret + 1))


def realize_note(note, tuning):
    """
    Build a BoxMelodyNote for one melody Note: every string/
    fret realization (via fretboard.find_positions(), reused
    exactly as-is), whether any of them is an open string, and
    which hand positions its fretted realizations reach.
    """

    open_notes = tuning.notes[1:]

    raw_positions = find_positions(note.midi, open_notes)

    realizations = [
        NoteRealization(
            string_index=p["string"],
            fret=p["fret"]
        )
        for p in raw_positions
    ]

    has_open_realization = any(
        r.fret == 0 for r in realizations
    )

    fretted_positions = set()

    for r in realizations:

        if r.fret > 0:

            fretted_positions |= positions_covering_fret(r.fret)

    return BoxMelodyNote(
        midi=note.midi,
        measure=note.measure,
        beat=note.beat,
        realizations=realizations,
        has_open_realization=has_open_realization,
        fretted_positions=fretted_positions
    )


def build_melody_boxes(score):
    """
    Split a score's melody into boxes, one per chord occurrence
    (see module docstring for the exact box definition). Boxes
    contain plain Note objects at this stage -- realize_note()
    and analyze_box() add the fretboard/position analysis on
    top, kept separate so this function only ever depends on
    Score's existing data, nothing tuning-specific.

    Returns a list of (harmony, next_harmony_or_None, notes)
    tuples, in score order.
    """

    harmonies_sorted = sorted(
        score.harmonies, key=lambda h: (h.measure, h.beat)
    )

    notes_sorted = sorted(
        score.notes, key=lambda n: (n.measure, n.beat)
    )

    boxes = []

    for index, harmony in enumerate(harmonies_sorted):

        start = (harmony.measure, harmony.beat)

        if index + 1 < len(harmonies_sorted):

            next_harmony = harmonies_sorted[index + 1]

            end = (next_harmony.measure, next_harmony.beat)

        else:

            next_harmony = None

            end = None

        box_notes = [
            note for note in notes_sorted
            if (note.measure, note.beat) >= start
            and (
                end is None
                or (note.measure, note.beat) < end
            )
        ]

        boxes.append((harmony, next_harmony, box_notes))

    return boxes


def compute_position_runs(box_notes):
    """
    For a box's list of BoxMelodyNote, determine every
    candidate starting hand position (the union of every note's
    fretted_positions -- positions capable of playing at least
    one note in the box via a fretted realization) and how far
    each one can continue before it can no longer realize the
    next note.

    A position only ever breaks on a note with NO open
    realization -- an open note is always playable, so it can
    never be the reason a position fails. This falls directly
    out of the model rather than needing a special case.

    Returns a list of PositionRun, one per candidate starting
    position. Empty if the box has no fretted notes at all.
    """

    if not box_notes:

        return []

    candidate_positions = set()

    for note in box_notes:

        candidate_positions |= note.fretted_positions

    runs = []

    for position in sorted(candidate_positions):

        notes_played = 0

        breaks_at_note_index = None

        breaking_realizations = []

        destination_positions = set()

        for note_index, note in enumerate(box_notes):

            playable = (
                note.has_open_realization
                or position in note.fretted_positions
            )

            if playable:

                notes_played += 1

                continue

            breaks_at_note_index = note_index

            breaking_realizations = [
                r for r in note.realizations if r.fret > 0
            ]

            destination_positions = set(
                note.fretted_positions
            )

            break

        runs.append(
            PositionRun(
                position=position,
                notes_played=notes_played,
                breaks_at_note_index=breaks_at_note_index,
                breaking_realizations=breaking_realizations,
                destination_positions=destination_positions
            )
        )

    return runs


def analyze_melody_boxes(score, tuning, chord_service=None):
    """
    Build and fully analyze every melody box in a score against
    one tuning: realizations, candidate hand positions, and
    where each one breaks.

    chord_service is optional. When supplied, each box's
    starting chord shape is attached via the EXISTING
    select_shape_for_melody() (root/quality from the box's own
    Harmony, melody note from the box's own first note) -- not
    a new hand-position model for the chord itself. When a box
    has no melody note to select against (rare -- a chord with
    an empty box), or chord_service is None, chord_shape stays
    None; this is a known limitation, not resolved here (see
    module docstring).

    Returns a list of MelodyBox, in score order.
    """

    raw_boxes = build_melody_boxes(score)

    result = []

    for harmony, next_harmony, notes in raw_boxes:

        box_notes = [
            realize_note(note, tuning) for note in notes
        ]

        position_runs = compute_position_runs(box_notes)

        chord_shape = None

        if chord_service is not None and box_notes:

            root_name = pitch_name(harmony.root_pc)

            quality_display = quality_code_to_display_name(
                harmony.quality_code
            )

            if quality_display is not None:

                melody_note_name = midi_to_note_name(
                    box_notes[0].midi
                )

                selection = chord_service.select_shape_for_melody(
                    tuning,
                    root_name,
                    harmony.root_pc,
                    harmony.quality_code,
                    quality_display,
                    melody_note_name
                )

                chord_shape = selection.selected_shape

        result.append(
            MelodyBox(
                chord=harmony,
                next_chord=next_harmony,
                notes=box_notes,
                chord_shape=chord_shape,
                position_runs=position_runs
            )
        )

    return result
