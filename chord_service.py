"""
chord_service.py

Single interface combining the verified chord library
(chord_library.py) with the dynamic chord generator
(chord_generator.py) into one merged list of chord shapes.

Neither chord_library.py nor chord_generator.py is modified by
this module -- ChordService only calls their existing public
APIs (ChordLibrary.find(), generate_candidates()) and combines
what they return. Each module's responsibility stays exactly
where the architecture proposal put it: chord_library.py loads
and looks up verified/player data; chord_generator.py computes
candidates from fretboard math; chord_service.py is the only
place that knows both exist.

Ranking, for this first version, is intentionally simple:

1. Verified shapes first, in the order ChordLibrary.find()
   returns them.
2. Generated candidates second, in the order
   generate_candidates() returns them -- skipping any shape
   that duplicates one already included from the verified
   list, so the same fret pattern never appears twice.

Generated candidates also pass through playability.py's
rule-based filter before being returned; rejected candidates
are dropped entirely (not just deprioritized). Verified library
shapes are never filtered -- a human already confirmed those,
so a simple rule-based check has nothing useful to add there.

No comfort scoring, chord transitions, or user feedback are
considered here. Those are separate future milestones, not
part of this pass.

get_shapes_for_melody() adds one more factor on top of the
above: preferring shapes whose top note matches a given melody
note (by pitch class). It reorders get_shapes()'s result --
matches first, then everything else -- without changing which
shapes are included or replacing the verified/generated
ordering with a new numerical score. See its own docstring for
the exact rule.

Verified library shapes don't come with top_note/inversion
metadata (chord_library.py never calculates it -- it just loads
CSV rows as-is), so get_shapes() enriches them using the same
shared calculation chord_generator.py uses
(fretboard.calculate_shape_metadata) before returning. This is
enrichment, not a CSV format change -- chord_library.py itself
is untouched.
"""

from chord_generator import generate_candidates

from playability import evaluate as evaluate_playability

from music import (
    note_name_to_pitch_class, chord_tones,
    ROOT_PRESENT, ROOTLESS_STRONG, ROOTLESS_WEAK
)

from fretboard import (
    calculate_shape_metadata,
    find_melody_occurrences,
    classify_melody_realization,
    sounding_notes,
    parse_shape,
    DIRECT_REALIZATION,
    INDIRECT_REALIZATION
)

from playing_model import _chord_working_fret

from models import (
    MelodyRealizationMatch,
    MelodyRealizationDiagnostic,
    ShapeSelectionResult
)


# ---------------------------------------------------------
# Melody realization diagnostic categories
# ---------------------------------------------------------
#
# See diagnose_melody_realization() below. Kept as plain string
# constants next to the function that produces them, matching
# how music.py keeps ROOT_PRESENT/ROOTLESS_STRONG/ROOTLESS_WEAK
# next to classify_voicing_quality().

CHORD_TONE_AND_USABLE_VOICING = "CHORD_TONE_AND_USABLE_VOICING"
CHORD_TONE_BUT_NO_USABLE_VOICING = "CHORD_TONE_BUT_NO_USABLE_VOICING"
NOT_A_CHORD_TONE = "NOT_A_CHORD_TONE"


