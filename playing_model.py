"""
playing_model.py

Chord-centered Playing Model: evaluates melody locations in
combination with playable chord shapes, rather than treating
melody optimization and chord optimization as two independent
systems. See DESIGN.md for the full design description and the
canonical E5 -> A5 -> C4 -> Bsus4 example this was built
against.

Pipeline (section 12 of the design):
    candidate chord shapes -> chord-shape playability ->
    chord/melody combinations -> phrase solutions ->
    phrase score -> tuning score

INTEGRATION STATUS -- read before wiring this into anything:
optimizer.py's TuningAnalyzer currently takes only (notes, key)
-- no chord/harmony dependency at all. Blending this model's
tuning-level score into score_tuning() would require changing
that interface (every caller: main.py, existing tests), which
is a larger structural change than "the smallest necessary."
This module produces real, structured phrase and tuning-level
scores; for this first implementation they're exposed as a
diagnostic (see dev_demos.py) rather than blended into the
production tuning score. Existing tuning recommendation
scoring/ranking is unchanged by this module's existence.

Reuses existing machinery throughout -- no duplicated music
theory or fretboard math:
- chord_service.ChordService.get_shapes() for candidate chord
  shapes (verified + generated, already playability-filtered)
- fretboard.find_positions() for melody note realizations
- fretboard.sounding_notes() / parse_shape() for shape geometry
- melody_box_analysis.build_melody_boxes() for the melody
  passage between chord occurrences (the phrase window)

HEURISTIC WEIGHTS: kept intentionally small and named, not a
large proliferation of tuned constants. They encode the
relationships the design doc itself calls out (2004 comfortable
vs 3206 difficult, 1234 vs 4321, open string 1/4 vs 2/3, etc.)
-- verified against those specific examples during development,
not against exhaustive real-world calibration. Treat them as
"initial heuristics, not immutable rules," per the design doc.
"""

from fretboard import parse_shape, sounding_notes

from melody_box_analysis import build_melody_boxes, realize_note

from music import (
    quality_code_to_display_name, pitch_name, chord_tones
)

from models import (
    ChordShapePlayability,
    MelodyChordCombination,
    PhraseSolution,
    TuningPlayingModelResult,
    ChordMelodyRealization,
    NON_CHORD_TONE,
    CHORD_TONE_NOT_IN_VOICING,
    CHORD_TONE_IN_VOICING,
    PLAYABLE_FROM_CHORD_POSITION,
    AVAILABLE_BUT_POSITION_CHANGE_REQUIRED
)


# ---------------------------------------------------------
# Section 3 -- intrinsic chord shape playability
# ---------------------------------------------------------

FINGER_LOAD_PENALTY = {0: 0.0, 1: 0.0, 2: 1.0, 3: 3.0, 4: 6.0}

EDGE_STRING_OPEN_BONUS = 1.5  # strings 1 and 4 (indices 3, 0)

INNER_STRING_OPEN_BONUS = 0.5  # strings 2 and 3 (indices 1, 2)

GEOMETRY_PENALTY_WEIGHT = 0.75

SPAN_COMFORTABLE_LIMIT = 3

SPAN_PENALTY_PER_FRET = 1.5

BASE_PLAYABILITY = 10.0


