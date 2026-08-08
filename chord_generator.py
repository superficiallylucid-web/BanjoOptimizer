"""
chord_generator.py

Generates candidate chord shapes for a (tuning, root, quality)
combination, by searching for USEFUL voicings -- not by
enumerating every mathematically possible combination of open,
fretted, and muted strings.

Core principle: a full (4-string) voicing is the default. A
reduced (muted-string) voicing is only offered as a RESCUE --
generated specifically because the corresponding full voicing
is impractical (rejected by playability.py) and removing one
string turns it into something playable. Muting a string just
because a full voicing *could* be reduced is NOT a reason to
offer it as a separate candidate -- that's the player's own
choice to make while playing, not a distinct recommendation.

This module now depends on playability.py (to decide full vs.
rescue), per the architecture: chord_generator.py finds
mathematically valid possibilities and uses playability.py to
judge them; chord_service.py combines/dedupes/ranks; neither
duplicates the other's logic.

Returns UP TO max_candidates -- never pads the list with
trivial variants just to reach five.
"""

from itertools import product

from models import ChordShape

from music import (
    chord_tones,
    tuning_symbol_from_notes
)

from fretboard import (
    find_frets_for_pitch_classes,
    format_shape,
    hand_span,
    average_fret as fretted_average,
    calculate_shape_metadata
)

from playability import evaluate as evaluate_playability


# How far up the neck to search for candidate frets. Banjo
# chord shapes in the existing verified data top out low on
# the neck (nothing above fret 2 in the current library), so
# this is generous headroom, not a tight guess.
FRET_CEILING = 7

# Loose computational bound on the SEARCH, not a playability
# judgment -- playability.py's own (stricter) span check is
# what actually decides accept/reject now. This just needs to
# be wide enough that genuinely "impractical" full voicings
# still get considered (and can then be rejected and possibly
# rescued), rather than being pruned before they're ever
# evaluated at all.
SEARCH_MAX_SPAN = 6

MAX_CANDIDATES = 5


def _score_candidate(values):
    """
    First-pass playability estimate for one candidate voicing
    (a list of 4 values, one per melody string: an int fret,
    or None for muted). Used only to order/compare candidates
    that playability.py has already accepted -- not used to
    decide accept/reject itself (that's playability.py's job).
    """

    open_count = sum(1 for value in values if value == 0)

    muted_count = sum(1 for value in values if value is None)

    span = hand_span(values)

    avg = fretted_average(values)

    return (
        (open_count * 10)
        - (muted_count * 3)
        - (avg * 2)
        - span
    )


def _sounding_pitch_classes(values, melody_strings):
    """
    Distinct chord-tone pitch classes actually sounding in this
    voicing (muted strings contribute nothing).
    """

    sounding_pitches = [
        open_note + value
        for open_note, value in zip(melody_strings, values)
        if value is not None
    ]

    return frozenset(pitch % 12 for pitch in sounding_pitches)


def _voicing_signature(values, melody_strings):
    """
    Identity used for duplicate removal: the set of distinct
    chord-tone pitch classes actually sounding, plus the exact
    top note. Two candidates with the same signature sound like
    the same voicing, so only the better one should survive.

    Deliberately ignores note *count*: a 3-note and 4-note
    voicing with the same signature are considered the same
    voicing.
    """

    sounding_pitches = [
        open_note + value
        for open_note, value in zip(melody_strings, values)
        if value is not None
    ]

    pitch_classes = frozenset(
        pitch % 12 for pitch in sounding_pitches
    )

    top_pitch = max(sounding_pitches)

    return (pitch_classes, top_pitch)


def attempt_rescue(full_values, melody_strings, tones):
    """
    Given a full voicing that playability.py has REJECTED, try
    muting one fretted (nonzero) string at a time to see if the
    result is both:

    - a valid triad: the remaining sounding pitch classes still
      cover every required chord tone (muting a string that
      held a tone no other string provides would leave the
      chord incomplete -- not offered)
    - playable: playability.py accepts the reduced shape

    Muting an already-open string is never attempted -- it
    can't fix a span/spike problem (open strings don't count
    toward either), so it would just remove a free note for no
    benefit.

    Returns a list of valid, playable reduced value-lists (each
    the same length as full_values, with exactly one entry set
    to None). May be empty if no single-string reduction
    rescues this voicing.
    """

    required = frozenset(tones)

    rescues = []

    for i, value in enumerate(full_values):

        if value is None or value == 0:

            # Muting an open string fixes nothing; muting an
            # already-muted string isn't meaningful here.
            continue

        reduced = list(full_values)

        reduced[i] = None

        coverage = _sounding_pitch_classes(
            reduced,
            melody_strings
        )

        if not required.issubset(coverage):

            # This reduction drops an essential chord tone --
            # not a valid triad, not offered.
            continue

        reduced_shape_text = format_shape(reduced)

        result = evaluate_playability(reduced_shape_text)

        if result.accepted:

            rescues.append(reduced)

    return rescues


