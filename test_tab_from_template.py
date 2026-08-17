"""
tests/test_tab_from_template.py

Regression tests for BO-23 Option 1: populating a MuseScore-
created TAB template with a real, short passage (The Christmas
Song, cut version -- 3 measures, mixed rhythms including rests,
dotted notes, and eighth-note runs, plus 5 chord symbols
including a Cmaj7).

Output is TAB-ONLY -- the template's own linked treble staff
(Staff-definition and content) is removed entirely before
saving. BO does not attempt or rely on genuine live-linked
editing (three independently-tested approaches at reconstructing
that were unsuccessful -- see BO-23's own investigation notes);
the user adds a linked treble staff manually via MuseScore's own
"Add Linked Staff" feature afterward, only if/when they want one.

Chord symbols and FretDiagrams both go directly on the TAB
staff, reusing _apply_chord_shapes() UNMODIFIED -- the same
melody-aware, position-aware BO-18 through BO-22 chord-shape
selection already used by generate_chord_diagrams_only(), not a
separate or simplified version of it.

This is a genuinely new generation path, separate from
generate_mscz()/generate_chord_diagrams_only() -- it does not
modify either.

Also covers parser.py's small, additive extension: Note.duration
(a field that already existed but was never populated) is now
set from the same _duration_value() call already used for beat
tracking -- confirmed nothing else in the codebase read this
field before, so this is purely additive.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile, DURATIONS

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _extract_staff_events,
    generate_tab_from_template
)


CUT_VERSION_PATH = "The_Christmas_Song_-_Cut_version.mscz"

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _open_cut_version():

    p = MuseScoreFile(CUT_VERSION_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    return p, staff_used


def _get_chord_service():

    return ChordService(ChordLibrary())


def _measure_duration_total(measure_element):

    total = 0.0

    for voice in measure_element.findall("{*}voice"):

        for el in voice:

            tag = el.tag.split("}")[-1]

            if tag not in ("Chord", "Rest"):

                continue

            duration_type_element = el.find("{*}durationType")

            dots_element = el.find("{*}dots")

            base = DURATIONS.get(duration_type_element.text, 0.0)

            dots = (
                int(dots_element.text)
                if dots_element is not None else 0
            )

            value = base

            add = base / 2

            for _ in range(dots):

                value += add

                add /= 2

            total += value

    return total


def _generate(filename):
    """
    Convenience wrapper: opens a fresh copy of the cut version,
    runs generate_tab_from_template(), and returns
    (output_path, applied, skipped, exceptions, root) --
    the parsed output XML included so tests don't each have to
    re-open the zip themselves.
    """

    p, staff_used = _open_cut_version()

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service, filename=filename
        )
    )

    with zipfile.ZipFile(output_path) as archive:

        mscx_name = [
            n for n in archive.namelist() if n.endswith(".mscx")
        ][0]

        xml_bytes = archive.read(mscx_name)

    root = ET.fromstring(xml_bytes)

    return output_path, applied, skipped, exceptions, root


# ---------------------------------------------------------
# 1 -- parser.py's Note.duration extension
# ---------------------------------------------------------

def test_note_duration_is_populated():

    p, staff_used = _open_cut_version()

    notes_by_position = {
        (n.measure, n.beat): n.duration for n in p.score.notes
    }

    # Confirmed real values from the actual source file.
    assert notes_by_position[(1, 2.5)] == 1.5  # dotted quarter

    assert notes_by_position[(2, 1.0)] == 0.5  # eighth

    assert notes_by_position[(3, 0.0)] == 1.0  # quarter


# ---------------------------------------------------------
# 2 -- event extraction: notes, rests, and harmonies all
# correctly captured with their real source rhythm
# ---------------------------------------------------------

def test_extract_staff_events_captures_rests_and_harmonies():

    p, staff_used = _open_cut_version()

    measures = _extract_staff_events(p, staff_used)

    assert len(measures) == 3

    # Measure 1 starts with two rests before the first note.
    assert measures[0][0]["type"] == "rest"

    assert measures[0][0]["duration_type"] == "half"

    assert measures[0][1]["type"] == "rest"

    assert measures[0][1]["duration_type"] == "eighth"

    assert measures[0][2]["type"] == "note"

    assert measures[0][2]["pitch"] == 60

    assert measures[0][2]["dots"] == 1

    # 5 harmonies total across all 3 measures, matching the
    # real source exactly.
    harmony_events = [
        e for m in measures for e in m if e["type"] == "harmony"
    ]

    assert len(harmony_events) == 5


# ---------------------------------------------------------
# 3 -- full pipeline: valid file, correct structure
# ---------------------------------------------------------

def test_full_generation_produces_valid_file():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_valid.mscz"
    )

    try:

        assert root.tag.split("}")[-1] == "museScore"

        assert applied == 5

        assert skipped == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- output is TAB-ONLY: exactly one content staff, one
# staff-definition, no dangling clef reference to a removed
# staff
# ---------------------------------------------------------

def test_output_is_tab_only():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_tab_only.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(staves) == 1

        assert staves[0].attrib.get("id") == "1"

        part_el = root.find(".//{*}Part")

        staff_defs = part_el.findall("{*}Staff")

        assert len(staff_defs) == 1

        instrument_el = root.find(".//{*}Instrument")

        clefs = instrument_el.findall("{*}clef")

        for clef in clefs:

            assert clef.attrib.get("staff") != "2", (
                "dangling clef reference to the removed treble "
                "staff"
            )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- every measure sums to a full measure -- the exact
# failure mode ("Incomplete measure") that plagued every
# earlier from-scratch TAB-generation attempt
# ---------------------------------------------------------

def test_every_measure_duration_correct():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_durations.mscz"
    )

    try:

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        measures = staff.findall("{*}Measure")

        assert len(measures) == 3

        for measure in measures:

            total = _measure_duration_total(measure)

            assert total == 4.0, (
                f"measure duration is {total}, expected 4.0"
            )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- every note's fret/string decodes to the exact source
# pitch, using the confirmed-reversed MuseScore string
# numbering
# ---------------------------------------------------------

def test_fret_string_values_decode_to_correct_pitches():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_pitches.mscz"
    )

    try:

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        open_notes = A_MODAL_SAWMILL.notes[1:]

        checked = 0

        for note in staff.findall(".//{*}Note"):

            pitch = int(note.find("{*}pitch").text)

            fret = int(note.find("{*}fret").text)

            ms_string = int(note.find("{*}string").text)

            fretboard_string_index = 3 - ms_string

            computed = open_notes[fretboard_string_index] + fret

            assert computed == pitch, (
                f"pitch={pitch} fret={fret} string={ms_string} "
                f"decodes to {computed}, not the source pitch"
            )

            checked += 1

        assert checked == 13  # the real source's own note count

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 7 -- chord symbols present on the TAB staff, correct count
# and positions
# ---------------------------------------------------------

def test_chord_symbols_present_on_tab_staff():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_harmonies.mscz"
    )

    try:

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        harmonies = staff.findall(".//{*}Harmony")

        assert len(harmonies) == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 8 -- FretDiagrams are present, one per chord symbol, none
# marked as exceptions for this real passage
# ---------------------------------------------------------

def test_fretdiagrams_present_and_none_are_exceptions():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_fretdiagrams.mscz"
    )

    try:

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(fret_diagrams) == 5

        assert exceptions == []

        for fd in fret_diagrams:

            assert fd.find("{*}color") is None

        # Confirmed real, correct value from BO-22-FOLLOWUP:
        # Cmaj7 in aEADE selects a complete C-E-G-B voicing.
        harmonies = staff.findall(".//{*}Harmony")

        cmaj7_index = None

        for i, h in enumerate(harmonies):

            name_el = h.find(".//{*}name")

            if name_el is not None and name_el.text == "maj7":

                cmaj7_index = i

                break

        assert cmaj7_index is not None

        cmaj7_fret_diagram = fret_diagrams[cmaj7_index]

        fret_offset_element = cmaj7_fret_diagram.find(
            "{*}fretOffset"
        )

        assert fret_offset_element is not None

        assert fret_offset_element.text == "7"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 9 -- rests are correctly reproduced, not just notes
# ---------------------------------------------------------

def test_rests_correctly_reproduced():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_tab_template_rests.mscz"
    )

    try:

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        first_measure = staff.find("{*}Measure")

        rests = first_measure.findall(".//{*}Rest")

        assert len(rests) == 2

        assert rests[0].find("{*}durationType").text == "half"

        assert rests[1].find("{*}durationType").text == "eighth"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 10 -- template formatting/style/eid-uniqueness preserved
# ---------------------------------------------------------

def test_template_formatting_and_string_data_preserved():

    p, staff_used = _open_cut_version()

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_tab_template_formatting.mscz"
        )
    )

    try:

        with zipfile.ZipFile(TEMPLATE_PATH) as template_zip:

            template_members = {
                n: template_zip.read(n)
                for n in template_zip.namelist()
                if not n.endswith(".mscx")
            }

        with zipfile.ZipFile(output_path) as output_zip:

            output_members = {
                n: output_zip.read(n)
                for n in output_zip.namelist()
                if not n.endswith(".mscx")
            }

            mscx_name = [
                n for n in output_zip.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = output_zip.read(mscx_name)

        assert template_members == output_members

        root = ET.fromstring(xml_bytes)

        string_data = root.find(".//{*}StringData")

        strings = [
            int(el.text)
            for el in string_data.findall("{*}string")
        ]

        assert strings == A_MODAL_SAWMILL.notes

        eids = [
            el.text for el in root.iter()
            if el.tag.split("}")[-1] == "eid"
        ]

        assert len(eids) == len(set(eids)), (
            "duplicate eids found -- the exact class of bug "
            "that caused repeated 'Incomplete measure' errors "
            "in every earlier from-scratch TAB attempt"
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 11 -- source score's own already-parsed state is untouched
# ---------------------------------------------------------

def test_source_score_state_unmodified():

    p, staff_used = _open_cut_version()

    before_note_count = len(p.score.notes)

    before_harmony_symbols = [h.symbol for h in p.harmonies]

    assert before_harmony_symbols  # sanity: baseline isn't empty

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_tab_template_source_unmodified.mscz"
        )
    )

    try:

        assert len(p.score.notes) == before_note_count

        assert [
            h.symbol for h in p.harmonies
        ] == before_harmony_symbols

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 12 -- the full Christmas Song: a much larger real stress
# test (34 measures, 197 notes, 56 chords, including 4
# measures with real tuplets -- eighth and quarter note
# triplets)
# ---------------------------------------------------------

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


def _tuplet_aware_measure_duration(measure_element):

    total = 0.0

    tuplet_scale = 1.0

    for voice in measure_element.findall("{*}voice"):

        for el in voice:

            tag = el.tag.split("}")[-1]

            if tag == "Tuplet":

                normal_notes_element = el.find(
                    "{*}normalNotes"
                )

                actual_notes_element = el.find(
                    "{*}actualNotes"
                )

                if (
                    normal_notes_element is not None
                    and actual_notes_element is not None
                ):

                    tuplet_scale = (
                        int(normal_notes_element.text)
                        / int(actual_notes_element.text)
                    )

            elif tag == "endTuplet":

                tuplet_scale = 1.0

            elif tag in ("Chord", "Rest"):

                duration_type_element = el.find(
                    "{*}durationType"
                )

                dots_element = el.find("{*}dots")

                base = DURATIONS.get(
                    duration_type_element.text, 0.0
                )

                dots = (
                    int(dots_element.text)
                    if dots_element is not None else 0
                )

                value = base

                add = base / 2

                for _ in range(dots):

                    value += add

                    add /= 2

                total += value * tuplet_scale

    return total


def test_full_song_every_measure_duration_correct():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_tab_template_full_song.mscz"
        )
    )

    try:

        assert applied == 56

        assert skipped == 0

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        measures = staff.findall("{*}Measure")

        assert len(measures) == 34

        bad_measures = []

        for mi, measure in enumerate(measures):

            total = _tuplet_aware_measure_duration(measure)

            if abs(total - 4.0) > 1e-9:

                bad_measures.append((mi + 1, total))

        assert bad_measures == [], (
            f"measures with incorrect total duration: "
            f"{bad_measures}"
        )

        open_notes = A_MODAL_SAWMILL.notes[1:]

        checked = 0

        for note in staff.findall(".//{*}Note"):

            pitch = int(note.find("{*}pitch").text)

            fret = int(note.find("{*}fret").text)

            ms_string = int(note.find("{*}string").text)

            fretboard_string_index = 3 - ms_string

            computed = open_notes[fretboard_string_index] + fret

            assert computed == pitch

            checked += 1

        assert checked == 197

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 13 -- tuplet markers are correctly re-emitted: a Tuplet
# element precedes the first note inside it, endTuplet
# follows the last one, and the ratio matches the source
# ---------------------------------------------------------

def test_tuplet_markers_correctly_emitted():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_tab_template_tuplet_markers.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        measures = staff.findall("{*}Measure")

        measure_6_voice = measures[5].find("{*}voice")

        tags_in_order = [
            el.tag.split("}")[-1] for el in measure_6_voice
        ]

        tuplet_index = tags_in_order.index("Tuplet")

        end_tuplet_index = tags_in_order.index("endTuplet")

        assert end_tuplet_index - tuplet_index == 4, (
            "expected exactly 3 Chord elements (the triplet's "
            "own 3 notes) between Tuplet and endTuplet"
        )

        assert (
            tags_in_order[tuplet_index + 1:end_tuplet_index]
            == ["Chord", "Chord", "Chord"]
        )

        tuplet_element = list(measure_6_voice)[tuplet_index]

        assert tuplet_element.find(
            "{*}normalNotes"
        ).text == "2"

        assert tuplet_element.find(
            "{*}actualNotes"
        ).text == "3"

        measure_24_voice = measures[23].find("{*}voice")

        tuplet_count = sum(
            1 for el in measure_24_voice
            if el.tag.split("}")[-1] == "Tuplet"
        )

        end_tuplet_count = sum(
            1 for el in measure_24_voice
            if el.tag.split("}")[-1] == "endTuplet"
        )

        assert tuplet_count == 2

        assert end_tuplet_count == 2

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 14 -- the beat-accumulator itself is tuplet-aware: the
# event immediately AFTER a tuplet must have the correct,
# non-drifted beat position (this is what melody-onset
# matching actually depends on, separately from whether the
# Tuplet/endTuplet markers are correctly re-emitted in the
# output XML -- both matter, but they're separate code paths)
# ---------------------------------------------------------

def test_beat_position_correct_immediately_after_tuplet():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    measures = _extract_staff_events(p, staff_used)

    # Measure 6 (confirmed real): quarter, quarter-worth of
    # eighths, quarter, THEN an eighth-note triplet, THEN a
    # final quarter note that must land at beat 3.0 -- not
    # 3.5, which is what an un-scaled triplet would produce.
    measure_6_events = measures[5]

    note_events = [
        e for e in measure_6_events if e["type"] == "note"
    ]

    last_note = note_events[-1]

    assert last_note["beat"] == 3.0, (
        f"expected the note after the triplet to land at beat "
        f"3.0, got {last_note['beat']} -- the beat accumulator "
        f"is not correctly scaling tuplet durations"
    )


def test_read_staff_notes_and_read_harmonies_stay_consistent_across_tuplets():
    """
    read_staff_notes() and read_harmonies() independently
    accumulate beat position using the same mechanism -- if only
    one of them were tuplet-aware, their beat values would drift
    apart after a tuplet, breaking BO-20's exact (measure, beat)
    melody-onset matching for any chord following one. Confirms
    both stay consistent on the real file.
    """

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    # Measure 6's second Harmony (confirmed real: occurs right
    # after the eighth-note triplet) must land at the same beat
    # as measure 6's last melody note.
    measure_6_harmonies = [
        h for h in p.harmonies if h.measure == 6
    ]

    measure_6_notes = [
        n for n in p.score.notes if n.measure == 6
    ]

    last_harmony = measure_6_harmonies[-1]

    last_note = max(measure_6_notes, key=lambda n: n.beat)

    assert last_harmony.beat == last_note.beat == 3.0