def analyze_chord_shape_playability(shape_text):
    """
    Intrinsic playability of one chord shape, independent of
    any melody -- section 3. Higher score = more playable.

    - Finger load: fewer fretted fingers is better (frees
      fingers for melody, section 5); a 4-finger chord takes a
      real penalty.
    - Finger geometry: rewards frets that rise (or stay level)
      moving from string 4 toward string 1 -- the natural angle
      the hand approaches the neck at (design doc: "1234
      comfortable, 4321 much less so"). Checked only across
      ADJACENT FRETTED strings; an open or muted string doesn't
      break the sequence, since no finger is forced there.
    - Span: a comfortable span (<=3 frets between the lowest and
      highest fretted position) costs nothing; each fret beyond
      that adds a penalty (design doc: "2004 comfortable despite
      apparent span" -- span alone isn't the whole story, but it
      still matters once a shape truly stretches).
    - Open strings: string 1 and string 4 (design doc: generally
      easier/more useful open) get a larger bonus than string 2
      or 3.
    """

    values = parse_shape(shape_text)

    fretted = [
        (i, f) for i, f in enumerate(values)
        if f is not None and f > 0
    ]

    open_strings = [
        i for i, f in enumerate(values) if f == 0
    ]

    finger_count = len(fretted)

    if fretted:

        frets_only = [f for _, f in fretted]

        span = max(frets_only) - min(frets_only)

    else:

        span = 0

    geometry_penalty = 0.0

    for (_, f1), (_, f2) in zip(fretted, fretted[1:]):

        if f2 < f1:

            geometry_penalty += (f1 - f2)

    finger_load_penalty = FINGER_LOAD_PENALTY.get(
        finger_count, FINGER_LOAD_PENALTY[4] + 2.0
    )

    open_bonus = sum(
        EDGE_STRING_OPEN_BONUS
        if i in (0, 3) else INNER_STRING_OPEN_BONUS
        for i in open_strings
    )

    span_penalty = (
        max(0, span - SPAN_COMFORTABLE_LIMIT)
        * SPAN_PENALTY_PER_FRET
    )

    score = (
        BASE_PLAYABILITY
        - finger_load_penalty
        - geometry_penalty * GEOMETRY_PENALTY_WEIGHT
        - span_penalty
        + open_bonus
    )

    return ChordShapePlayability(
        shape=shape_text,
        finger_count=finger_count,
        span=span,
        geometry_penalty=geometry_penalty,
        open_strings=open_strings,
        score=score
    )


# ---------------------------------------------------------
# Section 5 -- combining a chord shape with melody locations
# ---------------------------------------------------------

CONTAINED_IN_CHORD_BONUS = 6.0

FREE_FINGER_BONUS = 3.0

# Section 5: "string 1 is easiest to add a melody note to...
# string 4 is hardest" -- a physical accessibility preference,
# not a prohibition, so a small additive bonus rather than a
# hard filter. String 1 is index 3 in this project's 4th->1st
# string-index convention.
STRING_ACCESSIBILITY_BONUS = {3: 1.5, 2: 1.0, 1: 0.5, 0: 0.0}

PROXIMITY_BONUS_PER_FRET_CLOSE = 1.0  # within 2 frets of the chord


def _chord_working_fret(shape_values):
    """
    A chord shape's own approximate hand position -- the lowest
    fretted position, matching the same index-finger convention
    melody_box_analysis.py uses for melody. Returns None for an
    all-open/muted shape (no fretted position to anchor to).
    """

    fretted_values = [
        f for f in shape_values if f is not None and f > 0
    ]

    if not fretted_values:

        return None

    return min(fretted_values)


def evaluate_combination(chord_shape_text, tuning, note):
    """
    Evaluate one melody Note against one chord shape -- the
    central unit of the model (section 5). Considers every
    realization find_positions() returns (via
    melody_box_analysis.realize_note(), reused unchanged) and
    keeps the best-scoring one for THIS combination -- this
    function is not the final word on the note's location; a
    later phrase-continuity step may still prefer differently
    (section 11).

    Returns a MelodyChordCombination.
    """

    shape_values = parse_shape(chord_shape_text)

    chord_pitch_classes = {
        sounding_note.pitch_class
        for sounding_note in sounding_notes(
            tuning, chord_shape_text
        )
    }

    contained = (note.midi % 12) in chord_pitch_classes

    working_fret = _chord_working_fret(shape_values)

    box_note = realize_note(note, tuning)

    best_realization = None

    best_score = float("-inf")

    best_free_finger = False

    for realization in box_note.realizations:

        score = 0.0

        if contained:

            score += CONTAINED_IN_CHORD_BONUS

        free_finger = False

        if working_fret is not None and realization.fret > 0:

            # A free finger: this string isn't already used by
            # the chord shape, and the melody fret is within
            # the chord's own working position (reusing the
            # same strict four-fret window melody_box_analysis
            # already uses for hand position).
            string_in_use = (
                shape_values[realization.string_index]
                not in (None, 0)
            )

            in_working_position = (
                working_fret
                <= realization.fret
                <= working_fret + 3
            )

            free_finger = (
                not string_in_use and in_working_position
            )

        if free_finger:

            score += FREE_FINGER_BONUS

        score += STRING_ACCESSIBILITY_BONUS.get(
            realization.string_index, 0.0
        )

        if working_fret is not None and realization.fret > 0:

            distance = abs(realization.fret - working_fret)

            if distance <= 2:

                score += (
                    PROXIMITY_BONUS_PER_FRET_CLOSE
                    * (2 - distance)
                )

        elif realization.fret == 0:

            # An open string is always comfortably reachable
            # regardless of the chord's working position.
            score += PROXIMITY_BONUS_PER_FRET_CLOSE

        if score > best_score:

            best_score = score

            best_realization = realization

            best_free_finger = free_finger

    return MelodyChordCombination(
        midi=note.midi,
        contained_in_chord=contained,
        realization=best_realization,
        free_finger=best_free_finger,
        score=best_score if best_realization else 0.0
    )


