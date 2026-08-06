"""
chord_generator.py

Generates candidate chord shapes for a (tuning, root, quality)
combination, by brute-force search across the fretboard rather
than looking anything up from a file.

Scope of this first pass, deliberately kept small: one tuning,
one chord at a time, no muted strings (every one of the 4
melody strings -- 4th to 1st, matching the existing ChordShape
"shape" format -- must sound a chord tone). This matches how
every shape in the real chord library data actually looks today
(20/20 verified shapes use all 4 strings, none muted), so it's
not a simplification that throws away real cases -- it's the
actual shape of the data.

This module has no dependency on chord_library.py and doesn't
touch it. Per the architecture proposal, the two are meant to
work together later (verified shapes supplementing, not
replacing, generated candidates) -- that combination step is
a separate future module (chord_service.py), not built here.
"""

from itertools import product

from models import ChordShape

from music import (
    chord_tones,
    tuning_symbol_from_notes,
    midi_to_note_name
)

from fretboard import find_frets_for_pitch_classes


# How far up the neck to search for candidate frets. Banjo
# chord shapes in the existing verified data top out low on
# the neck (nothing above fret 2 in the current library), so
# this is generous headroom, not a tight guess.
FRET_CEILING = 7

# Maximum spread between the lowest and highest fret used in
# one candidate shape. Keeps candidates physically playable --
# without this, the brute-force search would happily return
# shapes spanning the whole neck.
MAX_SPAN = 4

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


def _score_candidate(frets):
    """
    First-pass playability estimate for one candidate shape,
    given as a tuple of 4 frets (4th string to 1st).

    Favors open strings, low positions, and a small span.
    This is a simple, explicit heuristic -- not the same
    scoring as TuningAnalyzer's melody scoring, and not meant
    to be the last word on chord playability. It exists so
    candidates can be ranked at all; refining it is expected
    future work, not something this first pass needs to get
    perfect.
    """

    open_count = sum(1 for fret in frets if fret == 0)

    average_fret = sum(frets) / len(frets)

    span = max(frets) - min(frets)

    return (
        (open_count * 10)
        - (average_fret * 2)
        - span
    )


def _identify_voicing(frets, melody_strings, tones):
    """
    Given one candidate's frets and the tuning's open-string
    MIDI values, work out the actual sounding pitches for this
    specific voicing, then identify:

    - inversion: which chord tone is lowest-sounding (root,
      third, fifth, or seventh), based on its position in
      `tones` -- tones[0] is always the root, per how
      music.chord_tones() builds its interval list.
    - top_note: the highest-sounding pitch, as a display name
      (e.g. "E4").

    Returns (inversion_name, top_note_name).
    """

    pitches = [
        open_note + fret
        for open_note, fret in zip(melody_strings, frets)
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

    Each returned ChordShape also has .inversion and .top_note
    set, identifying which chord tone is lowest-sounding in
    that specific voicing and what the highest note is. Not
    used in scoring or ranking here -- this is groundwork for
    future melody-note matching, not a ranking change.

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


    candidates = []

    for combination in product(*per_string_frets):

        span = max(combination) - min(combination)

        if span > MAX_SPAN:

            continue

        candidates.append(combination)


    scored = [
        (candidate, _score_candidate(candidate))
        for candidate in candidates
    ]

    scored.sort(key=lambda pair: pair[1], reverse=True)

    top = scored[:max_candidates]

    tuning_symbol = tuning_symbol_from_notes(tuning.notes)

    results = []

    for rank, (frets, score) in enumerate(top, start=1):

        shape_text = "".join(str(fret) for fret in frets)

        inversion, top_note = _identify_voicing(
            frets,
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
                top_note=top_note
            )
        )

    return results
