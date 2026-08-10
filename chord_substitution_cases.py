"""
tests/chord_substitution_cases.py

Real-world chord substitution/voicing examples extracted from
the user's "My Favorite Things" arrangement (key E minor,
banjo tuning aEADE / "A Modal Sawmill"), documenting decisions
Banjo Optimizer should eventually be able to explain or
reproduce.

This is a specification/data module -- there is no production
substitution algorithm yet (explicitly out of scope for this
task). See test_chord_substitution_cases.py for validation of
the factual claims made here.

Two case categories, kept structurally distinct on purpose --
see the "MOST IMPORTANT REQUIREMENT" this was built against:

CASE 1 (all SubstitutionCase entries with category
"melody_realization_upper_structure" or
"melody_driven_dominant_substitution"): the melody note IS a
chord tone of the original chord, but no playable banjo shape
puts it in a useful position -- so a different (but related)
chord is used instead. NOT a "melody note missing from chord"
problem.

"chord_color_addition": a different, smaller category --
same root, an added color tone, not a real substitution. Kept
separate so future work doesn't treat every arrangement
difference as melody-driven substitution.

VampElaborationCase: a third, different phenomenon -- one
sustained original harmony realized as a short sequence of
related practical shapes, not a single substitute. Explicitly
NOT implemented; recorded here as a distinct future problem.

Quality codes vs quality display: quality_code values (e.g.
"maj7", "mb5") match music.chord_tones()'s internal convention;
quality_display values (e.g. "Maj 7", "dim") match
chord_library.py's CSV column convention. These are
deliberately two different strings, per the existing
architecture -- see chord_service.get_shapes()'s own two
parameters for the same split.
"""

from dataclasses import dataclass, field


@dataclass
class SubstitutionCase:
    """
    A single-point chord substitution: one original chord at
    one melody position, replaced by one different chord.
    """

    measure: int

    beat: int  # 1-indexed, matching how musicians count beats

    melody_note: str

    original_root: str
    original_root_pc: int
    original_quality_code: str
    original_quality_display: str

    replacement_root: str
    replacement_root_pc: int
    replacement_quality_code: str
    replacement_quality_display: str

    category: str

    explanation: str

    tuning_symbol: str = "aEADE"


@dataclass
class VampElaborationCase:
    """
    A sustained original harmony realized as a short sequence
    of different practical banjo shapes/chords, rather than a
    single substitute. Distinct category -- see module
    docstring.
    """

    measures: str  # descriptive range, e.g. "5-10"

    original_root: str
    original_root_pc: int
    original_quality_code: str
    original_quality_display: str

    # Each entry: (root_name, short_quality_label). Short
    # labels used here ("5", "sus2", "minor") are resolved to
    # chord_tones() quality codes by the validation test, not
    # meant as a general-purpose quality vocabulary.
    replacement_sequence: list

    category: str

    explanation: str

    tuning_symbol: str = "aEADE"


SUBSTITUTION_CASES = [

    SubstitutionCase(
        measure=49, beat=2, melody_note="B3",
        original_root="C", original_root_pc=0,
        original_quality_code="maj7", original_quality_display="Maj 7",
        replacement_root="E", replacement_root_pc=4,
        replacement_quality_code="m", replacement_quality_display="minor",
        category="melody_realization_upper_structure",
        explanation=(
            "B is a chord tone of Cmaj7 (C-E-G-B), so this is NOT a "
            "missing-chord-tone case. The available playable Cmaj7 "
            "shapes in aEADE did not put B in a useful melody "
            "position (an alternate B location exists, e.g. 4th "
            "string 7th fret, but not where the player needed it). "
            "Em is the upper triad of Cmaj7 (its 3rd/5th/7th, "
            "omitting the root) and provides B in a practical, "
            "comfortable playable position. An upper-structure/"
            "subset substitution driven by melody realization, not "
            "harmonic necessity."
        )
    ),

    SubstitutionCase(
        measure=31, beat=2, melody_note="B3",
        original_root="C", original_root_pc=0,
        original_quality_code="maj7", original_quality_display="Maj 7",
        replacement_root="E", replacement_root_pc=4,
        replacement_quality_code="m", replacement_quality_display="minor",
        category="melody_realization_upper_structure",
        explanation=(
            "Identical case to measure 49 -- same original chord, "
            "same melody note, same replacement. An earlier "
            "occurrence of the same musical decision."
        )
    ),

    SubstitutionCase(
        measure=38, beat=1, melody_note="D#4",
        original_root="Eb", original_root_pc=3,
        original_quality_code="mb5", original_quality_display="dim",
        replacement_root="B", replacement_root_pc=11,
        replacement_quality_code="7", replacement_quality_display="Dom 7",
        category="melody_driven_dominant_substitution",
        explanation=(
            "D# is a chord tone of both Ebdim and B7 (D# is B7's "
            "third). Ebdim and B7 share 3 of their 4 tones (a "
            "diminished chord functions as a substitute dominant "
            "for chords a minor third apart). A genuine chord "
            "substitution -- root and quality both change, not a "
            "re-voicing. See measure 59 for the same original chord "
            "resolved a different way with a different melody note."
        )
    ),

    SubstitutionCase(
        measure=59, beat=1, melody_note="A4",
        original_root="Eb", original_root_pc=3,
        original_quality_code="mb5", original_quality_display="dim",
        replacement_root="A", replacement_root_pc=9,
        replacement_quality_code="7", replacement_quality_display="Dom 7",
        category="melody_driven_dominant_substitution",
        explanation=(
            "A is the root of A7, and also a chord tone of Ebdim. "
            "Same original chord (Ebdim) as measure 38, but resolved "
            "differently because the melody note differs (A vs D#). "
            "The strongest evidence that substitution cannot be a "
            "fixed original-chord -> replacement-chord lookup: it "
            "must consider melody note + key + playable shapes "
            "together."
        )
    ),

    SubstitutionCase(
        measure=68, beat=1, melody_note="A3",
        original_root="A", original_root_pc=9,
        original_quality_code="", original_quality_display="Major",
        replacement_root="A", replacement_root_pc=9,
        replacement_quality_code="sus4", replacement_quality_display="sus4",
        category="chord_color_addition",
        explanation=(
            "Same root, same melody note (A, the root of both "
            "chords) -- only the quality changes, adding a color "
            "tone (sus4). Deliberately a different category from "
            "the substitutions above: the melody isn't being "
            "rescued into a different chord, since plain A already "
            "provides A cleanly. Included so future development "
            "doesn't treat every score/arrangement difference as a "
            "melody-driven substitution."
        )
    ),

]


VAMP_CASES = [

    VampElaborationCase(
        measures="5-10",
        original_root="E", original_root_pc=4,
        original_quality_code="m(add9)",
        original_quality_display="m(add9)",
        replacement_sequence=[
            ("E", "5"),
            ("E", "5"),
            ("E", "sus2"),
            ("E", "minor"),
            ("E", "5"),
        ],
        category="harmonic_elaboration_sustained_chord",
        explanation=(
            "The original harmony is essentially static (Em / "
            "Em(add9), held for full phrases). The banjo "
            "arrangement instead moves through a short sequence of "
            "related, practical shapes (E5, E5, Esus2, Em, E5) "
            "under the same sustained function -- decorating/"
            "animating a static chord rather than substituting it "
            "for a different one. Every shape in the sequence is a "
            "coherent subset of the underlying Em(add9) (a power "
            "chord, a sus2 reading of the added 9th, and the plain "
            "triad). Explicitly NOT implemented -- a different "
            "future problem (multiple voicings over one sustained "
            "harmony) from single-point chord substitution."
        )
    ),

]