# ---------------------------------------------------------
# Section 6 & 9 -- phrase window (lead-in / box) and 5th string
# ---------------------------------------------------------

FIFTH_STRING_BRIDGE_BONUS = 2.0

LEAD_IN_NOTE_COUNT = 2


def _fifth_string_bonus(tuning, notes_in_phrase):
    """
    Section 9: the 5th string is considered separately from the
    fretted melody/chord fingering -- a bonus if any melody note
    in the phrase matches the 5th string's fixed open pitch
    class (a usable drone/bridge point), not treated as an
    ordinary fretted melody string at all.
    """

    fifth_string_pitch_class = tuning.notes[0] % 12

    for note in notes_in_phrase:

        if note.midi % 12 == fifth_string_pitch_class:

            return FIFTH_STRING_BRIDGE_BONUS

    return 0.0


def evaluate_phrase(
    chord_shape, tuning, harmony, box_notes, lead_in_notes
):
    """
    Section 6: evaluate a chord shape against the melody
    immediately before it (lead_in_notes) and after it
    (box_notes) -- not an instantaneous event at the chord
    symbol's exact moment.

    Returns a PhraseSolution.
    """

    playability = analyze_chord_shape_playability(
        chord_shape.shape
    )

    lead_in_results = [
        evaluate_combination(chord_shape.shape, tuning, note)
        for note in lead_in_notes
    ]

    box_results = [
        evaluate_combination(chord_shape.shape, tuning, note)
        for note in box_notes
    ]

    fifth_bonus = _fifth_string_bonus(
        tuning, lead_in_notes + box_notes
    )

    combination_score = sum(
        result.score for result in lead_in_results + box_results
    )

    total_score = (
        playability.score + combination_score + fifth_bonus
    )

    return PhraseSolution(
        chord=harmony,
        chord_shape=chord_shape,
        shape_playability=playability,
        lead_in=lead_in_results,
        box_notes=box_results,
        fifth_string_bonus=fifth_bonus,
        score=total_score
    )


# ---------------------------------------------------------
# Section 7 -- phrase continuity
# ---------------------------------------------------------

CONTINUITY_MOVE_PENALTY_PER_FRET = 0.3

CONTINUITY_MOVE_DAMPENING_START = 5  # frets before penalty stops growing


def _continuity_bonus(previous_phrase, current_phrase):
    """
    Section 7: prefer modest movement between consecutive chord
    shapes' working positions, but do not treat a large move as
    automatically bad -- the penalty is capped rather than
    growing without bound, since a big jump can be the musically
    right choice (e.g. moving up the neck for a substantially
    better position).
    """

    if (
        previous_phrase is None
        or previous_phrase.chord_shape is None
        or current_phrase.chord_shape is None
    ):

        return 0.0

    previous_fret = _chord_working_fret(
        parse_shape(previous_phrase.chord_shape.shape)
    )

    current_fret = _chord_working_fret(
        parse_shape(current_phrase.chord_shape.shape)
    )

    if previous_fret is None or current_fret is None:

        return 0.0

    distance = abs(current_fret - previous_fret)

    penalized_distance = min(
        distance, CONTINUITY_MOVE_DAMPENING_START
    )

    return -(penalized_distance * CONTINUITY_MOVE_PENALTY_PER_FRET)


