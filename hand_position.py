"""
hand_position.py

BO-59: a persistent Hand Position (HP) state machine, formally
specified and validated against real BO output across 4 real
songs/tunings before this implementation (see the BO-59
investigation's own report for the full specification, mechanism
map, and real-score trace this code implements).

HP represents the actual physical position of the fretting hand,
as STATE carried forward through a score in document order -- not
a theoretical per-note window recomputed independently each time.
There is no HP before the first fretted note or chord; open
strings never establish or move it; a chord/FD always establishes
a new HP (even one that overlaps the previous one); a fretted
melody note either stays within the current HP (unchanged) or
lies outside it -- above OR below -- and establishes a new HP
starting at its own fret, with no distinction between the two
directions.

This module is deliberately STATE-MACHINE ONLY: it computes and
represents HP as an observable, testable value. Per BO-59's own
explicit scope, it does not yet feed into or influence melody/
chord candidate scoring anywhere -- that is future work.
"""

from collections import namedtuple

from playing_model import _chord_working_fret


HandPosition = namedtuple("HandPosition", ["low", "high"])


def chord_hp_span(shape_values):
    """
    BO-59 -- the (low, high) HandPosition a chord/FD establishes,
    reusing playing_model._chord_working_fret() UNMODIFIED for
    the low end (per BO-59's own requirement to reuse existing
    infrastructure rather than duplicate it), and computing the
    high end from the shape's own real fretted span.

    A normal (<=3-fret span) shape gets a normal 4-fret HP
    (low, low+3). A shape whose own real fretted span exceeds 3
    frets (confirmed real, though not exercised by any of the 4
    songs used in the BO-59 investigation -- every real FD
    span in that dataset was <=3) widens the HP to cover the
    whole legitimate span, per BO-59's own explicit 5-fret
    exception: high = low + max(3, span).

    Returns None for an all-open/muted shape (no fretted
    position at all to establish an HP from) -- matches
    _chord_working_fret()'s own None case exactly.
    """

    low = _chord_working_fret(shape_values)

    if low is None:

        return None

    fretted_values = [
        f for f in shape_values if f is not None and f > 0
    ]

    span = max(fretted_values) - min(fretted_values)

    return HandPosition(low, low + max(3, span))


def melody_note_hp(current_hp, fret):
    """
    BO-59 -- the new HP state after a single fretted melody note
    (fret > 0) is played, given the current_hp (a HandPosition or
    None).

    Rules (see this module's own docstring above for the full
    specification):
    - current_hp is None -> establishes (fret, fret+3).
    - fret is within [current_hp.low, current_hp.high] -> HP
      unchanged (returns current_hp itself).
    - fret is outside current_hp, in EITHER direction -> a new
      HP (fret, fret+3). There is no separate "below" case: the
      only condition that matters is "outside", not "outside and
      going down" -- confirmed explicitly correct per the BO-59
      specification's own clarification.

    fret == 0 (open string) is NOT a valid input here -- open
    strings never establish or change HP at all (see
    open_string_hp() below); this function is for fretted notes
    only.
    """

    if current_hp is None:

        return HandPosition(fret, fret + 3)

    if current_hp.low <= fret <= current_hp.high:

        return current_hp

    return HandPosition(fret, fret + 3)


def open_string_hp(current_hp):
    """
    BO-59 -- an open-string note NEVER establishes or moves HP,
    under any circumstance, including as the very first event in
    a score (current_hp stays None) and when sandwiched between
    two different fretted regions (confirmed real: Cousin Sally
    Brown / Double C, measures 7-8, where an open D4 between an
    E4 at one HP and a C4 at a different one leaves the HP
    exactly as the preceding E4 left it). Returns current_hp
    completely unchanged -- this function exists for the calling
    code's own explicit readability, not because it does anything
    beyond identity.
    """

    return current_hp


def nearest_new_hp(current_hp, candidate_frets):
    """
    BO-59 -- among several fretted candidates that would ALL lie
    outside current_hp (each therefore establishing its own new
    HP), returns the one requiring the smallest hand movement:
    the candidate fret whose own new HP (fret, fret+3) has a
    starting fret closest to current_hp's own starting fret.

    distance = abs(candidate_fret - current_hp.low) -- exactly
    the metric specified in the finalized BO-59 specification.

    This is a movement-PREFERENCE value for a caller to weigh
    alongside other, existing quality/scoring factors -- it does
    not by itself decide anything, and this function does not
    consult or override note quality, phrase coverage, or any
    other existing scoring mechanism at all (per BO-59's own
    explicit scope: "do not allow it to override substantially
    better note/chord realizations").

    If current_hp is None, every candidate is equally "nearest"
    (there is nothing established yet to measure distance from);
    returns the first candidate in that case, since no real
    distance comparison is meaningful.

    candidate_frets must be non-empty.
    """

    if current_hp is None:

        return candidate_frets[0]

    return min(
        candidate_frets,
        key=lambda fret: abs(fret - current_hp.low)
    )


HpTraceEntry = namedtuple(
    "HpTraceEntry",
    [
        "event_index", "measure", "beat", "event_type",
        "pitch", "fret", "string", "chord_lowest_fret",
        "hp_before", "hp_after", "transition"
    ]
)
"""
BO-59 -- one diagnostic record per event, for real-generation
inspection/testing ONLY (see generate_tab_from_template()'s own
hp_trace_sink parameter). Never consulted by any production
selection logic -- purely observational.

event_type: "open_note" | "fretted_note" | "chord" | "rest"
transition: "established_first" | "unchanged" | "established_new"
    | "chord_reset" | "open_string" | "no_note"
    (a rest, or a chord/FD with no fretted position at all,
    records "no_note" -- HP genuinely does not change, but there
    is no fret/chord to describe the transition in terms of.)
pitch/fret/string: populated for note events, None for chords.
chord_lowest_fret: populated for chord events, None for notes.
"""
