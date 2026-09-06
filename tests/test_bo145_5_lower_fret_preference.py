"""
tests/test_bo145_5_lower_fret_preference.py

Focused tests for BO-145.5:

1. best_position()'s own middle-string "favor middle melody
   strings" bonus (BO-98/BO-99) is removed entirely -- confirmed
   real (BO-145.4's own investigation): it was a deliberate
   "favor the middle two strings" heuristic, not the intended
   general melody-position behavior at all.

2. A new, explicit "prefer the lower fret" secondary tie-break
   is added to _choose_melody_position()'s own _sort_key() --
   positioned as the LAST tie-break, after every other
   meaningful component (chord-anchor distance, phrase
   coverage, HP membership/offset, same-string continuity), so
   none of those stronger, established playing considerations
   are overridden by it.

Uses the real, confirmed Alizarin C5 case throughout as the
concrete acceptance test.
"""

import sys

sys.path.insert(0, '.')

sys.path.insert(0, 'tests')

import os

from fretboard import best_position, find_positions

from score_generator import (
    _choose_melody_position, generate_tab_from_template
)

from tunings import get_tunings

from hand_position import HandPosition

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary


OPEN_G = get_tunings()['Open G']

C_STANDARD = get_tunings()['C Standard']


# ---------------------------------------------------------
# 1 -- middle-string bonus is genuinely gone from best_position()
# ---------------------------------------------------------

def test_middle_string_bonus_removed_from_best_position():

    open_notes = C_STANDARD.notes[1:]

    positions = find_positions(67, open_notes)  # G4

    best_position(positions)

    fret12 = next(p for p in positions if p["fret"] == 12)

    fret5 = next(p for p in positions if p["fret"] == 5)

    # No string bonus at all now -- score is purely
    # _fret_band_value(fret), unaffected by which string.
    assert fret5["score"] == 5

    assert fret12["score"] == 2

    # Not reintroducing a middle-string OR a reversed (string 1
    # highest) preference -- confirming score depends only on
    # fret, matching two different candidates on different
    # strings but the same fret.
    positions_at_5 = [
        p for p in find_positions(67, open_notes)
        if p["fret"] == 5
    ]

    best_position(positions_at_5)

    scores_at_fret_5 = {p["score"] for p in positions_at_5}

    assert len(scores_at_fret_5) == 1, (
        "Expected every candidate at the same fret to score "
        "identically regardless of string, confirming no "
        "string-based bonus (middle OR reversed) remains."
    )


# ---------------------------------------------------------
# 2 -- equivalent candidates at frets 10, 13, 17 -> fret 10 wins
# (the exact real Alizarin C5 candidate set)
# ---------------------------------------------------------

def test_lower_fret_wins_among_equivalent_candidates():

    open_notes = OPEN_G.notes[1:]

    result = _choose_melody_position(
        72, open_notes,
        current_hp=HandPosition(4, 7),
        previous_position={"string": 3, "fret": 4, "score": 10},
        preceding_chord_shape_values=[7, 5, 5, 5]
    )

    assert result["fret"] == 10, (
        f"Expected fret 10 to win among equivalent candidates "
        f"(10, 13, 17, 22), got fret {result['fret']}."
    )

    assert result["string"] == 3, "Expected user string 1 (1-10)."


# ---------------------------------------------------------
# 3 -- lower fret wins across different strings, without
# reintroducing the middle-string bonus
# ---------------------------------------------------------

def test_lower_fret_wins_not_middle_string():

    # A candidate on the outer string (user 1, internal 3) at a
    # LOWER fret must beat a candidate on a middle string
    # (user 2/3) at a HIGHER fret -- if the old middle-string
    # bonus were still active, the middle-string candidate could
    # win despite the higher fret.
    open_notes = OPEN_G.notes[1:]

    result = _choose_melody_position(
        72, open_notes,
        current_hp=HandPosition(4, 7),
        previous_position={"string": 3, "fret": 4, "score": 10},
        preceding_chord_shape_values=[7, 5, 5, 5]
    )

    assert result["string"] == 3, (
        "Expected the outer string's own lower-fret candidate "
        "to win, confirming no middle-string bonus remains."
    )


# ---------------------------------------------------------
# 4 -- an established HP/phrase preference still beats the
# lower-fret tie-break when it should (BO-62's own real case)
# ---------------------------------------------------------

