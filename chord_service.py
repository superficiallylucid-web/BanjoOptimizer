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

HP_CONTINUITY_QUALITY_TOLERANCE = 0.5  # BO-54 -- see
# get_shapes_for_exact_melody_pitch()'s own sort_key for exactly
# where this is used. NOT an arbitrary new number: BO-42's own
# investigation (whole-song scan across 22 real cases) found the
# voicing_quality_score gap between a chord's full voicing and
# an otherwise-identical one is STRICTLY BIMODAL -- always either
# ~0.5 (the alternative omits only the chord's own non-defining
# 5th) or ~2.0+ (the alternative omits a tone that actually
# defines the chord's own quality -- the 3rd, the 7th, or a sus
# chord's own defining 2nd). Confirmed directly, not assumed, for
# BO-54's own real Cmaj7/aDADE case: the alternative shape within
# this tolerance (quality 21.0 vs the top candidate's 21.5) is
# missing exactly the 5th (G) and nothing else. A candidate more
# than this tolerance below the group's own best quality_score
# never becomes eligible for the HP-continuity tiebreak at all --
# intrinsic chord quality remains dominant outside this narrow,
# evidence-backed band, protecting against a severely awkward
# chord shape winning merely because it happens to fit one
# melody note.


def _capped_position_distance(
    notes, melody_pitches, preferred_melody_fret, melody_strings
):
    """
    BO-33: distance between preferred_melody_fret and the ACTUAL
    fret at which the melody pitch itself sounds within this
    specific candidate -- not the shape's own overall working
    fret (playing_model._chord_working_fret(), which is a
    different value: the shape's own lowest FRETTED position
    across every string, regardless of which one, if any, plays
    the melody note). Confirmed by direct investigation (BO-32)
    that these can diverge: a candidate's overall working fret
    can come from a DIFFERENT string than the one sounding the
    melody pitch, so comparing preferred_melody_fret against the
    wrong string's fret let a shape whose own working position
    happened to be numerically closer win over one where the
    melody note itself was the exact match -- even though the
    tiebreak's entire purpose is "does this candidate's own
    melody-note position match where the melody is likely being
    played."

    notes: this candidate's own sounding_notes(tuning,
    shape.shape) output (REUSED from the caller's own sort_key,
    not recomputed here -- the caller already builds this same
    list for its own contains_melody_pitch check). Each entry
    carries its own string_index (fretboard.SoundingNote,
    unmodified), used here with melody_strings to recover the
    exact fret on that string.

    melody_pitches: the same pitches set already used for
    contains_melody_pitch in the caller.

    melody_strings: tuning.notes[1:] (4th to 1st), the same
    open-string values sounding_notes() itself already used to
    build `notes` -- passed through rather than re-deriving from
    a shape string, since the caller already has it.

    When the melody pitch sounds on more than one string within
    this candidate (a doubled note), the occurrence CLOSEST to
    preferred_melody_fret is used -- not an arbitrary "first by
    string_index" rule. Confirmed necessary by a real regression
    caught via the full test suite: the established Am/aEADE
    example (melody E4) has shape 5320, which sounds E4 on BOTH
    string_index 2 (fret 2) and string_index 3 (fret 0, open) --
    picking the first by string_index order alone would compare
    preferred_melody_fret against fret 2 and miss that fret 0 is
    actually available and exactly matches, causing this
    established shape to lose a tie it should win. Taking the
    minimum distance directly answers this tiebreak's own
    question -- "how close can this shape's own melody-note
    position get to where the melody is likely being played" --
    a shape offering multiple ways to sound the pitch is
    correctly judged by its best one.

    Returns 0 (neutral -- no distance penalty) when
    preferred_melody_fret is None (no playable melody position
    was determined), when melody_pitches is empty, or when none
    of this candidate's own sounding notes actually plays one of
    melody_pitches (this last case should not occur for any
    candidate that reaches this tiebreak in practice, since
    get_shapes_for_exact_melody_pitch()'s own melody-containment
    priority already runs before this one -- returning neutral
    here is a defensive fallback, not load-bearing behavior).
    """

    if preferred_melody_fret is None:

        return 0

    if not melody_pitches:

        return 0

    best_distance = None

    for note in notes:

        if note.midi not in melody_pitches:

            continue

        melody_fret = note.midi - melody_strings[note.string_index]

        distance = min(
            abs(melody_fret - preferred_melody_fret),
            POSITION_DISTANCE_CAP
        )

        if best_distance is None or distance < best_distance:

            best_distance = distance

    if best_distance is None:

        return 0

    return best_distance



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
        preferred_melody_fret=None,
        following_box_notes=None,
        incoming_shape=None
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

        melody_strings = tuning.notes[1:]

        # BO-54 -- HP (Hand Position) continuity. Computed once,
        # outside sort_key, since it needs the group's own max
        # quality_score to define the tolerance window every
        # candidate is checked against.
        max_quality_score = max(
            (s.voicing_quality_score for s in shapes), default=0
        )

        def hp_notes_played(shape):
            """
            BO-54 -- how many of the box's own following melody
            notes (already realize_note()-processed BoxMelodyNote
            objects, reusing melody_box_analysis.realize_note()
            unmodified) can be played without leaving the HP this
            candidate shape's own working fret establishes.

            Reuses the exact same "position N covers frets N..N+3"
            HP geometry, and the exact same open/fretted-position
            check, melody_box_analysis.compute_position_runs()
            itself uses -- not a new, competing HP definition.
            Computed directly for THIS shape's own specific
            working fret, rather than looking that fret up among
            compute_position_runs()'s own pre-enumerated candidate
            starting positions (which are derived only from the
            box notes' own reachable frets, not from any chord
            shape's own working fret at all) -- confirmed via a
            real bug that lookup-based approach caused: The
            Christmas Song's own real Cmaj7/aEADE case had
            working_fret=8, which simply never appeared among the
            box's own candidate positions, so the lookup always
            returned 0 for it regardless of how well it actually
            served the following melody -- silently losing to a
            genuinely less-complete voicing (missing the chord's
            own 5th) that happened to land on a position the
            lookup did recognize.

            Returns 0 when following_box_notes is empty/None, when
            this shape's own working fret is None (an all-open
            shape has no single fretted HP to anchor to), when no
            run in the box starts at that exact fret (the working
            fret doesn't reach any of the box's own notes at
            all), or when this shape's own working fret is more
            than POSITION_DISTANCE_CAP frets from preferred_
            melody_fret.

            That last bound is necessary, not defensive
            decoration: confirmed via a real, direct bug this
            tiebreak produced without it -- White Christmas's own
            real G chord in Open G, box notes B4/B4/B4/E5/D5,
            initially selected a working_fret=21 candidate purely
            because that extreme, barely-reachable position
            happened to keep 4 of 5 box notes technically playable
            (an artifact of very-high frets often covering several
            very-high melody pitches at once), overriding the far
            more practical low-position shape a real player would
            actually use. HP continuity is meant to keep the hand
            from moving AWAY from an already-sensible position, not
            to justify moving TO a distant, impractical one merely
            because it happens to reach more notes -- reusing
            POSITION_DISTANCE_CAP (the same existing bound the
            onset-position tiebreak below already uses, not a new
            number) keeps this tiebreak from ever operating outside
            the same practical neighborhood that tiebreak already
            respects.
            """

            if not following_box_notes:

                return 0

            values = parse_shape(shape.shape)

            if any(v is None for v in values):

                return 0

            working_fret = _chord_working_fret(values)

            if working_fret is None:

                return 0

            if (
                preferred_melody_fret is not None
                and abs(working_fret - preferred_melody_fret)
                > POSITION_DISTANCE_CAP
            ):

                return 0

            # BO-54 -- computed directly for this SPECIFIC
            # working_fret, not via a lookup into compute_
            # position_runs()'s own candidate_positions set.
            # compute_position_runs() only ever considers starting
            # positions derived from the box notes' own reachable
            # frets -- a chord shape's own working fret is not
            # guaranteed to be one of them (confirmed via a real
            # bug this caused: The Christmas Song's own real
            # Cmaj7/aEADE case, working_fret=8, was not among the
            # box's own candidate positions at all despite being
            # a completely reasonable, nearby hand position,
            # incorrectly scoring 0 and losing to a genuinely
            # less-complete voicing that happened to match exactly
            # -- see this function's own updated docstring below
            # for the specific example). Reuses the exact same
            # underlying check compute_position_runs() itself uses
            # (an open note is always playable; a fretted note is
            # playable when this working_fret lies within its own
            # positions_covering_fret() set) -- not a second,
            # competing definition, just applied directly to this
            # one specific fret instead of restricted to the
            # box's own pre-enumerated set.

            notes_played = 0

            for note in following_box_notes:

                playable = (
                    note.has_open_realization
                    or working_fret in note.fretted_positions
                )

                if not playable:

                    break

                notes_played += 1

            return notes_played

        def transition_anchor_count(shape):
            """
            BO-54 REVISION -- how many fretted (non-open) string
            positions this candidate shares EXACTLY with
            incoming_shape, the immediately preceding chord's own
            already-selected shape.

            This is the "incoming HP" signal the original BO-54
            implementation was missing entirely: it only ever
            evaluated a candidate against the FOLLOWING melody,
            never against the hand position the player is already
            in when they arrive at this chord. Confirmed via a
            real case the user's own testing surfaced: The
            Christmas Song's own real C chord (0(10)(10)0, A Modal
            Sawmill) immediately precedes Cmaj7. 0(10)98 shares
            its own fretted 3rd-string 10th fret exactly with C
            (anchor_count=1); 0798 shares no fretted position with
            C at all (anchor_count=0) despite scoring better on
            following-melody continuity alone. The user's own
            direct musical judgment: this incoming-position anchor
            matters more here than the following-melody benefit,
            because that following melody can reach its own low-
            position destination via an open/5th-string bridge
            regardless of which Cmaj7 shape is chosen -- it doesn't
            actually depend on staying near the Cmaj7's own HP at
            all.

            Only FRETTED matches count -- an open string is always
            available from any hand position at all (the same
            reason has_open_realization already lets an open note
            pass hp_notes_played() unconditionally); an open-string
            match reflects no genuine positional continuity and
            would inflate this count without musical meaning.
            Confirmed directly: excluding it is what produces the
            real 1-vs-0 gap above -- including it would give a
            misleading 2-vs-1 (both shapes' own open 4th string
            "matching" C's own open 4th string, which requires no
            hand position at all and proves nothing).

            Returns 0 when incoming_shape is None (no preceding
            chord -- e.g. the first chord of a song) or when this
            candidate's own shape fails to parse.
            """

            if incoming_shape is None:

                return 0

            incoming_values = parse_shape(incoming_shape)

            if any(v is None for v in incoming_values):

                return 0

            candidate_values = parse_shape(shape.shape)

            if any(v is None for v in candidate_values):

                return 0

            return sum(
                1 for i in range(4)
                if incoming_values[i] == candidate_values[i]
                and incoming_values[i] != 0
            )

        def sort_key(shape):

            rank = category_rank.get(
                shape.voicing_quality_category, -1
            )

            notes = sounding_notes(tuning, shape.shape)

            contains_melody_pitch = any(
                note.midi in pitches for note in notes
            )

            # BO-54 -- candidates within HP_CONTINUITY_QUALITY_
            # TOLERANCE of the group's own best quality_score are
            # treated as tied for this purpose (quality_tier=0);
            # everything else keeps deciding purely on quality
            # (quality_tier=1, HP continuity never even consulted).
            # The tolerance (0.5) is not a new, arbitrary number --
            # it's the exact gap BO-42's own investigation already
            # confirmed corresponds specifically to a candidate
            # missing only the chord's own non-defining 5th (never
            # the root/3rd/7th that define the chord's own
            # character) -- real, direct evidence, not a guess
            # (see HP_CONTINUITY_QUALITY_TOLERANCE's own module-
            # level comment for the full citation).
            quality_gap = (
                max_quality_score - shape.voicing_quality_score
            )

            within_hp_tolerance = (
                quality_gap <= HP_CONTINUITY_QUALITY_TOLERANCE
            )

            quality_tier = 0 if within_hp_tolerance else 1

            # BO-124 -- an all-open candidate (working_fret is
            # None) that genuinely sounds the onset melody pitch
            # (already passed contains_melody_pitch above) and is
            # within quality tolerance should never lose to a
            # lower-quality, fretted alternative purely because
            # hp_notes_played() treats "no working fret" as 0
            # phrase coverage. Confirmed real, direct bug this
            # caused: Open C's own C chord (0000, quality 19.5 --
            # tied for the group's own best, and the tuning's own
            # canonical, defining voicing) lost to 0500 (quality
            # 19.0, missing only the non-defining 5th, same as
            # HP_CONTINUITY_QUALITY_TOLERANCE's own citation
            # above) purely because 0500's own working fret
            # happened to reach 4 following notes while 0000's
            # own hp_notes_played() short-circuited to 0 --
            # producing an indefensible high-fret D4 immediately
            # after, in a tuning literally named for this chord's
            # own open voicing. Scoped narrowly to quality_tier=0
            # (a genuinely close-quality alternative outside
            # tolerance still wins normally, unchanged) and to
            # contains_melody_pitch (already computed above, so
            # this never activates for a candidate that doesn't
            # actually sound the melody note at all -- confirmed
            # this is why White Christmas's own real G-chord case,
            # where 0000 does NOT contain that chord's own onset
            # pitch, B4, is completely unaffected: 0000 never
            # reaches this tiebreak there in the first place,
            # since not-containing already excludes it earlier in
            # this same sort key). This does not change anchor_
            # count or notes_played themselves, or their own
            # relative priority -- it only prevents an open
            # candidate that requires no hand movement at all from
            # being treated as reaching nothing.
            open_check_values = parse_shape(shape.shape)

            working_fret_for_open_check = (
                _chord_working_fret(open_check_values)
                if not any(v is None for v in open_check_values)
                else None
            )

            open_shape_preference = (
                0
                if (
                    within_hp_tolerance
                    and contains_melody_pitch
                    and working_fret_for_open_check is None
                )
                else 1
            )

            anchor_count = (
                transition_anchor_count(shape)
                if within_hp_tolerance else 0
            )

            notes_played = (
                hp_notes_played(shape)
                if within_hp_tolerance else 0
            )

            position_distance = _capped_position_distance(
                notes, pitches, preferred_melody_fret,
                melody_strings
            )

            return (
                -rank, not contains_melody_pitch,
                quality_tier, open_shape_preference,
                -anchor_count, -notes_played,
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
