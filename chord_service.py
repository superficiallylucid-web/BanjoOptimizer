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

from music import note_name_to_pitch_class

from fretboard import calculate_shape_metadata


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
        quality_display
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
            quality_display=quality_display
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
        whose top note matches melody_note by pitch class.

        TEMPORARY SIMPLIFICATION: this matches on top_note only
        -- the single highest-sounding note -- not on whether
        melody_note occurs anywhere in the shape. A melody note
        on an inner voice, or doubled across multiple strings,
        isn't recognized as a match here even though it's
        musically present in the chord. fretboard.py now has
        find_melody_occurrences() for that fuller question, but
        this method hasn't been changed to use it yet -- how
        occurrence data should affect ranking is a separate,
        deliberate decision to be made after reviewing that data
        (not part of this pass).

        melody_note: a note name (e.g. "E", "E4") -- octave is
            ignored, since only the pitch class matters here
            (an E melody note is served equally well by a chord
            shape topping out on E3, E4, or E5). Pass None (or
            an unparseable value) to skip matching entirely and
            get exactly get_shapes()'s order back -- that's the
            explicit fallback for "no identifiable melody note"
            rather than a special case to handle separately.

        Ordering rule: every shape whose top_note has the same
        pitch class as melody_note comes first, followed by
        every shape that doesn't -- but WITHIN each of those
        two groups, the relative order from get_shapes() is
        preserved exactly. This is a stable partition, not a
        new score: it deliberately does not re-rank verified
        vs. generated shapes against each other beyond what
        matching/non-matching decides. A matching generated
        shape can end up ahead of a non-matching verified shape
        (matching is evaluated first), but two shapes that both
        match, or both don't, keep whatever order get_shapes()
        already gave them.
        """

        shapes = self.get_shapes(
            tuning,
            root,
            root_pc,
            quality_code,
            quality_display
        )

        target_pitch_class = note_name_to_pitch_class(
            melody_note
        )

        if target_pitch_class is None:

            return shapes


        matching = []

        non_matching = []

        for shape in shapes:

            shape_pitch_class = note_name_to_pitch_class(
                shape.top_note
            )

            if shape_pitch_class == target_pitch_class:

                matching.append(shape)

            else:

                non_matching.append(shape)


        return matching + non_matching