# ---------------------------------------------------------
# Section 12 -- full pipeline, one tuning at a time
# ---------------------------------------------------------

MAX_CHORD_SHAPE_CANDIDATES = 5  # matches chord_service's own cap


def analyze_tuning_playing_model(score, tuning, chord_service):
    """
    Run the full Playing Model pipeline for one score against
    one tuning -- section 12. For each chord occurrence
    (reusing melody_box_analysis.build_melody_boxes() for the
    phrase window), evaluate every candidate chord shape
    (reusing chord_service.get_shapes()) against the melody
    immediately before and after it, and keep the best-scoring
    shape as that phrase's solution.

    Chordless passages (section 8) are handled by the box model
    itself: a box is only ever bounded by real chord symbols, so
    a long gap between two chords is just a long box, analyzed
    the same way -- no separate mechanism was needed for this.

    Returns a TuningPlayingModelResult.
    """

    raw_boxes = build_melody_boxes(score)

    phrases = []

    previous_box_notes = []

    for harmony, next_harmony, box_notes in raw_boxes:

        lead_in_notes = previous_box_notes[-LEAD_IN_NOTE_COUNT:]

        root_name = pitch_name(harmony.root_pc)

        quality_display = quality_code_to_display_name(
            harmony.quality_code
        )

        candidate_shapes = []

        if quality_display is not None:

            candidate_shapes = chord_service.get_shapes(
                tuning,
                root_name,
                harmony.root_pc,
                harmony.quality_code,
                quality_display
            )[:MAX_CHORD_SHAPE_CANDIDATES]

        best_phrase = None

        for shape in candidate_shapes:

            phrase = evaluate_phrase(
                shape, tuning, harmony, box_notes, lead_in_notes
            )

            if (
                best_phrase is None
                or phrase.score > best_phrase.score
            ):

                best_phrase = phrase

        if best_phrase is None:

            # No usable chord shape for this occurrence (an
            # unrecognized quality, or none playable in this
            # tuning) -- still record the phrase, honestly, with
            # no chord shape rather than skipping it silently.
            best_phrase = PhraseSolution(
                chord=harmony,
                chord_shape=None,
                shape_playability=None,
                lead_in=[],
                box_notes=[],
                fifth_string_bonus=0.0,
                score=0.0
            )

        phrases.append(best_phrase)

        previous_box_notes = box_notes

    continuity_bonus = 0.0

    for index in range(1, len(phrases)):

        continuity_bonus += _continuity_bonus(
            phrases[index - 1], phrases[index]
        )

    total_score = (
        sum(phrase.score for phrase in phrases)
        + continuity_bonus
    )

    return TuningPlayingModelResult(
        tuning_symbol=tuning.symbol,
        phrases=phrases,
        continuity_bonus=continuity_bonus,
        total_score=total_score
    )


# ---------------------------------------------------------
# BO-51 -- chord/melody realization diagnostics
# ---------------------------------------------------------
#
# Read-only, diagnostic-only additions. Nothing above this
# section is modified: evaluate_combination() and realize_note()
# are called exactly as analyze_tuning_playing_model() already
# calls them, reused unchanged. This section does not alter
# scoring, chord-shape selection, or any existing Playing Model
# behavior -- it only exposes, per melody note, the relationship
# BO-51's own investigation found the existing code already had
# enough information to answer but never surfaced as a single,
# inspectable result (see models.ChordMelodyRealization's own
# docstring for the full field list).