def diagnose_melody_realization(
    tuning,
    root,
    root_pc,
    quality_code,
    melody_note,
    shapes
):
    """
    Answers two separate questions about one chord occurrence,
    and keeps them separate rather than conflating them:

    1. Is melody_note theoretically a tone of this chord
       (root_pc + quality_code)?
    2. If so, does any of the given (already playable) `shapes`
       actually sound that pitch class somewhere -- on any
       string, not just the top note, and not just an open
       string?

    This is purely diagnostic. It does not pick a replacement
    chord, filter `shapes`, or change ranking -- it exists to
    make the distinction from the My Favorite Things
    investigation (Cmaj7 + melody B, where B is a real chord
    tone but the available shapes didn't put it where the
    arrangement needed it) explicit and reusable, ahead of
    actual chord-substitution work.

    tuning: a Tuning object, passed to find_melody_occurrences()
    root, root_pc, quality_code: the written chord
    melody_note: a note name (e.g. "B3", "B") -- matched by
        pitch class, exactly like find_melody_occurrences()
    shapes: a list of ChordShape -- the already-playable shapes
        to check. Root presence is deliberately NOT used to
        exclude anything here; music.classify_voicing_quality()
        already handles that as a separate ranking concern, and
        this diagnostic reports whichever shapes actually
        contain the melody note regardless of their root/
        voicing-quality standing.

    Returns a MelodyRealizationDiagnostic. category is one of:

    - NOT_A_CHORD_TONE: melody_note isn't part of this chord at
      all -- matches is always empty in this case.
    - CHORD_TONE_BUT_NO_USABLE_VOICING: melody_note IS a chord
      tone, but none of `shapes` sounds it anywhere.
    - CHORD_TONE_AND_USABLE_VOICING: melody_note is a chord
      tone AND at least one shape in `shapes` sounds it -- see
      matches for exactly where.
    """

    tones = chord_tones(root_pc, quality_code)

    if tones is None:

        return MelodyRealizationDiagnostic(
            category=NOT_A_CHORD_TONE,
            root=root,
            quality_code=quality_code,
            melody_note=melody_note,
            matches=[]
        )

    target_pitch_class = note_name_to_pitch_class(melody_note)

    if target_pitch_class is None or target_pitch_class not in tones:

        return MelodyRealizationDiagnostic(
            category=NOT_A_CHORD_TONE,
            root=root,
            quality_code=quality_code,
            melody_note=melody_note,
            matches=[]
        )

    matches = []

    melody_strings = tuning.notes[1:]

    for shape in shapes:

        occurrences = find_melody_occurrences(
            tuning, shape.shape, melody_note
        )

        for occurrence in occurrences:

            open_note = melody_strings[occurrence.string_index]

            fret = occurrence.midi - open_note

            matches.append(
                MelodyRealizationMatch(
                    shape=shape.shape,
                    source=shape.source,
                    voicing_quality_category=(
                        shape.voicing_quality_category
                    ),
                    string_index=occurrence.string_index,
                    fret=fret,
                    sounding_note=occurrence.name
                )
            )

    category = (
        CHORD_TONE_AND_USABLE_VOICING
        if matches
        else CHORD_TONE_BUT_NO_USABLE_VOICING
    )

    return MelodyRealizationDiagnostic(
        category=category,
        root=root,
        quality_code=quality_code,
        melody_note=melody_note,
        matches=matches
    )


POSITION_DISTANCE_CAP = 5  # frets; matches playing_model.py's
# own CONTINUITY_MOVE_DAMPENING_START, reused for consistency
# rather than inventing a new number. Caps how much a candidate
# can be penalized for being far from the melody's preferred
# position -- this is a TIEBREAK among candidates already tied
# on category and melody-pitch-containment (see
# get_shapes_for_exact_melody_pitch()'s own docstring), so
# capping it here is defensive, not load-bearing: it can never
# reach past those two priorities regardless, but a cap keeps
# it from ever growing large enough to swamp the further,
# lower-priority playability tiebreak below it either.


def _capped_position_distance(shape, preferred_melody_fret):
    """
    BO-22: distance between a candidate ChordShape's own working
    fret (playing_model._chord_working_fret() -- REUSED
    unmodified, not a competing definition) and
    preferred_melody_fret, capped at POSITION_DISTANCE_CAP.

    Returns 0 (neutral -- no distance penalty) when
    preferred_melody_fret is None (no playable melody position
    was determined) or when the shape has no working fret at all
    (an all-open shape has no hand position to be distant from,
    matching playing_model._continuity_bonus()'s own handling of
    this same case).
    """

    if preferred_melody_fret is None:

        return 0

    working_fret = _chord_working_fret(parse_shape(shape.shape))

    if working_fret is None:

        return 0

    return min(
        abs(working_fret - preferred_melody_fret),
        POSITION_DISTANCE_CAP
    )


