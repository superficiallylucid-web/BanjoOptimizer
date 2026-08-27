"""
stroke_cycle.py

BO-88 -- the clawhammer ATTACK SEQUENCE, established by the BO-85
through BO-87 investigation chain, replacing BO-81's original
continuous-elapsed-time model.

BO-84/85 found that BO-81's original model -- dividing all elapsed
musical time into fixed eighth-note down/pull positions -- was
wrong: it conflated two genuinely separate things, the hand's own
continuous rhythmic motion versus which melody notes are actually
eligible to be classified as a clawhammer attack at all.

The confirmed model (BO-87, validated directly against the real
"Rhythmic Clawhammer Stroke Cycle" TAB fixture, matching 7 of its 8
real measures exactly -- see the one known, documented exception
below) is an ORDINAL SEQUENCE, not a phase clock:

    down -> pull -> down -> pull -> ...

- A note whose own duration is > 1 beat is NOT eligible for attack
  classification at all, and TERMINATES any currently-running
  sequence. The very next eligible attack after it starts a fresh
  sequence at "down". Confirmed real (M3, M4, M6): a half note
  never continues an established sequence and never receives a
  forced role of its own.

- The sequence's own RATE is established by whichever notes begin
  it -- eighth notes start a fast sequence (M5, M6's own opening),
  bare quarter notes (nothing faster nearby) start their own,
  slower sequence (M1) -- confirmed real, both directions. Once
  established, subsequent eligible notes take the next ordinal
  slot regardless of their own individual duration (M6's own
  quarter note continues an eighth-established sequence at "down",
  rather than restarting its own slower cycle) -- this is why the
  model is ordinal (position-in-sequence), not time-based at all.

- A rest occupies its own slot in the sequence WITHOUT producing
  an attack, and does NOT terminate the sequence -- confirmed real
  (M2: down - rest/pull - down - pull, matching the established
  CSB G4-rest-G4-G4 -> finger-rest-finger-thumb case exactly).

- An ineligible (>1 beat) note is not merely "excluded from attack
  classification" in some soft sense -- it is completely UNCON-
  STRAINED by this mechanism. It may still end up on the 5th
  string for entirely separate, pre-existing reasons (open_string_
  bonus and similar existing mechanisms, untouched by this
  module) -- confirmed real: M4's two half notes both land
  fretted, while M6's single half note independently lands on the
  5th string, even though neither is rhythmically constrained at
  all. This is deliberate, not a gap: rhythmic attack classifi-
  cation and ordinary candidate selection remain genuinely
  separate concerns.

KNOWN, DOCUMENTED DISCREPANCY (measure 8 of the real TAB fixture):
after two consecutive ineligible dotted-half notes (1.5 beats
each), the real fixture's own third note (an eligible quarter)
is "pull" -- this implementation, matching every other real
measure, predicts "down" (the first eligible attack after any
ineligible note always starts a fresh sequence at down). No
consistent rule reconciling this single case with the other 7
(especially M3, which shows the analogous single-ineligible-note
-> next-attack-is-down pattern clearly) was identified during
BO-88's own investigation. Flagged explicitly rather than special-
cased around.
"""

from collections import namedtuple


# BO-87/88 -- a note (or rest) with duration greater than this many
# beats is not eligible for clawhammer attack classification at
# all, and terminates any currently-running attack sequence.
ATTACK_ELIGIBILITY_THRESHOLD_BEATS = 1.0

# BO-63/81 -- the 5th string is the only stroke-compatibility
# distinction available without drop-thumb classification (BO-80's
# own explicit, deliberate scope limit, unchanged by BO-88: "do
# not attempt to determine whether a thumb stroke is specifically
# a 5th-string thumb stroke or a drop-thumb stroke" -- that remains
# future work).
FIFTH_STRING_INDEX = 4


AttackSequenceEntry = namedtuple(
    "AttackSequenceEntry", ["role"]
)
# role is "down", "pull", or None (ineligible -- unconstrained).


def compute_attack_sequence_by_event_id(ordered_events):
    """
    BO-88 -- walks ordered_events (a flat list of note/rest event
    dicts, each with "duration", in the exact document order they
    occur, harmony markers already excluded by the caller) and
    returns a dict mapping id(event) -> AttackSequenceEntry, giving
    each event's own attack role.

    Algorithm (an ordinal sequence, not elapsed-time arithmetic --
    see this module's own docstring for the real evidence this is
    built from):

        current_slot starts at None (no active sequence).

        For each event, in order:

            if event["duration"] > ATTACK_ELIGIBILITY_THRESHOLD_BEATS:
                role = None (ineligible, unconstrained)
                current_slot = None (terminates the sequence)

            else:
                role = current_slot if current_slot is not None
                       else "down" (the first attack of a fresh
                       sequence always starts down)
                current_slot flips: "down" -> "pull", "pull" -> "down"

    A rest event participates in this walk exactly like an eligible
    note (its own role is computed and the slot still flips), but
    since a rest has no real candidates at all, its own role is
    never actually used for filtering -- only for correctly
    advancing/flipping the sequence state for what follows it
    (confirmed real: M2's own rest occupies the "pull" slot without
    an attack, and the sequence correctly continues to "down" for
    the note after it).
    """

    role_by_id = {}

    current_slot = None

    for event in ordered_events:

        if event["duration"] > ATTACK_ELIGIBILITY_THRESHOLD_BEATS:

            role_by_id[id(event)] = AttackSequenceEntry(role=None)

            current_slot = None

        else:

            role = (
                current_slot if current_slot is not None
                else "down"
            )

            role_by_id[id(event)] = AttackSequenceEntry(role=role)

            current_slot = "pull" if role == "down" else "down"

    return role_by_id


def filter_by_attack_role(positions, expected_role):
    """
    BO-88 -- given positions (the same list of candidate dicts
    find_positions()/best_position() already produce, each with
    "string"/"fret") and expected_role ("down", "pull", or None),
    returns only the attack-compatible subset.

    expected_role=None (an ineligible, >1-beat note -- see this
    module's own docstring): the mechanism is completely inert --
    returns positions COMPLETELY UNFILTERED. This is deliberate,
    not a fallback: an ineligible note was never rhythmically
    constrained in the first place, so there is nothing to filter
    at all -- existing, separate mechanisms (open_string_bonus,
    etc.) remain fully responsible for its own candidate, exactly
    as before this module existed.

    expected_role="pull": only a genuinely OPEN 5th-string
    candidate (string==FIFTH_STRING_INDEX, fret==0) qualifies -- a
    FRETTED 5th-string candidate (confirmed real, BO-81's own
    implementation: the 5th string can reach an adjacent pitch
    fretted, exactly like any other string) is an ordinary
    fretting-hand note, not a thumb-on-an-open-string stroke, and
    must not be treated as pull-compatible merely because its own
    string_index is 4.

    expected_role="down": every other candidate (including a
    fretted 5th-string one) qualifies.

    Mandatory fallback (unchanged from BO-81/83): if no candidate
    matches expected_role, returns positions completely unfiltered
    -- this mechanism must never be able to make a note unplayable.
    """

    if expected_role is None:

        return positions

    if expected_role == "pull":

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
