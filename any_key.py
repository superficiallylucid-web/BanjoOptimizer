"""
any_key.py

BO-178 -- any-key tuning recommendation mode: for each candidate
tuning, tries every key listed in that tuning's own key_
strengths (not all 12 chromatic roots -- only the keys the
tuning itself claims genuine strength in), scores the song
transposed to each one using the EXISTING melody + chord/FD
machinery unchanged (TuningAnalyzer.score_tuning(), reused
directly), and keeps the best-scoring (key, result) combination
for that tuning. No new scoring logic of its own.

Deliberately separate from optimizer.py's own same-key analyze()
path (which stays completely unchanged -- see run_optimizer()'s
own `any_key` parameter, mirroring output_key's existing
same-key/explicit-key split): a tuning with no real
key_strengths at all (e.g. a historical tuning with `{}`) simply
falls back to [source_key], the same single candidate same-key
mode would have used -- any-key mode never disadvantages a
tuning that has nothing to gain from it.
"""

import copy
from types import SimpleNamespace

from optimizer import TuningAnalyzer
from transposition import semitones_for_output_key, transpose_score
from tunings import get_tunings


def _transposed_analyzer(notes, melody_notes, harmonies, source_key, target_key_text):
    """
    Returns a fresh TuningAnalyzer scoring the song transposed to
    target_key_text (a "ROOT MODE" string, e.g. "D major" --
    tuning.key_strengths' own key format), built from DEEP COPIES
    of notes/melody_notes/harmonies -- transposing for one
    candidate key never mutates the caller's own data or any
    other candidate's own copy, unlike main.py's own output_key
    path (which transposes the single shared score once, in
    place, since it only ever needs one target key per run).

    Reuses transpose_score() unchanged via a minimal stand-in
    object exposing exactly the shape it reads/writes (.notes,
    .score.notes, .harmonies, .score.harmonies, .key,
    .score.key) -- not a real parser.MuseScoreFile instance,
    which carries unrelated XML-parsing state this never needs.
    """

    target_root = target_key_text.split()[0]

    semitones = semitones_for_output_key(source_key, target_root)

    copied_notes = copy.deepcopy(notes)

    copied_melody_notes = copy.deepcopy(melody_notes)

    copied_harmonies = copy.deepcopy(harmonies)

    inner = SimpleNamespace(
        notes=copied_melody_notes,
        harmonies=copied_harmonies,
        key=source_key
    )

    stand_in = SimpleNamespace(
        notes=copied_notes,
        harmonies=copied_harmonies,
        key=source_key,
        score=inner
    )

    new_key = transpose_score(stand_in, semitones)

    return (
        TuningAnalyzer(
            stand_in.notes, new_key, stand_in.harmonies,
            stand_in.score.notes
        ),
        new_key
    )


def rank_tunings_across_keys(
    notes, melody_notes, harmonies, source_key
):
    """
    Returns every "modern"-category tuning's own best-scoring
    (tuning, key) result, sorted by combined_score descending --
    the any-key equivalent of TuningAnalyzer.analyze()["modern"].

    Each returned TuningResult has recommended_key set to the
    root note name (e.g. "D") its own best candidate key
    transposed to -- None only if that tuning's own best
    candidate was the source key itself (semitones=0, a genuine
    "already there" result, not a missing value).

    combined_score here is computed per (tuning, key) INDEPENDENTLY
    (via TuningAnalyzer._apply_combined_score() on a single-
    element list) rather than group-relative across every other
    tuning also being considered -- safe only because BO-176 made
    BOTH the melody and chord/FD sides of that formula fixed-
    reference normalized; before that change this shortcut would
    have been wrong (melody normalization used to depend on which
    OTHER tunings were in the group).
    """

    best_by_tuning = []

    for tuning in get_tunings().values():

        if tuning.category != "modern":

            continue

        candidate_keys = (
            list(tuning.key_strengths.keys())
            if tuning.key_strengths
            else [source_key]
        )

        best_result = None

        for candidate_key_text in candidate_keys:

            analyzer, new_key = _transposed_analyzer(
                notes, melody_notes, harmonies, source_key,
                candidate_key_text
            )

            result = analyzer.score_tuning(tuning)

            analyzer._apply_combined_score([result])

            result.recommended_key = (
                new_key.split()[0]
                if new_key != source_key
                else None
            )

            if (
                best_result is None
                or result.combined_score
                > best_result.combined_score
            ):

                best_result = result

        best_by_tuning.append(best_result)

    best_by_tuning.sort(
        key=lambda r: -r.combined_score
    )

    return best_by_tuning
