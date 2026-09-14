"""
tests/test_bo174_non_matching_anchor_hp_continuity.py

Focused tests for BO-174: a preceding chord anchor must only
suppress the alternative hand-position continuity mechanisms
(hp_tiebreak, within_hp_offset) when it actually provides a
position for the current melody pitch -- not merely because it
exists and is still "relevant" (hand hasn't left its own HP span).

Root cause: no_chord_anchor_at_all treated "preceding_chord_shape_
values is not None" as sufficient to disable hp_tiebreak/within_hp_
offset, even when that shape's own _fd_positions_for_pitch() match
for this exact pitch was empty (a genuine passing tone). The fix
widens the condition to also require preceding_chord_anchor_
matches_pitch (built from the existing preceding_fd_matches set --
no second, independent match definition) whenever the chord is
still relevant.

All three tests go through main.run_optimizer() -- the real,
GUI-equivalent production path (capo/5th-string are only ever
correctly applied there, not by calling generate_tab_from_
template() directly with parameters it doesn't accept).
"""

import sys

sys.path.insert(0, '.')

import main

from parser import MuseScoreFile

from conftest import fixture_path, TEST_OUTPUT_DIR


def _generate():

    result = main.run_optimizer(
        score_path=str(fixture_path("BO-174_input_score.mscz")),
        tuning_symbol="gCGCD",
        capo=2,
        fifth_string="A",
        output_folder=str(TEST_OUTPUT_DIR),
        output_key="D"
    )

    return result["scores"][0]["generated_files"][0]["tab_path"]


def _positions_by_measure_beat(tab_path):

    p = MuseScoreFile(tab_path)

    p.open()

    staff = p.root.find('.//{*}Staff[@id="1"]')

    measures = staff.findall("{*}Measure")

    positions = {}

    for m_idx, measure in enumerate(measures, start=1):

        for voice in measure.findall("{*}voice"):

            beat = 0.0

            for element in voice:

                tag = element.tag.split("}")[-1]

                if tag in ("Chord", "Rest"):

                    duration = p._duration_value(element)

                    if tag == "Chord":

                        for note in element.findall("{*}Note"):

                            pitch_el = note.find("{*}pitch")

                            fret_el = note.find("{*}fret")

                            string_el = note.find("{*}string")

                            if (
                                pitch_el is not None
                                and fret_el is not None
                            ):

                                # 1-indexed string and 1-indexed
                                # beat, matching the ticket's own
                                # "measure N, beat B, tab S-F"
                                # notation throughout.
                                positions[
                                    (m_idx, round(beat + 1, 4))
                                ] = (
                                    int(string_el.text) + 1,
                                    int(fret_el.text)
                                )

                    beat += duration

    return positions


# ---------------------------------------------------------
# 1 -- a representative non-matching passing tone: a preceding
# chord anchor (F#m7, measure 1 beat 1) is still relevant, but
# does not contain the pitch at measure 1 beat 3.5 -- hp_tiebreak
# must no longer be suppressed merely because the anchor exists.
# ---------------------------------------------------------

def test_non_matching_preceding_chord_no_longer_suppresses_hp_tiebreak():

    positions = _positions_by_measure_beat(_generate())

    # Real, confirmed BO-174 example: previously stuck at (1, 3)
    # (string 1, fret 3 -- the ticket's own "assigned" defect
    # value); now correctly lands on the ticket's own "preferred"
    # (2, 5) -- the position much closer to the immediately
    # preceding note's own hand position, instead of a low-fret
    # jump to a different string.
    assert positions[(1, 3.5)] == (2, 5)


# ---------------------------------------------------------
# 2 -- a genuine chord-anchored note: preceding_fd_violation
# actually finds a match (measure 3's own real exact-anchor
# case) -- existing chord-anchor behavior must be completely
# preserved, explicitly NOT changed by BO-174.
# ---------------------------------------------------------

def test_genuine_matching_preceding_chord_anchor_unaffected():

    positions = _positions_by_measure_beat(_generate())

    # BO-176 -- updated from the stale (2, 0). Direct
    # investigation confirms the note at measure 3 beat 1.5 is
    # the SECOND note of a real slur (confirmed via the raw
    # source XML's own <Spanner type="Slur"><prev> element),
    # connected to the note at beat 1 (string 3). A slur
    # physically requires both connected notes to share a
    # string (hammer-on/pull-off/slide), and this constraint was
    # explicitly specified (BO-176) to outweigh even an exact
    # chord-shape match -- so this note now correctly follows
    # the slur-start note onto string 3 (fret 5) instead of the
    # Bm chord's own exact-inclusion match at string 2 (fret 0).
    # Beat 2.0 (a separate, unslurred note) is genuinely
    # untouched by BO-176 and remains the real, confirmed
    # exact-anchor case BO-174 itself preserved.
    assert positions[(3, 1.5)] == (3, 5)

    assert positions[(3, 2.0)] == (2, 0)



# ---------------------------------------------------------
# 3 -- production-path regression using the supplied score/
# scenario: the nine primary BO-174 placements improve as
# expected.
# ---------------------------------------------------------

def test_production_path_nine_primary_examples_improve():

    positions = _positions_by_measure_beat(_generate())

    # The 9 primary BO-174 examples (ticket's own 1-indexed
    # measure/beat/string notation) -- all now match the
    # ticket's own "preferred" position exactly, except (2, 4.0)
    # which lands on (2, 5) instead of the ticket's own suggested
    # (2, 3) -- both are genuine, defensible same-string-
    # continuity results (see the BO-174 implementation report),
    # so that one entry is checked only for "no longer the bad
    # (1, 3) position" rather than an exact match.
    assert positions[(1, 3.5)] == (2, 5)

    assert positions[(1, 4.0)] == (2, 7)

    assert positions[(1, 4.5)] == (2, 5)

    assert positions[(2, 3.0)] == (2, 3)

    assert positions[(2, 4.0)] != (1, 3)

    assert positions[(4, 3.0)] == (2, 5)

    assert positions[(5, 3.5)] == (2, 5)

    assert positions[(6, 2.0)] == (2, 5)

    assert positions[(6, 4.0)] == (2, 5)

    # BO-176 -- updated from the stale (2, 0). See test_
    # genuine_matching_preceding_chord_anchor_unaffected's own
    # BO-176 comment for the full explanation: this note is the
    # second note of a real slur, and the same-string slur
    # constraint (explicitly specified to outweigh even an exact
    # chord-shape match) now correctly moves it to string 3
    # (matching the slur-start note), fret 5. Beat 2.0 is a
    # separate, unslurred note and remains the real, unchanged
    # exact-anchor case.
    assert positions[(3, 1.5)] == (3, 5)

    assert positions[(3, 2.0)] == (2, 0)