def test_established_hp_preference_still_beats_lower_fret():

    open_notes = C_STANDARD.notes[1:]

    # fret 2 is NOT E4's own best-scored candidate by raw
    # comfort/fret alone (fret 4 is lower-banded/closer to open)
    # -- but fret 2 is the real, established HP's own root, and
    # BOTH candidates are inside the same HP, so within_hp_offset
    # must still decide this BEFORE the new lower-fret tie-break
    # ever gets a chance, exactly as it did before BO-145.5.
    result = _choose_melody_position(
        64, open_notes, current_hp=HandPosition(2, 5),
        previous_position={"string": 2, "fret": 2, "score": 0}
    )

    assert result["fret"] == 2

    assert result["string"] == 3


# ---------------------------------------------------------
# 5 -- working_fret_anchor=None does not eliminate the new
# lower-fret preference (it's independent of chord anchoring)
# ---------------------------------------------------------

def test_lower_fret_preference_active_without_working_fret_anchor():

    open_notes = OPEN_G.notes[1:]

    result = _choose_melody_position(
        72, open_notes,
        current_hp=HandPosition(4, 7),
        previous_position={"string": 3, "fret": 4, "score": 10},
        preceding_chord_shape_values=[7, 5, 5, 5],
        working_fret_anchor=None,
        following_working_fret_anchor=None
    )

    assert result["fret"] == 10, (
        "Expected the lower-fret preference to remain active "
        "even with no working_fret_anchor set at all -- "
        "confirming it's independent of chord-anchor distance."
    )


# ---------------------------------------------------------
# 6 -- existing within_hp_offset behavior unchanged (direct
# BO-62 regression re-check)
# ---------------------------------------------------------

def test_within_hp_offset_unchanged():

    open_notes = C_STANDARD.notes[1:]

    result = _choose_melody_position(
        64, open_notes, current_hp=HandPosition(2, 5),
        previous_position={"string": 2, "fret": 2, "score": 0}
    )

    # Unchanged from the pre-BO-145.5 established result.
    assert result["fret"] == 2

    assert result["string"] == 3


# ---------------------------------------------------------
# 7 -- existing BO-123 string_distance behavior unchanged
# ---------------------------------------------------------

def test_bo123_string_distance_gate_unchanged():

    open_notes = C_STANDARD.notes[1:]

    # No working_fret_anchor/following anchor at all, and no
    # melody_phrase_notes -- string_distance's own BO-123 gate
    # should remain active exactly as before, same-string
    # continuity still applying under these conditions.
    result = _choose_melody_position(
        64, open_notes,
        previous_position={"string": 2, "fret": 5, "score": 5}
    )

    assert result["string"] == 2, (
        "Expected BO-123's own same-string continuity behavior "
        "to remain unchanged when no chord anchor or phrase "
        "context is present."
    )


# ---------------------------------------------------------
# 8 -- real Alizarin acceptance test: all four C5 cases -> 1-10
# ---------------------------------------------------------

def test_real_alizarin_all_four_c5_resolve_to_1_10():

    if not os.path.exists('scores/Alizarin.mscz'):

        return

    p = MuseScoreFile('scores/Alizarin.mscz')

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, _, _, _ = generate_tab_from_template(
        p, OPEN_G, staff_used,
        'templates/TAB_linked_Treble_Example.mscz', 'output',
        service, filename='bo145_5_test_alizarin.mscz'
    )

    import zipfile

    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    measures = root.findall('.//{*}Measure')

    target_measures = {26, 28, 30, 31}  # m27, m29, m31, m32 (0-indexed)

    found = {}

    for idx in target_measures:

        m = measures[idx]

        for chord in m.iter():

            if chord.tag.split('}')[-1] != 'Chord':

                continue

            for note in chord.findall('{*}Note'):

                pitch_el = note.find('{*}pitch')

                if (
                    pitch_el is not None
                    and pitch_el.text == '72'
                    and idx not in found
                ):

                    fret_el = note.find('{*}fret')

                    string_el = note.find('{*}string')

                    found[idx] = (
                        fret_el.text, string_el.text
                    )

    assert len(found) == 4, (
        f"Expected all 4 real C5 occurrences, found "
        f"{len(found)}."
    )

    for idx, (fret, xml_string) in found.items():

        # XML string 0 == user string 1 (confirmed, BO-145.4's
        # own audit).
        assert fret == '10' and xml_string == '0', (
            f"Expected m{idx+1}'s own C5 to resolve to 1-10 "
            f"(XML fret=10, string=0), got fret={fret} "
            f"string={xml_string}."
        )
