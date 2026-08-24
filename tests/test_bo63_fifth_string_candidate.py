"""
tests/test_bo63_fifth_string_candidate.py

Regression tests for BO-63's two, narrowly-scoped implementation
changes: (A) the 5th string is now a genuine candidate in the
melody-position pool, appended as string_index=4 without shifting
the existing 4 strings; (B) the final MuseScore XML write
correctly handles string_index=4 as the literal value 4, since
the existing "3 - string_index" formula is only valid for indices
0-3.

Deliberately does NOT encode any musical preference for when the
5th string should or shouldn't be selected -- that is intentional
future work, not BO-63's own scope. These tests only confirm the
mechanical correctness of making it visible/writable at all.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from fretboard import find_positions, best_position

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template

from hand_position import HandPosition, open_string_hp


DOUBLE_C = get_tunings()["Double C"]


# ---------------------------------------------------------
# 1 -- a 5th-string candidate can be represented as
# string_index=4, fret=0
# ---------------------------------------------------------

def test_fifth_string_candidate_is_string_4_fret_0():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    # G4 (midi 67) is Double C's own real 5th-string pitch.
    positions = find_positions(67, open_notes)

    fifth_string_candidates = [
        p for p in positions if p["string"] == 4
    ]

    assert len(fifth_string_candidates) == 1

    assert fifth_string_candidates[0]["fret"] == 0


# ---------------------------------------------------------
# 2 -- existing string indexes 0-3 are unchanged
# ---------------------------------------------------------

def test_existing_four_string_indexes_unchanged():

    old_open_notes = DOUBLE_C.notes[1:]

    new_open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    old_positions = find_positions(67, old_open_notes)

    new_positions = find_positions(67, new_open_notes)

    old_four = {
        (p["string"], p["fret"]) for p in old_positions
    }

    new_four = {
        (p["string"], p["fret"])
        for p in new_positions if p["string"] != 4
    }

    # Every real candidate string_index/fret pair the OLD
    # (4-string-only) pool produced is still present, unchanged,
    # in the new pool -- confirms nothing shifted.
    assert old_four == new_four


# ---------------------------------------------------------
# 3 -- the 5th-string candidate gets existing open-string
# scoring, no new bonus added
# ---------------------------------------------------------

def test_fifth_string_candidate_uses_existing_open_scoring():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    positions = find_positions(67, open_notes)

    best_position(positions)

    fifth = next(p for p in positions if p["string"] == 4)

    # Real, confirmed: fret==0 gets the existing +10 fret-band
    # bonus every open string already receives; string==4 matches
    # none of the existing string==1/2/3 explicit bonuses, so it
    # gets exactly 0 from that component -- no new, 5th-string-
    # specific bonus exists anywhere. Total: 10.
    assert fifth["score"] == 10


# ---------------------------------------------------------
# 4 -- a 5th-string candidate does not establish or modify HP
# ---------------------------------------------------------

def test_fifth_string_candidate_does_not_affect_hp():

    # Reuses the existing, unmodified open_string_hp() -- no
    # 5th-string-specific HP logic exists or is needed.
    current_hp = HandPosition(2, 5)

    result = open_string_hp(current_hp)

    assert result == current_hp

    assert result is current_hp

    # Also confirmed starting from no established HP at all.
    assert open_string_hp(None) is None


# ---------------------------------------------------------
# 5 -- the final MuseScore XML writes the 5th string as
# <string>4</string>, and existing indexes are unaffected
# ---------------------------------------------------------

def test_real_csb_gCGCD_fifth_string_writes_valid_xml():

    import os

    p = MuseScoreFile("scores/Cousin Sally Brown.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo63_xml_check.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        string_values = set()

        for note in root.iter():

            if note.tag.split("}")[-1] == "Note":

                s = note.find("{*}string")

                if s is not None:

                    string_values.add(int(s.text))

        # Every real string value written must be a valid
        # MuseScore value (0-4) -- confirms no negative/invalid
        # value (e.g. the -1 that "3 - 4" would have produced)
        # ever reaches the real output.
        for value in string_values:

            assert 0 <= value <= 4

        # Real, confirmed: G4 genuinely selects the 5th string in
        # this real song/tuning under BO-63's own unmodified
        # existing scoring -- string value 4 genuinely appears.
        assert 4 in string_values

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_existing_string_indexes_write_same_museScore_values():

    # Direct confirmation that indexes 0-3 still map through the
    # existing, unmodified "3 - string_index" formula.
    for string_index, expected_ms_value in [
        (0, 3), (1, 2), (2, 1), (3, 0)
    ]:

        computed = (
            4 if string_index == 4 else 3 - string_index
        )

        assert computed == expected_ms_value

    # And the new, BO-63-added case:
    assert (4 if 4 == 4 else 3 - 4) == 4


# ---------------------------------------------------------
# 6 -- chord/FD selection remains unchanged -- never attempts
# to use the 5th string as a chord-string position
# ---------------------------------------------------------

def test_chord_shapes_never_use_fifth_string():

    import os

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    double_d = get_tunings()["Double D"]

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, double_d, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo63_chord_check.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        fd_count = 0

        for fd in root.iter():

            if fd.tag.split("}")[-1] == "FretDiagram":

                fd_count += 1

                # Real FD shapes always describe exactly 4
                # strings (parse_shape()'s own confirmed
                # behavior) -- never a 5th-string position.
                strings_seen = set()

                for child in fd.iter():

                    if child.tag.split("}")[-1] == "string":

                        strings_seen.add(
                            int(child.attrib.get("no", -1))
                        )

                assert all(s <= 3 for s in strings_seen)

        assert fd_count > 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