def diagnose_melody_chord_realization(
    chord_shape, tuning, harmony, note
):
    """
    BO-51 -- the full relationship between one melody Note and
    one candidate chord shape, for diagnostic inspection.

    Reuses two existing functions completely unchanged for their
    own established computations:
      - evaluate_combination() for voicing_contains_pitch (its
        own `contained_in_chord`, which -- confirmed by reading
        its own implementation -- already checks the chord
        shape's own ACTUAL SOUNDING pitch classes via fretboard.
        sounding_notes(), never chord theory), the best-scoring
        realization, its free_finger status, and the chord's own
        working_fret.
      - melody_box_analysis.realize_note() for every candidate
        realization (fretboard.find_positions(), unmodified) --
        not just the single best one evaluate_combination() itself
        keeps.

    Adds exactly one new piece of information neither existing
    function computes: chord-theory membership, via music.
    chord_tones(harmony.root_pc, harmony.quality_code) -- this is
    what makes it possible to tell a genuinely non-chord-tone
    melody note (chord theory itself doesn't include this pitch
    class at all) apart from a real chord tone this SPECIFIC
    voicing simply doesn't happen to sound. chord_tones() returns
    None for an unrecognized quality code; treated the same as
    "pitch not confirmed to be a chord tone" (chord_contains_
    pitch=False) rather than raising, matching this project's own
    established "unknown quality -> decline gracefully" pattern
    elsewhere (see chord_service.py).

    playable_from_chord_position is deliberately a SEPARATE
    dimension from chord/voicing membership, not folded into
    classification's own hierarchy -- reuses the exact same
    open-string-or-within-working-fret-window test evaluate_
    combination() already applies internally when computing
    free_finger, but WITHOUT free_finger's own additional "string
    not already used by the chord shape" requirement, since a
    melody note can share a hand position with the chord even on
    a string the chord shape itself also uses (a real position
    concept, not a real-time playing-technique one -- BO-51 is
    diagnostic only, not a claim about simultaneous fingering).

    classification is exactly one of the five models.py
    constants, in this priority order:
      1. NON_CHORD_TONE -- chord_contains_pitch is False.
      2. CHORD_TONE_NOT_IN_VOICING -- chord theory includes this
         pitch class, but the actual selected voicing doesn't
         sound it.
      3. CHORD_TONE_IN_VOICING -- chord theory includes it AND
         the voicing sounds it, but it is NOT reachable from the
         chord's own hand position without a position change.
      4. PLAYABLE_FROM_CHORD_POSITION -- chord theory includes
         it, the voicing sounds it, AND it's reachable from the
         chord's own hand position.
    A pitch with no playable realization at all in this tuning
    (candidate_realizations empty) is classified purely on its
    own chord/voicing membership (1 or 2 above); 3 and 4 both
    require a real, playable realization to exist at all.

    Returns a ChordMelodyRealization.
    """

    shape_values = parse_shape(chord_shape.shape)

    working_fret = _chord_working_fret(shape_values)

    combination = evaluate_combination(
        chord_shape.shape, tuning, note
    )

    box_note = realize_note(note, tuning)

    candidate_realizations = list(box_note.realizations)

    best_realization = combination.realization

    melody_pitch_class = note.midi % 12

    melody_octave = (note.midi // 12) - 1

    theoretical_tones = chord_tones(
        harmony.root_pc, harmony.quality_code
    )

    chord_contains_pitch = (
        theoretical_tones is not None
        and melody_pitch_class in theoretical_tones
    )

    voicing_contains_pitch = combination.contained_in_chord

    fret_distance = None

    playable_from_chord_position = False

    if best_realization is not None:

        if best_realization.fret == 0:

            playable_from_chord_position = True

        elif working_fret is not None:

            fret_distance = abs(
                best_realization.fret - working_fret
            )

            playable_from_chord_position = (
                working_fret
                <= best_realization.fret
                <= working_fret + 3
            )

    if not chord_contains_pitch:

        classification = NON_CHORD_TONE

    elif not voicing_contains_pitch:

        classification = CHORD_TONE_NOT_IN_VOICING

    elif playable_from_chord_position:

        classification = PLAYABLE_FROM_CHORD_POSITION

    else:

        classification = AVAILABLE_BUT_POSITION_CHANGE_REQUIRED

    return ChordMelodyRealization(
        chord_symbol=harmony.symbol,
        melody_pitch=note.midi,
        melody_pitch_class=melody_pitch_class,
        melody_octave=melody_octave,
        chord_contains_pitch=chord_contains_pitch,
        voicing_contains_pitch=voicing_contains_pitch,
        candidate_realizations=candidate_realizations,
        best_realization=best_realization,
        working_fret=working_fret,
        fret_distance=fret_distance,
        free_finger_available=combination.free_finger,
        playable_from_chord_position=(
            playable_from_chord_position
        ),
        classification=classification
    )
