"""
tests/test_bo137_3_tie_continuation_inheritance.py

Focused tests for BO-137.3: a tie continuation inherits the
tie-start's already-resolved TAB result (pitch, string, fret)
rather than independently running melody-position selection.

Uses real Gamboge data wherever a real example exists (confirmed
directly against the actual score); constructs controlled XML
scenarios only for the two cases Gamboge doesn't naturally
contain (explicit octave substitution at a tie start, and a
3+-event tie chain).
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import generate_tab_from_template

from chord_service import ChordService

from chord_library import ChordLibrary

import copy

import os


def _load_gamboge():

    p = MuseScoreFile('scores/Gamboge.mscz')

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p, staff_used


def _generate(p, staff_used, filename):

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service, filename=filename,
            hp_trace_sink=trace
        )
    )

    os.remove(output_path)

    return trace


def _notes_at(trace, measure, beat=None):

    note_events = [
        e for e in trace
        if e.event_type in ('fretted_note', 'open_note')
    ]

    return [
        e for e in note_events
        if e.measure == measure
        and (beat is None or abs(e.beat - beat) < 0.01)
    ]


# ---------------------------------------------------------
# 1 -- single-note tie crossing a measure boundary
# (also satisfies 3 -- no chord symbol at the destination,
# confirmed directly: no harmony exists at m7 or m8 at all)
# ---------------------------------------------------------

def test_single_note_tie_crosses_measure_boundary():

    p, staff_used = _load_gamboge()

    trace = _generate(
        p, staff_used, 'bo137_3_test_single_note.mscz'
    )

    start = _notes_at(trace, 7, 3.0)

    continuation = _notes_at(trace, 8, 0.0)

    assert len(start) == 1 and len(continuation) == 1

    assert start[0].pitch == continuation[0].pitch == 62

    assert start[0].fret == continuation[0].fret

    assert start[0].string == continuation[0].string


# ---------------------------------------------------------
# 2 -- the real Gamboge dyad
# ---------------------------------------------------------

def test_real_gamboge_dyad_continuation_inherits_resolved_result():

    p, staff_used = _load_gamboge()

    trace = _generate(
        p, staff_used, 'bo137_3_test_dyad.mscz'
    )

    # Tie-start's own real, resolved F#4->F#3 result (confirmed
    # directly, BO-137.2's own investigation): pitch 54,
    # string0, fret2.
    continuation = _notes_at(trace, 2, 0.0)

    pitches_found = {e.pitch for e in continuation}

    assert 54 in pitches_found, (
        f"Expected the continuation to inherit the resolved "
        f"F#3 (54), not revert to the source F#4 (66) -- found "
        f"pitches {pitches_found}."
    )

    assert 66 not in pitches_found

    f_sharp_note = next(
        e for e in continuation if e.pitch == 54
    )

    assert f_sharp_note.fret == 2 and f_sharp_note.string == 0, (
        f"Expected the inherited position (fret=2, string=0, "
        f"player's '4-2'), got fret={f_sharp_note.fret} "
        f"string={f_sharp_note.string}."
    )


# ---------------------------------------------------------
# 4 -- non-tied control, no chord symbol
# ---------------------------------------------------------

def test_non_tied_note_with_no_chord_uses_independent_path():

    p, staff_used = _load_gamboge()

    trace = _generate(
        p, staff_used, 'bo137_3_test_control.mscz'
    )

    # m7 b0.0, pitch 57 -- confirmed real, non-tied, no chord
    # symbol at this measure at all. Must still resolve via the
    # normal, independent path (this test simply confirms it
    # produces a real, valid result -- not that inheritance was
    # skipped, which isn't directly observable from output alone,
    # but confirms the control case is unaffected/still works).
    result = _notes_at(trace, 7, 0.0)

    assert len(result) == 1

    assert result[0].pitch == 57


# ---------------------------------------------------------
# 5 -- explicit octave substitution at the tie start
# ---------------------------------------------------------

def test_continuation_inherits_explicit_octave_substitution():

    p, staff_used = _load_gamboge()

    # Apply a real, explicit octave substitution (BO-133.4's own
    # existing mechanism) to the tie-start note at m7/b3.0
    # (midi=62) -- shifting it UP one octave to 74 (confirmed
    # directly playable; shifting down to 50 is below this
    # tuning's lowest open string at 52 and is genuinely
    # unplayable, unrelated to BO-137 itself), unrelated to any
    # of BO-137's own automatic behavior.
    p.apply_octave_substitutions(staff_used, [
        {
            "measure": 7, "beat": 3.0,
            "original_midi": 62, "new_midi": 74
        }
    ])

    trace = _generate(
        p, staff_used, 'bo137_3_test_octave_sub.mscz'
    )

    start = _notes_at(trace, 7, 3.0)

    continuation = _notes_at(trace, 8, 0.0)

    assert len(start) == 1 and len(continuation) == 1

    assert start[0].pitch == 74, (
        f"Expected the tie-start's own explicit substitution "
        f"(74) to be reflected, got {start[0].pitch}."
    )

    assert continuation[0].pitch == 74, (
        f"Expected the continuation to inherit the EXPLICITLY "
        f"substituted pitch (74), not revert to the original "
        f"source XML pitch (62), got {continuation[0].pitch}."
    )

    assert continuation[0].fret == start[0].fret

    assert continuation[0].string == start[0].string


# ---------------------------------------------------------
# 6 -- tie chain (3+ events)
# ---------------------------------------------------------

def test_tie_chain_three_events_all_inherit_same_result():

    # Gamboge itself has no real 3+-event tie chain (confirmed
    # directly: every tie is exactly two events long). Extend
    # the real, existing m31->m32 tie (pitch 60) into a third
    # link by appending a NEW measure at the very end of the
    # score -- deliberately after the last real measure (32),
    # so no other, existing measure's own number is disturbed
    # at all. m32's own note becomes ALSO a tie start (adding a
    # <Tie><eid>/<next> alongside its existing <prev>); the new,
    # appended measure's own note is a pure continuation, built
    # by deep-copying m32's own real <Measure> structure and
    # replacing its Spanner with a plain continuation one.
    import xml.etree.ElementTree as ET

    p, staff_used = _load_gamboge()

    current_staff = 0

    m32_measure_element = None

    m32_note = None

    staff_element_ref = None

    for staff_element in p.root.iter():

        if staff_element.tag.split('}')[-1] == 'Staff':

            current_staff += 1

            if current_staff == 2:

                staff_element_ref = staff_element

                measures = staff_element.findall('{*}Measure')

                m32_measure_element = measures[-1]

                for voice in m32_measure_element.findall(
                    '{*}voice'
                ):

                    for element in voice:

                        if element.tag.split('}')[-1] != 'Chord':

                            continue

                        for note in element.findall('{*}Note'):

                            pitch_el = note.find('{*}pitch')

                            if (
                                pitch_el is not None
                                and pitch_el.text == '60'
                            ):

                                m32_note = note

                break

    assert m32_note is not None and staff_element_ref is not None

    # m32's own note also becomes a tie start.
    new_tie_start_spanner = ET.SubElement(m32_note, 'Spanner')

    new_tie_start_spanner.set('type', 'Tie')

    new_tie_el = ET.SubElement(new_tie_start_spanner, 'Tie')

    ET.SubElement(new_tie_el, 'eid').text = 'synthetic_chain_eid'

    next_el = ET.SubElement(new_tie_start_spanner, 'next')

    ET.SubElement(next_el, 'location')

    # New, appended third-link measure -- deep copy of m32's own
    # real structure, with its own Spanner replaced by a plain
    # continuation (prev only).
    new_measure = copy.deepcopy(m32_measure_element)

    for voice in new_measure.findall('{*}voice'):

        for element in voice:

            if element.tag.split('}')[-1] != 'Chord':

                continue

            for note in element.findall('{*}Note'):

                for child in list(note):

                    if (
                        child.tag.split('}')[-1] == 'Spanner'
                        and child.get('type') == 'Tie'
                    ):

                        note.remove(child)

                continuation_spanner = ET.SubElement(
                    note, 'Spanner'
                )

                continuation_spanner.set('type', 'Tie')

                prev_el = ET.SubElement(
                    continuation_spanner, 'prev'
                )

                ET.SubElement(prev_el, 'location')

    staff_element_ref.append(new_measure)

    trace = _generate(
        p, staff_used, 'bo137_3_test_chain.mscz'
    )

    link1 = _notes_at(trace, 31, 3.0)

    link2 = _notes_at(trace, 32, 0.0)

    link3 = _notes_at(trace, 33, 0.0)

    assert len(link1) == 1 and len(link2) == 1 and len(link3) == 1

    assert link1[0].pitch == link2[0].pitch == link3[0].pitch

    assert link1[0].fret == link2[0].fret == link3[0].fret

    assert (
        link1[0].string == link2[0].string == link3[0].string
    )
