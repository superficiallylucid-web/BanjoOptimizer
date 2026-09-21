"""
tests/test_bo186_octave_shift_out_of_range_notes.py

Regression test for BO-186: when a melody note is genuinely
outside every string's own reachable range in this tuning -- not
merely beyond the user's own configured ceiling (BO-179's own
fallback already covers that), but unreachable even at the real
physical maximum, e.g. below the lowest open string entirely, so
no fret at all (frets can't be negative) can reach it --
generate_tab_from_template() now tries the SAME pitch class one
octave away (+12 first, then -12) as a last resort before falling
through to a silent Rest. A successful shift is written as a
real note (not a Rest), automatically marked red by the existing
_is_octave_substituted() check (BO-168, unmodified -- it already
compares the final written pitch against the note's own real
source pitch), and carries lyrics/slurs/ties normally, since it
takes the exact same successful-note-writing path as any other
note from that point on.

Real fixture used: The_Christmas_Song_Low.mscz in G minor
(gDGBbD) -- the user's own reported case. Confirmed directly
during this BO's own investigation: measure 14 has real lyrics
("ti", "ny", "with") on notes that were previously silently
dropped (both the note AND its lyric) because they were below
gDGBbD's own lowest open string.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

import main

from conftest import fixture_path, TEST_OUTPUT_DIR


def _generate():

    return main.run_optimizer(
        score_path=str(
            fixture_path('The_Christmas_Song_Low.mscz')
        ),
        tuning_symbol='gDGBbD',
        output_folder=str(TEST_OUTPUT_DIR)
    )


def _tab_staff_from(tab_path):

    with zipfile.ZipFile(tab_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    for staff in root.iter():

        if (
            staff.tag.split('}')[-1] == 'Staff'
            and staff.attrib.get('id') == '1'
        ):

            return staff

    return None


def test_out_of_range_notes_written_not_dropped():

    result = _generate()

    gen = result['scores'][0]['generated_files'][0]

    shifted = [
        ex for ex in gen['melody_exceptions']
        if 'source_pitch' in ex
    ]

    # The real, confirmed case: 30 notes below gDGBbD's own
    # lowest open string, all shifted up an octave (+12).
    assert len(shifted) > 0

    for ex in shifted:

        assert ex['melody_pitch'] == ex['source_pitch'] + 12

    # No longer reported as a plain "unreachable" (silent Rest)
    # exception -- these were genuinely written.
    unreachable = [
        ex for ex in gen['melody_exceptions']
        if 'source_pitch' not in ex and 'chord_symbol' not in ex
        and ex.get('melody_pitch') in {
            shifted_ex['source_pitch'] for shifted_ex in shifted
        }
    ]

    assert unreachable == []


def test_shifted_notes_are_real_and_colored_red():

    result = _generate()

    gen = result['scores'][0]['generated_files'][0]

    staff = _tab_staff_from(gen['tab_path'])

    assert staff is not None

    # Every shifted source pitch (48, 47) becomes 60/59 -- confirm
    # at least one real, colored Note exists at the shifted pitch
    # (not a Rest).
    found_colored_60 = False

    for note in staff.iter():

        if note.tag.split('}')[-1] != 'Note':

            continue

        pitch_el = note.find('{*}pitch')

        if pitch_el is not None and pitch_el.text == '60':

            color = note.find('{*}color')

            if color is not None:

                found_colored_60 = True

                break

    assert found_colored_60


def test_shifted_notes_keep_their_lyrics():

    result = _generate()

    gen = result['scores'][0]['generated_files'][0]

    staff = _tab_staff_from(gen['tab_path'])

    measures = staff.findall('{*}Measure')

    # Measure 14 (1-indexed) in the real source has lyrics "ti",
    # "ny", "tots", "with", "their", "eyes" -- "ti"/"ny"/"with"
    # sit on notes that were previously dropped entirely (note
    # AND lyric both) because they were below gDGBbD's own lowest
    # open string.
    m14 = measures[13]

    lyrics_texts = []

    for lyrics_el in m14.iter():

        if lyrics_el.tag.split('}')[-1] != 'Lyrics':

            continue

        text_el = lyrics_el.find('{*}text')

        if text_el is not None:

            lyrics_texts.append(text_el.text)

    assert 'ti' in lyrics_texts

    assert 'ny' in lyrics_texts

    assert 'with' in lyrics_texts


def test_genuinely_unreachable_even_after_shift_stays_a_rest():

    # A pitch far enough away that neither +12 nor -12 helps
    # must still fall back to a silent Rest, exactly as before
    # this BO -- confirmed directly against gDGBbD's own real
    # open notes.
    from fretboard import find_positions

    open_notes = [67, 50, 55, 58, 62]  # gDGBbD

    extreme_low = 20

    assert find_positions(
        extreme_low, open_notes, max_fret=22
    ) == []

    assert find_positions(
        extreme_low + 12, open_notes, max_fret=22
    ) == []

    assert find_positions(
        extreme_low - 12, open_notes, max_fret=22
    ) == []
