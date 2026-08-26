"""
stroke_cycle.py

BO-81 -- the rhythmic clawhammer stroke cycle, established by the
BO-77 through BO-80 investigation chain.

The physical clawhammer motion alternates a down/finger stroke and
a pull/thumb stroke, continuously, in musical time -- independent
of note repetition, rests, sustained-note duration, or chord
presence. A rest occupies its own stroke position(s) without an
attack; a sustained note occupies its own duration's worth of
stroke positions without repeated attacks. Confirmed real
motivating evidence (BO-75/76): Cousin Sally Brown, C Standard --

    G4 - rest - G4 - G4   ->  finger - rest/pull - finger - thumb
    G4 - G4 - G4          ->  finger - thumb - finger

both fall out of ONE continuous eighth-note-unit cycle with no
run-length or repeated-note special-casing at all (confirmed
directly: BO-77's own investigation).

This module is deliberately pure and isolated, mirroring
hand_position.py's own separation -- it knows nothing about
scoring, HP, chords, or the existing _sort_key. It answers exactly
two questions: (1) what stroke phase does a given event's own
onset fall on, and (2) given that phase, which of a candidate
list is stroke-compatible. Everything else (which compatible
candidate is actually best) remains entirely the existing,
unmodified selection machinery's job.
"""

from collections import namedtuple


# One eighth note = one stroke unit, for ordinary (non-tuplet)
# passages -- confirmed by BO-77/78's own direct fit against the
# real CSB evidence above.
EIGHTH_NOTE_BEATS = 0.5

# BO-63/81 -- the 5th string is the only stroke-compatibility
# distinction available without drop-thumb classification (BO-80's
# own explicit, deliberate scope limit: "do not attempt to
# determine whether a thumb stroke is specifically a 5th-string
# thumb stroke or a drop-thumb stroke" -- that remains future work).
FIFTH_STRING_INDEX = 4


StrokePhaseEntry = namedtuple(
    "StrokePhaseEntry", ["phase", "units_elapsed"]
)


def compute_stroke_phase_by_event_id(ordered_events):
    """
    BO-81 -- walks ordered_events (a flat list of note/rest event
    dicts, each with "duration" and "tuplet_scale" -- BO-81's own
    small parser/extraction addition -- in the exact document
    order they occur, harmony markers already excluded by the
    caller) and returns a dict mapping id(event) -> StrokePhaseEntry
    for every event, giving that event's own ONSET stroke phase
    ("down" or "pull") and the cumulative stroke units elapsed at
    that onset.

    The cycle's own anchor (BO-81's own explicit, deliberate first-
    implementation choice, per the investigation's own finding that
    no existing phrase/grouping concept exists to reuse -- BO-79/80)
    is simply the first event in ordered_events: units_elapsed
    starts at 0.0 there, always an onset "down" stroke.

    Tuplet handling (BO-80's own established musical decision: the
    hand speeds up to match the tuplet subdivision, confirmed real
    via The Christmas Song's own triplet passages): an event whose
    own tuplet_scale != 1.0 advances the cycle by exactly ONE
    stroke unit regardless of its own beat-length duration -- each
    note within a tuplet gets its own down/pull assignment at the
    tuplet's own accelerated pace, rather than being measured
    against the surrounding eighth-note grid at all. A non-tuplet
    event advances the cycle by its own duration, in eighth-note
    units (duration / EIGHTH_NOTE_BEATS) -- this is what lets a
    rest or a sustained note occupy MULTIPLE stroke positions
    without any attack at all (BO-78's own confirmed refinement:
    "a rest/sustained note occupies the same stroke positions a
    note of equal duration would").
    """

    phase_by_id = {}

    units_elapsed = 0.0

    for event in ordered_events:

        phase = (
            "down" if round(units_elapsed) % 2 == 0 else "pull"
        )

        phase_by_id[id(event)] = StrokePhaseEntry(
            phase=phase, units_elapsed=units_elapsed
        )

        tuplet_scale = event.get("tuplet_scale", 1.0)

        if tuplet_scale != 1.0:

            units_elapsed += 1.0

        else:

            units_elapsed += (
                event["duration"] / EIGHTH_NOTE_BEATS
            )

    return phase_by_id


def filter_by_stroke_phase(positions, expected_phase):
    """
    BO-81 -- given positions (the same list of candidate dicts
    find_positions()/best_position() already produce, each with
    "string"/"fret") and an expected_phase ("down" or "pull"),
    returns only the stroke-compatible subset.

    First-implementation scope (BO-80's own explicit, deliberate
    limit): the only stroke-role distinction available without
    drop-thumb classification is string index -- the OPEN 5th
    string (FIFTH_STRING_INDEX, fret 0 -- confirmed real during
    BO-81's own implementation: the 5th string can also be
    FRETTED, e.g. reaching an adjacent pitch, exactly like any
    other string, and a fretted 5th-string note is a normal
    fretting-hand note, not a thumb-on-an-open-string stroke at
    all) is the sole "pull/thumb" candidate; every other position
    -- including a fretted 5th-string one -- is "down/finger".
    This does NOT duplicate or replace open_string_bonus (a
    different, pre-existing, already-validated mechanism) -- it
    only ever narrows WHICH candidates reach that and every other
    existing scoring mechanism unchanged; it never scores or
    prefers among them itself.

    Mandatory fallback (BO-79/80/81's own explicit, repeated
    requirement): if no candidate matches expected_phase, returns
    positions completely unfiltered. The rhythmic model must never
    be able to make a note unplayable -- confirmed as essential
    given not every melody pitch has a real 5th-string realization
    at all, let alone one compatible with a specific phase.
    """

    if expected_phase == "pull":

        compatible = [
            p for p in positions
            if p["string"] == FIFTH_STRING_INDEX
            and p["fret"] == 0
        ]

    else:

        compatible = [
            p for p in positions
            if not (
                p["string"] == FIFTH_STRING_INDEX
                and p["fret"] == 0
            )
        ]

    return compatible if compatible else positions