def generate_candidates(
    tuning,
    root,
    root_pc,
    quality_code,
    quality_display,
    max_candidates=MAX_CANDIDATES
):
    """
    Generate up to max_candidates ChordShapes for one chord in
    one tuning -- USEFUL voicings, not every mathematically
    valid combination.

    For each full (4-string) combination that covers the
    required chord tones:
      - if playability.py accepts it, it's a candidate as-is
      - if not, try rescuing it by muting one fretted string
        (see attempt_rescue) -- a rescue is only kept if it's
        a valid, playable triad
      - if neither works, that combination contributes nothing

    A rescue is then dropped if it's redundant with an already-
    accepted full voicing for this same chord: if every pitch
    class the rescue sounds is already covered by some accepted
    full voicing, a player could get that exact sound by simply
    choosing not to play one string of the full voicing --
    that's their own playing choice, not a separate
    recommendation.

    tuning: a Tuning (only .notes is used -- the 5 open-string
        MIDI values, 5th string to 1st)
    root: display name for the chord root, e.g. "C"
    root_pc: root pitch class (0-11)
    quality_code: internal quality code understood by
        music.chord_tones(), e.g. "" for major, "m" for minor
    quality_display: how the quality should read in the
        ChordShape, e.g. "Major"

    Each returned ChordShape has .inversion, .top_note,
    .average_fret, .hand_span, and .generator_score set.

    Returns however many genuinely useful candidates exist, up
    to max_candidates -- never pads the list to reach five, and
    may return an empty list if nothing in range is playable at
    all.
    """

    tones = chord_tones(root_pc, quality_code)

    if tones is None:

        return []


    # The 4 melody strings, 4th to 1st -- the 5th/drone string
    # isn't part of the "shape" format (see ChordShape's
    # docstring in models.py).
    melody_strings = tuning.notes[1:]

    per_string_frets = [
        find_frets_for_pitch_classes(
            open_note,
            tones,
            FRET_CEILING
        )
        for open_note in melody_strings
    ]

    if any(not frets for frets in per_string_frets):

        # At least one string has no fret in range that
        # produces a chord tone -- no valid shape exists
        # within our search window.
        return []


    full_combinations = [
        combination
        for combination in product(*per_string_frets)
        if hand_span(combination) <= SEARCH_MAX_SPAN
    ]

    accepted_full = []

    rescue_candidates = []

    for full_values in full_combinations:

        full_shape_text = format_shape(full_values)

        result = evaluate_playability(full_shape_text)

        if result.accepted:

            accepted_full.append(full_values)

        else:

            for reduced in attempt_rescue(
                full_values,
                melody_strings,
                tones
            ):

                rescue_candidates.append(reduced)


    # Drop rescues that are redundant with an already-accepted
    # full voicing: if a rescue's coverage is fully contained
    # in some accepted full voicing's coverage, a player could
    # get that sound by simply not playing one string of the
    # full voicing -- not a distinct candidate.
    full_coverages = [
        _sounding_pitch_classes(values, melody_strings)
        for values in accepted_full
    ]

    useful_rescues = []

    for reduced in rescue_candidates:

        coverage = _sounding_pitch_classes(
            reduced,
            melody_strings
        )

        redundant = any(
            coverage <= full_coverage
            for full_coverage in full_coverages
        )

        if not redundant:

            useful_rescues.append(reduced)


    # Combine, dedupe by voicing signature (prefer full over
    # reduced on a tie, then higher generator score), and take
    # up to max_candidates. Full voicings are listed first so
    # that a full/reduced tie in the dedup step below prefers
    # the full voicing, per "a full voicing should normally
    # outrank and replace its reduced variants."
    all_candidates = (
        [(values, True) for values in accepted_full]
        + [(values, False) for values in useful_rescues]
    )

    best_by_signature = {}

    for values, is_full in all_candidates:

        signature = _voicing_signature(values, melody_strings)

        score = _score_candidate(values)

        existing = best_by_signature.get(signature)

        if existing is None:

            best_by_signature[signature] = (
                values, is_full, score
            )

        else:

            _, existing_is_full, existing_score = existing

            prefer_new = (
                (is_full and not existing_is_full)
                or (
                    is_full == existing_is_full
                    and score > existing_score
                )
            )

            if prefer_new:

                best_by_signature[signature] = (
                    values, is_full, score
                )

    deduped = list(best_by_signature.values())

    # Full voicings first, then by score -- never sort a
    # reduced candidate ahead of an available full one.
    deduped.sort(
        key=lambda entry: (not entry[1], -entry[2])
    )

    top = deduped[:max_candidates]

    tuning_symbol = tuning_symbol_from_notes(tuning.notes)

    results = []

    for values, is_full, score in top:

        shape_text = format_shape(values)

        inversion, top_note = calculate_shape_metadata(
            tuning,
            shape_text,
            root_pc,
            quality_code
        )

        voicing_type = "full" if is_full else "reduced/rescue"

        results.append(
            ChordShape(
                tuning=tuning_symbol,
                root=root,
                quality=quality_display,
                shape=shape_text,
                comfort_code=None,
                comfort_explanation="",
                comments=(
                    f"Generated candidate ({voicing_type}, "
                    f"playability estimate: {score:.1f})"
                ),
                verified=None,
                inversion=inversion,
                top_note=top_note,
                average_fret=round(fretted_average(values), 2),
                hand_span=hand_span(values),
                generator_score=round(score, 2)
            )
        )

    return results