class ChordService:
    """
    Combines a ChordLibrary (verified/player data) with the
    dynamic chord generator into one merged list of chord
    shapes per (tuning, root, quality).
    """

    def __init__(self, chord_library):

        self.chord_library = chord_library


    def get_shapes(
        self,
        tuning,
        root,
        root_pc,
        quality_code,
        quality_display,
        melody_pitches=None
    ):
        """
        Return one merged, deduplicated list of ChordShapes
        for one chord in one tuning: verified shapes first
        (library order preserved), then generated candidates
        that aren't already covered by a verified shape
        (generator order preserved).

        tuning: a Tuning object. .symbol is used for the
            library lookup; the whole object is passed through
            to generate_candidates(), which uses .notes.
        root, quality_display: display strings, e.g. "C",
            "Major" -- must match how they're stored in the
            library CSV for the verified lookup to match.
        root_pc, quality_code: used only for chord generation,
            e.g. 0, "" for C major.
        melody_pitches: optional set/list of exact MIDI values,
            forwarded unchanged to generate_candidates() (BO-20)
            -- see that function's own docstring for exactly
            what this does (widens the per-string search when
            needed to reach a specific melody pitch; never
            affects verified/library shapes, and never bypasses
            playability.py's own acceptance check). None (the
            default) reproduces the exact prior behavior.

        Each returned ChordShape has .source set to "verified"
        or "generated" (see ChordShape in models.py) so callers
        can tell them apart reliably, regardless of what the
        `verified` field itself says. Verified shapes also get
        .inversion/.top_note calculated here (chord_library.py
        doesn't set them), so melody matching works the same
        way for verified and generated shapes alike.
        """

        verified_shapes = self.chord_library.find(
            tuning.symbol,
            root,
            quality_display
        )

        for shape in verified_shapes:

            shape.source = "verified"

            inversion, top_note = calculate_shape_metadata(
                tuning,
                shape.shape,
                root_pc,
                quality_code
            )

            if inversion is not None:

                shape.inversion = inversion

            if top_note is not None:

                shape.top_note = top_note


        generated_shapes = generate_candidates(
            tuning=tuning,
            root=root,
            root_pc=root_pc,
            quality_code=quality_code,
            quality_display=quality_display,
            melody_pitches=melody_pitches
        )

        verified_shape_strings = {
            shape.shape for shape in verified_shapes
        }

        new_generated_shapes = []

        for shape in generated_shapes:

            if shape.shape in verified_shape_strings:

                continue

            if not evaluate_playability(shape.shape).accepted:

                continue

            shape.source = "generated"

            new_generated_shapes.append(shape)


        return verified_shapes + new_generated_shapes


    def get_shapes_for_exact_melody_pitch(
        self,
        tuning,
        root,
        root_pc,
        quality_code,
        quality_display,
        melody_pitches,
        preferred_melody_fret=None
    ):
        """
        Same result as get_shapes(), reordered to strongly
        prefer shapes that sound at least one of melody_pitches
        somewhere among their sounding notes -- BO-20. Also
        prefers, as a narrower tiebreak among otherwise-equal
        candidates, a chord shape whose own working position is
        close to where the melody note is likely actually being
        played -- BO-22.

        melody_pitches: a set/list of EXACT MIDI values (e.g.
        the melody note(s) occurring at a chord's exact musical
        onset -- pass more than one when multiple melody notes
        share that same location, such as a block chord within
        the melody line itself; see
        score_generator._melody_notes_at_harmony_onset(), which
        is what actually builds this set from real melody data).
        Pass None or an empty collection to get exactly
        get_shapes()'s order back unchanged -- the explicit
        fallback for "no melody note at this chord's location."

        Deliberately compares EXACT pitch (MIDI value), not
        merely pitch class -- unlike get_shapes_for_melody()
        above, which matches by pitch class for a different,
        pre-existing purpose (melody-realization diagnostics,
        where "some octave of this note" is the right question).
        Here, a chord shape is meant to directly SUPPORT a
        specific melody note being played at that moment, so it
        needs to sound that exact note, not just some octave of
        it. Reuses fretboard.sounding_notes() unmodified -- no
        new pitch representation introduced.

        preferred_melody_fret: BO-22, optional -- the fret the
        melody note is likely actually played at (see
        score_generator._apply_chord_shapes(), which computes
        this via the EXISTING fretboard.find_positions()/
        best_position(), not a new position representation).
        None (the default) disables this tiebreak entirely,
        reproducing BO-20/21's own prior ranking exactly -- the
        explicit fallback for "no playable melody position could
        be determined."

        Ranking, in priority order (BO-22-FOLLOWUP fixed a real
        defect in step 3/4's original ordering -- see below):

        1. Voicing quality CATEGORY (ROOT_PRESENT /
           ROOTLESS_STRONG / ROOTLESS_WEAK -- see
           music.classify_voicing_quality()). Never crossed by
           anything below -- a clearly superior, complete
           voicing is never sacrificed for an inferior one, no
           matter how well the inferior one matches the melody
           pitch or its position.
        2. Exact melody-pitch containment, WITHIN the same
           category (BO-20's own priority, unchanged).
        3. The finer-grained voicing_quality_score itself (BO-22-
           FOLLOWUP, NEW position in the ordering): within the
           same category and melody-match outcome, a candidate
           with a HIGHER quality_score (e.g. one that happens to
           include the non-defining 5th, or otherwise covers more
           of the chord) is preferred before position is ever
           consulted. This closes a real bug found by direct
           investigation: for Cmaj7 in aEADE with melody B4, a
           complete C-E-G-B voicing (quality_score 21.5) was
           previously losing to an incomplete C-E-B voicing
           (quality_score 21.0) purely because the incomplete one
           happened to sit one fret closer to the melody's
           preferred position -- step 3 previously only checked
           category (coarse), never the finer quality_score that
           actually distinguished the two candidates, so a real,
           meaningful quality difference was being swallowed into
           the "tied" bucket that position then decided. The
           fix does not touch how quality_score itself is
           computed (music.classify_voicing_quality(), unchanged)
           -- only where it participates in this ranking.
        4. Positional compatibility (BO-22): among candidates
           still tied after all three priorities above, prefer
           the one whose own working fret (see
           playing_model._chord_working_fret() -- REUSED
           unmodified, not a competing definition: a chord's
           lowest FRETTED position, ignoring open strings, which
           correctly still resolves to None/neutral for an all-
           open shape) is closer to preferred_melody_fret. The
           distance is CAPPED (see POSITION_DISTANCE_CAP below)
           so it can only ever break a tie among otherwise-equal
           candidates -- it can never grow large enough to
           overwhelm any priority above it, and it never even
           activates unless a candidate already survived all of
           them.
        5. The existing playability_score tiebreak (BO-18/
           unchanged), preserved automatically by Python's
           stable sort -- get_shapes()'s own prior ordering
           (quality score, then playability, then verified-
           before-generated) is otherwise kept exactly as-is
           within each (category, melody-match, quality_score,
           position-distance) group.

        This is entirely additive: passing preferred_melody_fret
        =None (its default) reproduces BO-20/21's own ranking
        with no change at all, and every existing caller that
        doesn't pass it is completely unaffected.
        """

        shapes = self.get_shapes(
            tuning, root, root_pc, quality_code, quality_display,
            melody_pitches=melody_pitches
        )

        pitches = set(melody_pitches) if melody_pitches else set()

        if not pitches:

            return shapes

        category_rank = {
            ROOT_PRESENT: 2,
            ROOTLESS_STRONG: 1,
            ROOTLESS_WEAK: 0
        }

        def sort_key(shape):

            rank = category_rank.get(
                shape.voicing_quality_category, -1
            )

            notes = sounding_notes(tuning, shape.shape)

            contains_melody_pitch = any(
                note.midi in pitches for note in notes
            )

            position_distance = _capped_position_distance(
                shape, preferred_melody_fret
            )

            return (
                -rank, not contains_melody_pitch,
                -shape.voicing_quality_score,
                position_distance
            )

        return sorted(shapes, key=sort_key)


    def get_shapes_for_melody(
        self,
        tuning,
        root,
        root_pc,
        quality_code,
        quality_display,
        melody_note
    ):
        """
        Same result as get_shapes(), reordered to prefer shapes
        that actually sound melody_note SOMEWHERE -- on any
        string, not just the highest one. Uses
        fretboard.find_melody_occurrences() for the match check,
        so a melody note on an inner voice, or doubled across
        multiple strings, is recognized exactly the same as one
        that happens to be the top note.

        This replaces an earlier version that matched on
        top_note only (see git history / prior versions of this
        docstring if you need the reasoning for why that was a
        deliberate, temporary simplification at the time --
        find_melody_occurrences() didn't exist yet when this
        method was first built).

        melody_note: a note name (e.g. "E", "E4") -- octave is
            ignored, since only the pitch class matters here
            (an E melody note is served equally well by a chord
            shape sounding E3, E4, or E5 anywhere in it). Pass
            None (or an unparseable value) to skip matching
            entirely and get exactly get_shapes()'s order back
            -- that's the explicit fallback for "no identifiable
            melody note" rather than a special case to handle
            separately.

        Ordering rule: DIRECT_REALIZATION shapes first (melody
        note is the top/lead voice), then INDIRECT_REALIZATION
        shapes (melody note sounds somewhere, but not as the
        top note), then NO_REALIZATION shapes -- see
        fretboard.classify_melody_realization(). WITHIN each of
        those three groups, the relative order from get_shapes()
        is preserved exactly. This is a stable 3-way partition,
        not a new numerical score: it deliberately does not
        re-rank verified vs. generated shapes against each other
        beyond what realization tier decides. A directly-
        realizing generated shape can end up ahead of a non-
        realizing verified shape (tier is evaluated first), but
        two shapes in the same tier keep whatever order
        get_shapes() already gave them.
        """

        shapes = self.get_shapes(
            tuning,
            root,
            root_pc,
            quality_code,
            quality_display
        )

        if note_name_to_pitch_class(melody_note) is None:

            return shapes


        direct = []

        indirect = []

        unrealized = []

        for shape in shapes:

            tier = classify_melody_realization(
                tuning, shape.shape, melody_note
            )

            if tier == DIRECT_REALIZATION:

                direct.append(shape)

            elif tier == INDIRECT_REALIZATION:

                indirect.append(shape)

            else:

                unrealized.append(shape)


        return direct + indirect + unrealized


    def select_shape_for_melody(
        self,
        tuning,
        root,
        root_pc,
        quality_code,
        quality_display,
        melody_note
    ):
        """
        Pick the single best shape for one chord+melody
        occurrence, and make explicit how well it actually
        realizes the melody -- architecture for future chord-
        substitution work, not substitution logic itself.

        Returns a ShapeSelectionResult (see models.py):

        - selected_shape: the top of
          get_shapes_for_melody()'s 3-tier ranking (DIRECT_
          REALIZATION first, then INDIRECT_REALIZATION, then
          NO_REALIZATION) -- so this is always the best
          available shape, even when nothing realizes the
          melody well. None only if get_shapes_for_melody()
          returned nothing at all (e.g. an unrecognized chord
          quality), which is different from "shapes exist but
          none of them work."
        - realization_tier: selected_shape's own tier -- check
          this (or diagnosis.category) rather than assuming a
          non-None selected_shape means the melody is properly
          realized. A NO_REALIZATION selected_shape is a real,
          legitimate result: the best playable option that
          exists, honestly labeled as not realizing the melody,
          not silently presented as if it did.
        - diagnosis: the existing aggregate answer (see
          diagnose_melody_realization()) -- whether melody_note
          is even a theoretical chord tone, and whether ANY
          shape in the full list realizes it. This is the
          clearest single signal for "this chord+melody
          combination can't be properly realized" -- check
          diagnosis.category != CHORD_TONE_AND_USABLE_VOICING
          for that.
        - all_shapes_ranked: the full list, for deeper
          diagnostics only -- not needed for the concise
          answer.
        """

        ranked_shapes = self.get_shapes_for_melody(
            tuning,
            root,
            root_pc,
            quality_code,
            quality_display,
            melody_note
        )

        diagnosis = diagnose_melody_realization(
            tuning,
            root,
            root_pc,
            quality_code,
            melody_note,
            ranked_shapes
        )

        if not ranked_shapes:

            return ShapeSelectionResult(
                selected_shape=None,
                realization_tier="",
                diagnosis=diagnosis,
                all_shapes_ranked=[]
            )

        selected_shape = ranked_shapes[0]

        realization_tier = classify_melody_realization(
            tuning, selected_shape.shape, melody_note
        )

        return ShapeSelectionResult(
            selected_shape=selected_shape,
            realization_tier=realization_tier,
            diagnosis=diagnosis,
            all_shapes_ranked=ranked_shapes
        )
