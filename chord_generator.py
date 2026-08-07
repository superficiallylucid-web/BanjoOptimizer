"""
chord_generator.py

Generates candidate chord shapes for a (tuning, root, quality)
combination, by brute-force search across the fretboard rather
than looking anything up from a file.

Now supports partial voicings: a shape may mute one of the 4
melody strings if doing so produces a more playable chord,
represented with "--" for that string (see fretboard.py's
parse_shape/format_shape). Every generated shape still has at
least 3 sounding notes -- two-note dyads aren't generated yet.
Fully-fretted (4-string) shapes keep the exact same format as
before ("2012"), so nothing about the existing verified-shape
matching in chord_service.py needs to change.

This module has no dependency on chord_library.py and doesn't
touch it. Per the architecture proposal, the two are meant to
work together later (verified shapes supplementing, not
replacing, generated candidates) -- that combination step is
chord_service.py, not built here.
"""

from itertools import product

from models import ChordShape

from music import (
    chord_tones,
    tuning_symbol_from_notes,
    midi_to_note_name
)

from fretboard import (
    find_frets_for_pitch_classes,
    format_shape,
    hand_span,
    average_fret as fretted_average
)


# How far up the neck to search for candidate frets. Banjo
# chord shapes in the existing verified data top out low on
# the neck (nothing above fret 2 in the current library), so
# this is generous headroom, not a tight guess.
FRET_CEILING = 7

# Maximum spread between the lowest and highest FRETTED note
# in one candidate shape (open and muted strings don't count --
# see fretboard.hand_span). Keeps candidates physically
# playable without the brute-force search returning shapes
# spanning the whole neck.
MAX_SPAN = 4

# At most one of the 4 melody strings may be muted. This keeps
# every shape at 3 or 4 sounding notes -- two-note dyads aren't
# generated yet.
MAX_MUTED_STRINGS = 1

MAX_CANDIDATES = 5

# Ordered to match how music.chord_tones() builds its interval
# list: index 0 is always the root, index 1 the third (if the
# quality has one), index 2 the fifth, index 3 the seventh (for
# 7th-chord qualities). Which chord tone ends up lowest-sounding
# in a given voicing determines its inversion -- root in the
# bass is root position, third in the bass is first inversion,
# and so on.
INVERSION_NAMES = [
    "Root position",
    "First inversion",
    "Second inversion",
    "Third inversion"
]


def _score_candidate(values):
    """
    First-pass playability estimate for one candidate voicing
    (a list of 4 values, one per melody string: an int fret,
    or None for muted).

    Open strings get a real bonus -- they cost nothing to
    play. Muting a string is NOT treated the same way: on a
    banjo, deliberately silencing a string takes extra
    technique (palm muting, finger contact), unlike an open
    string which just rings on its own. So muting gets a small
    penalty instead of the open-string bonus -- it should only
    win out when it solves a real problem (e.g. removing a
    string that would otherwise force a wide span), not simply
    because fewer notes looks "easier" by note count alone.

    This is a simple, explicit heuristic -- not the same
    scoring as TuningAnalyzer's melody scoring, and not meant
    to be the last word on chord playability.
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


def _voicing_signature(values, melody_strings):
    """
    Identity used for duplicate removal: the set of distinct
    chord-tone pitch classes actually sounding, plus the exact
    top note. Two candidates with the same signature sound like
    the same voicing -- e.g. a 4-note shape and a 3-note muted
    variant that only removed a doubled chord tone -- so only
    the better-scoring one should survive.

    Deliberately ignores note *count*: a 3-note and 4-note
    voicing with the same signature are considered the same
    voicing, per the spec's own example.
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


def _identify_voicing(values, melody_strings, tones):
    """
    Given one candidate's per-string values (fret or None for
    muted) and the tuning's open-string MIDI values, work out
    the actual sounding pitches for this specific voicing, then
    identify:

    - inversion: which chord tone is lowest-sounding (root,
      third, fifth, or seventh), based on its position in
      `tones` -- tones[0] is always the root, per how
      music.chord_tones() builds its interval list.
    - top_note: the highest-sounding pitch, as a display name
      (e.g. "E4").

    Muted strings contribute no pitch at all -- only actually
    sounding strings are considered.

    Returns (inversion_name, top_note_name).
    """

    pitches = [
        open_note + value
        for open_note, value in zip(melody_strings, values)
        if value is not None
    ]

    lowest_pitch = min(pitches)

    highest_pitch = max(pitches)

    lowest_pitch_class = lowest_pitch % 12

    if lowest_pitch_class in tones:

        inversion_index = tones.index(lowest_pitch_class)

    else:

        # Shouldn't happen -- every fret in a candidate was
        # chosen because its pitch class is a chord tone (see
        # generate_candidates) -- but fall back safely rather
        # than raise if something upstream ever changes.
        inversion_index = None


    if (
        inversion_index is not None
        and inversion_index < len(INVERSION_NAMES)
    ):

        inversion = INVERSION_NAMES[inversion_index]

    else:

        inversion = "Unknown inversion"


    top_note = midi_to_note_name(highest_pitch)

    return inversion, top_note


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
    one tuning, via brute-force search -- best (highest-scoring)
    first.

    tuning: a Tuning (only .notes is used -- the 5 open-string
        MIDI values, 5th string to 1st)
    root: display name for the chord root, e.g. "C"
    root_pc: root pitch class (0-11)
    quality_code: internal quality code understood by
        music.chord_tones(), e.g. "" for major, "m" for minor
    quality_display: how the quality should read in the
        ChordShape, e.g. "Major"

    Each returned ChordShape has .inversion, .top_note,
    .average_fret, .hand_span, and .generator_score set. None
    of this is used in scoring/ranking elsewhere in the app --
    this is groundwork for future melody-note matching, not a
    ranking change to anything outside this module.

    Returns an empty list if no valid combination exists within
    FRET_CEILING / MAX_SPAN -- that's a legitimate result (some
    chords may not be reachable on some tunings within a
    reasonable stretch), not an error.
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


    # Each string's options are its valid frets, plus the
    # option to mute it entirely.
    per_string_options = [
        [None] + frets
        for frets in per_string_frets
    ]

    candidates = []

    for combination in product(*per_string_options):

        muted_count = combination.count(None)

        if muted_count > MAX_MUTED_STRINGS:

            continue

        if hand_span(combination) > MAX_SPAN:

            continue

        candidates.append(combination)


    scored = [
        (candidate, _score_candidate(candidate))
        for candidate in candidates
    ]

    # Duplicate removal: if two candidates sound the same set
    # of chord tones with the same top note (e.g. a 4-note
    # voicing and a 3-note muted variant that only dropped a
    # doubled tone), keep only the better-scoring one.
    best_by_signature = {}

    for values, score in scored:

        signature = _voicing_signature(values, melody_strings)

        existing = best_by_signature.get(signature)

        if existing is None or score > existing[1]:

            best_by_signature[signature] = (values, score)

    deduped = list(best_by_signature.values())

    deduped.sort(key=lambda pair: pair[1], reverse=True)

    top = deduped[:max_candidates]

    tuning_symbol = tuning_symbol_from_notes(tuning.notes)

    results = []

    for values, score in top:

        shape_text = format_shape(values)

        inversion, top_note = _identify_voicing(
            values,
            melody_strings,
            tones
        )

        results.append(
            ChordShape(
                tuning=tuning_symbol,
                root=root,
                quality=quality_display,
                shape=shape_text,
                comfort_code=None,
                comfort_explanation="",
                comments=(
                    f"Generated candidate "
                    f"(playability estimate: {score:.1f})"
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
