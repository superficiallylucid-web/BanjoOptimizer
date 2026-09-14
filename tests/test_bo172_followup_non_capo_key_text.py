"""
tests/test_bo172_followup_non_capo_key_text.py

Focused tests for the BO-172 follow-up: the non-capo branch of
_add_tuning_text() gains a "Key <root> | " prefix in front of
its existing "Banjo tuning: ..." wording, when a real output
key is available -- but "Unknown" (parser.MuseScoreFile's own
default when key estimation never populated a real key) must be
treated as no usable key, preserving the legacy, unprefixed text
exactly (test_bo26/test_bo53's own existing coverage).
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from score_generator import generate_tab_from_template

from conftest import fixture_path, TEST_OUTPUT_DIR


def _tuning_text_containing(output_path, needle):

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    for element in root.iter():

        if element.tag.split('}')[-1] != 'Text':

            continue

        text_el = element.find('{*}text')

        if (
            text_el is not None and text_el.text
            and needle in text_el.text
        ):

            return text_el.text

    return None


# ---------------------------------------------------------
# 1 -- a real key-estimated non-capo case produces the
# "Key X | Banjo tuning: ..." text
# ---------------------------------------------------------

def test_real_key_estimated_non_capo_case_includes_key_prefix():

    p = MuseScoreFile(str(fixture_path('Aureolin.mscz')))

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()  # populates a real key -- "B minor"

    p.read_harmonies(staff_used)

    tuning = get_tunings()['Double C']  # capo == 0, named tuning

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service,
            filename='bo172fu_real_key_test.mscz'
        )
    )

    tuning_text = _tuning_text_containing(
        output_path, 'Banjo tuning'
    )

    assert tuning_text == 'Key B | Banjo tuning: gCGCD (Double C)'


def test_real_key_estimated_non_capo_case_via_full_pipeline():

    # The actual, real production path (main.py's own call),
    # confirming the exact "Key <root>" convention (just the
    # root note, not the full "B minor" key string) end-to-end,
    # for an explicitly specified non-capo tuning.
    import main

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='G'
    )

    generated = result['scores'][0]['generated_files'][0]

    tuning_text = _tuning_text_containing(
        generated['tab_path'], 'Banjo tuning'
    )

    assert tuning_text == 'Key G | Banjo tuning: gCGCD (gCGCD)'


# ---------------------------------------------------------
# 2 -- score_file.key == "Unknown" preserves the existing
# unprefixed text exactly
# ---------------------------------------------------------

def test_unknown_key_preserves_legacy_unprefixed_text():

    p = MuseScoreFile(str(fixture_path('Aureolin.mscz')))

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    # Deliberately NOT calling p.estimate_key() -- p.key stays at
    # its own real, documented default ("Unknown"), the exact
    # same state test_bo26/test_bo53's own existing setup is
    # already in.
    p.read_harmonies(staff_used)

    assert p.key == 'Unknown'

    tuning = get_tunings()['Double C']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service,
            filename='bo172fu_unknown_key_test.mscz'
        )
    )

    tuning_text = _tuning_text_containing(
        output_path, 'Banjo tuning'
    )

    assert tuning_text == 'Banjo tuning: gCGCD (Double C)'

    assert 'Key' not in tuning_text
