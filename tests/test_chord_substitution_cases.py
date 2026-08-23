"""
tests/test_chord_substitution_cases.py

Validates the factual claims in chord_substitution_cases.py
against the project's existing music-theory utilities
(music.chord_tones) -- NOT a test of any production
substitution algorithm, since none exists yet.

Also includes a descriptive (non-asserting) function that
records what the current chord library/generator/service
pipeline actually produces for each case's original chord in
aEADE, and whether the melody note appears anywhere in those
shapes. This is a baseline recording, not a pass/fail check --
"is a given occurrence musically preferable" is explicitly
future work (see fretboard.find_melody_occurrences's own
docstring history).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music import chord_tones, note_name_to_pitch_class

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from fretboard import find_melody_occurrences

from chord_substitution_cases import SUBSTITUTION_CASES, VAMP_CASES


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _service():

    # No verified library CSV data exists for aEADE -- the
    # only chord library CSV in this project is for gDGBD.
    # An unloaded ChordLibrary is correct here: find() just
    # returns [] for a tuning it has no data for, and
    # get_shapes() falls back to generated candidates only.
    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# THE MOST IMPORTANT REQUIREMENT: every case documented here
# must be Case 1 (melody note IS a chord tone of the original
# chord), never Case 2 (melody note missing from the chord).
# ---------------------------------------------------------

def test_every_case_melody_note_is_original_chord_tone():

    for case in SUBSTITUTION_CASES:

        tones = chord_tones(
            case.original_root_pc, case.original_quality_code
        )

        assert tones is not None, (
            f"m{case.measure}: unrecognized original quality "
            f"code {case.original_quality_code!r}"
        )

        melody_pc = note_name_to_pitch_class(case.melody_note)

        assert melody_pc is not None, (
            f"m{case.measure}: melody note "
            f"{case.melody_note!r} could not be parsed"
        )

        assert melody_pc in tones, (
            f"m{case.measure}: melody {case.melody_note} is NOT "
            f"a chord tone of {case.original_root}"
            f"{case.original_quality_display} -- this would be a "
            "Case 2 (melody not in chord) situation, but every "
            "case in this file is documented as Case 1"
        )


def test_every_replacement_also_contains_the_melody_note():

    for case in SUBSTITUTION_CASES:

        tones = chord_tones(
            case.replacement_root_pc,
            case.replacement_quality_code
        )

        assert tones is not None

        melody_pc = note_name_to_pitch_class(case.melody_note)

        assert melody_pc in tones, (
            f"m{case.measure}: replacement "
            f"{case.replacement_root}"
            f"{case.replacement_quality_display} does not "
            f"actually contain the melody note "
            f"{case.melody_note} -- that would undermine the "
            "premise of the substitution"
        )


# ---------------------------------------------------------
# The Ebdim -> B7 / A7 pair: same original chord, different
# replacement, different melody note
# ---------------------------------------------------------

def test_ebdim_cases_have_different_replacements_for_different_melody():

    ebdim_cases = [
        case for case in SUBSTITUTION_CASES
        if case.original_root == "Eb"
        and case.original_quality_code == "mb5"
    ]

    assert len(ebdim_cases) == 2

    melody_notes = {case.melody_note for case in ebdim_cases}

    replacements = {
        (case.replacement_root, case.replacement_quality_code)
        for case in ebdim_cases
    }

    assert len(melody_notes) == 2, (
        "expected the two Ebdim cases to have different melody "
        "notes"
    )

    assert len(replacements) == 2, (
        "expected the two Ebdim cases to have different "
        "replacement chords -- this is the core evidence that "
        "substitution depends on melody note, not just the "
        "original chord"
    )


# ---------------------------------------------------------
# The color/addition case must stay structurally distinct
# from the real substitution cases
# ---------------------------------------------------------

def test_color_addition_case_keeps_the_same_root():

    color_cases = [
        case for case in SUBSTITUTION_CASES
        if case.category == "chord_color_addition"
    ]

    assert len(color_cases) == 1

    case = color_cases[0]

    assert case.original_root == case.replacement_root, (
        "a color/addition case should keep the same root -- if "
        "the root changes too, it's a substitution, not a color "
        "addition, and belongs in a different category"
    )


def test_substitution_cases_actually_change_something():

    substitution_categories = {
        "melody_realization_upper_structure",
        "melody_driven_dominant_substitution",
    }

    for case in SUBSTITUTION_CASES:

        if case.category not in substitution_categories:

            continue

        changed = (
            case.original_root != case.replacement_root
            or (
                case.original_quality_code
                != case.replacement_quality_code
            )
        )

        assert changed, (
            f"m{case.measure}: categorized as a substitution but "
            "root and quality are identical to the original"
        )


# ---------------------------------------------------------
# Vamp elaboration: every shape in the sequence must be a
# valid subset of the sustained original chord's tones
# ---------------------------------------------------------

def test_vamp_sequence_shapes_are_subsets_of_sustained_chord():

    short_label_to_code = {
        "5": "5",
        "sus2": "sus2",
        "minor": "m"
    }

    for case in VAMP_CASES:

        # music.chord_tones() doesn't support "add9"-family
        # quality codes yet (its full registered set is just
        # ['', 'm', '7', 'm7', 'maj7', 'mb5', '5', 'sus2',
        # 'sus4'] -- confirmed by inspection). Adding "add9"
        # support there is out of scope for this task (it would
        # be changing production chord logic), so the sustained
        # chord's tones are computed directly here instead: a
        # minor add9 is root + minor 3rd + 5th + 9th (NOT the
        # 7th -- that's what distinguishes "add9" from "9").
        root_pc = case.original_root_pc

        original_tones = {
            root_pc,               # root
            (root_pc + 3) % 12,    # minor 3rd
            (root_pc + 7) % 12,    # 5th
            (root_pc + 2) % 12,    # added 9th (same pitch
                                    # class as the 2nd)
        }

        for root_name, quality_label in case.replacement_sequence:

            root_pc = note_name_to_pitch_class(root_name)

            quality_code = short_label_to_code[quality_label]

            tones = set(chord_tones(root_pc, quality_code))

            assert tones.issubset(original_tones), (
                f"{root_name}{quality_label} is not a subset of "
                f"the sustained {case.original_root}"
                f"{case.original_quality_display} harmony"
            )


# ---------------------------------------------------------
# Descriptive baseline (not asserted pass/fail): what the
# CURRENT pipeline actually produces today. Run manually to
# see current behavior -- see this module's docstring.
# ---------------------------------------------------------

def record_current_pipeline_behavior():

    service = _service()

    for case in SUBSTITUTION_CASES:

        shapes = service.get_shapes(
            A_MODAL_SAWMILL,
            case.original_root,
            case.original_root_pc,
            case.original_quality_code,
            case.original_quality_display
        )

        print(
            f"m{case.measure} {case.original_root}"
            f"{case.original_quality_display} "
            f"(melody {case.melody_note}): "
            f"{len(shapes)} playable shape(s) found"
        )

        for shape in shapes:

            occurrences = find_melody_occurrences(
                A_MODAL_SAWMILL, shape.shape, case.melody_note
            )

            if occurrences:

                locations = ", ".join(
                    f"string {o.string_index} ({o.name})"
                    for o in occurrences
                )

                print(
                    f"    {shape.shape}: melody found at "
                    f"{locations}"
                )

            else:

                print(
                    f"    {shape.shape}: melody note not present"
                )
