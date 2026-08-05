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

No comfort scoring, melody matching, chord transitions, user
feedback, or playability heuristics are considered here. Those
are separate future milestones, not part of this pass.
"""

from chord_generator import generate_candidates


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
        `verified` field itself says.
        """

        verified_shapes = self.chord_library.find(
            tuning.symbol,
            root,
            quality_display
        )

        for shape in verified_shapes:

            shape.source = "verified"


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

            shape.source = "generated"

            new_generated_shapes.append(shape)


        return verified_shapes + new_generated_shapes
