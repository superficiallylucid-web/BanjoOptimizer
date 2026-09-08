"""
chord_vocabulary_analysis.py

Evidence-gathering for comparing how well two tunings serve the
same score's actual chord vocabulary -- e.g. the real question
that motivated this module: why might aEADE be a better
practical choice than aDADE for a given arrangement, even
though the tuning-recommendation optimizer scores them nearly
equal?

This module does NOT:
- change tuning-recommendation scoring (optimizer.py is
  untouched and not imported here)
- pick a "winner" between tunings
- implement chord substitution
- duplicate any music/chord logic -- it's a thin analysis layer
  over the existing chord_service.py / fretboard.py machinery
  (get_shapes(), select_shape_for_melody(),
  classify_melody_realization())

It produces evidence for a human to look at, via
analyze_score_for_tuning() -- comparing two TuningChordAnalysis
results side by side (one per tuning) is how that evidence gets
used, not anything automated here.

REPETITION IS NOT WEIGHTED, DELIBERATELY (see
extract_chord_vocabulary()): a chord+melody combination that
occurs 9 times in an arrangement is analyzed once, the same as
one that occurs once. The practical chord vocabulary of an
arrangement is the set of distinct musical situations it
presents, not a frequency-weighted score -- and a weighting
scheme is exactly the "complicated" thing this task asked NOT
to build yet. occurrence_count is still recorded on each result
for transparency.
"""

from music import (
    pitch_name,
    quality_code_to_display_name,
    midi_to_note_name
)

from fretboard import (
    DIRECT_REALIZATION,
    INDIRECT_REALIZATION,
    NO_REALIZATION
)

from models import ChordOccurrenceAnalysis, TuningChordAnalysis


def extract_chord_vocabulary(score):
    """
    Return the distinct (root_pc, quality_code, melody pitch
    class) combinations that make up a score's practical chord
    vocabulary, deduplicated -- not one entry per raw
    occurrence in the score (see module notes on why repetition
    isn't weighted).

    melody pitch class is None for a chord occurrence with no
    identifiable melody note (see Score.melody_note_for_harmony)
    -- that's kept as a genuinely distinct vocabulary entry from
    the same chord WITH a melody note, since "just the chord,
    no specific melody requirement" is a different practical
    situation.

    Returns a list of dicts (one per distinct combination):
        root_pc, quality_code, symbol (a representative chord
        symbol string, from the first occurrence),
        melody_pitch_class, melody_midi (from the first
        occurrence sharing this pitch class -- used only to
        build a display name later), occurrence_count,
        example_measure (the first measure this combination
        appears at).

    Does not require or use a tuning -- this is purely about
    what the SCORE asks for, before any tuning-specific
    playability question is considered.
    """

    seen = {}

    order = []

    for harmony in score.harmonies:

        melody_midi = score.melody_note_for_harmony(harmony)

        melody_pitch_class = (
            melody_midi % 12
            if melody_midi is not None
            else None
        )

        key = (
            harmony.root_pc,
            harmony.quality_code,
            melody_pitch_class
        )

        if key in seen:

            seen[key]["occurrence_count"] += 1

            continue

        entry = {
            "root_pc": harmony.root_pc,
            "quality_code": harmony.quality_code,
            "symbol": harmony.symbol,
            "melody_pitch_class": melody_pitch_class,
            "melody_midi": melody_midi,
            "occurrence_count": 1,
            "example_measure": harmony.measure,
        }

        seen[key] = entry

        order.append(key)

    return [seen[key] for key in order]


def analyze_chord_for_tuning(
    chord_service,
    tuning,
    vocabulary_entry
):
    """
    Analyze one chord vocabulary entry (see
    extract_chord_vocabulary()) against one tuning, using the
    existing chord_service.py machinery directly -- no new
    musical logic.

    Returns a ChordOccurrenceAnalysis.
    """

    root_pc = vocabulary_entry["root_pc"]

    quality_code = vocabulary_entry["quality_code"]

    root_name = pitch_name(root_pc)

    quality_display = quality_code_to_display_name(quality_code)

    melody_midi = vocabulary_entry["melody_midi"]

    melody_note = None

    if melody_midi is not None:

        melody_note = midi_to_note_name(melody_midi)


    shapes = []

    if quality_display is not None:

        shapes = chord_service.get_shapes(
            tuning,
            root_name,
            root_pc,
            quality_code,
            quality_display
        )

    usable_shape_count = len(shapes)

    selected_shape = None

    realization_tier = ""

    if usable_shape_count > 0:

        if melody_note is not None:

            selection = chord_service.select_shape_for_melody(
                tuning,
                root_name,
                root_pc,
                quality_code,
                quality_display,
                melody_note
            )

            selected_shape = selection.selected_shape

            realization_tier = selection.realization_tier

        else:

            selected_shape = shapes[0]


    voicing_quality_category = (
        selected_shape.voicing_quality_category
        if selected_shape is not None
        else ""
    )

    return ChordOccurrenceAnalysis(
        root=root_name,
        quality_code=quality_code,
        quality_display=quality_display,
        chord_symbol=vocabulary_entry["symbol"],
        melody_note=melody_note,
        occurrence_count=vocabulary_entry["occurrence_count"],
        example_measure=vocabulary_entry["example_measure"],
        usable_shape_count=usable_shape_count,
        selected_shape=selected_shape,
        realization_tier=realization_tier,
        voicing_quality_category=voicing_quality_category
    )


def analyze_score_for_tuning(score, tuning, chord_service):
    """
    Analyze a score's full chord vocabulary against one tuning.

    Returns a TuningChordAnalysis: one ChordOccurrenceAnalysis
    per distinct chord+melody combination (see
    extract_chord_vocabulary()), plus simple tallies for
    convenience. No comparison or verdict -- call this once per
    tuning and compare the two TuningChordAnalysis results
    yourself (or via the diagnostic demo in dev_demos.py).
    """

    vocabulary = extract_chord_vocabulary(score)

    occurrences = [
        analyze_chord_for_tuning(chord_service, tuning, entry)
        for entry in vocabulary
    ]

    analysis = TuningChordAnalysis(
        tuning_symbol=tuning.symbol,
        occurrences=occurrences
    )

    for occurrence in occurrences:

        if occurrence.usable_shape_count == 0:

            analysis.no_usable_shape_count += 1

        if occurrence.melody_note is None:

            analysis.no_melody_note_count += 1

            continue

        if occurrence.realization_tier == DIRECT_REALIZATION:

            analysis.direct_count += 1

        elif occurrence.realization_tier == INDIRECT_REALIZATION:

            analysis.indirect_count += 1

        else:

            analysis.no_realization_count += 1

    return analysis
