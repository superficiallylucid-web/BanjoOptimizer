"""
tests/test_bo143_additional_score_elements.py

Focused tests for BO-143: preserving/creating ten additional
score elements in the generated .mscz -- Subtitle, Composer,
Lyricist (metadata) and Fine, D.C. al Fine, D.S. al Fine, D.C.
al Coda, Coda, Segno, Fermata above (musical/navigation) --
whenever the corresponding element is present in the input
score, using genuine MuseScore-specific elements (Marker/Jump/
Fermata/Text) rather than plain text standing in for them.

Uses the real, supplied BO-143 reference score throughout,
since that's the authoritative example for how these elements
are actually represented in MuseScore's own XML.
"""

import sys

sys.path.insert(0, '.')

sys.path.insert(0, 'tests')

import os

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


REFERENCE_PATH = 'scores/BO-143 reference.mscz'


def _generate_reference_output():
    """
    Runs the real, complete pipeline against the real BO-143
    reference score and returns the parsed output XML root.
    Cleans up the generated file itself before returning.
    """

    p = MuseScoreFile(REFERENCE_PATH)

    p.open()

    p.read_title()

    p.read_composer()

    p.read_subtitle()

    p.read_lyricist()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, _, _, _ = generate_tab_from_template(
        p, tuning, staff_used,
        'templates/TAB_linked_Treble_Example.mscz', 'output',
        service, filename='bo143_test_output.mscz'
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    return ET.fromstring(content), p


def _vbox_texts(root):

    for el in root.iter():

        if el.tag.split('}')[-1] == 'VBox':

            result = []

            for text_el in el.findall('{*}Text'):

                style_el = text_el.find('{*}style')

                content_el = text_el.find('{*}text')

                style = (
                    style_el.text if style_el is not None
                    else None
                )

                text = (
                    ''.join(content_el.itertext())
                    if content_el is not None else None
                )

                result.append((style, text))

            return result

    return []


def _measure_children(root, tag):

    result = []

    for measure in root.iter():

        if measure.tag.split('}')[-1] == 'Measure':

            for child in measure:

                if child.tag.split('}')[-1] == tag:

                    result.append(child)

    return result


# ---------------------------------------------------------
# Parsing -- real reference score
# ---------------------------------------------------------

def test_parses_subtitle_composer_lyricist_from_real_score():

    p = MuseScoreFile(REFERENCE_PATH)

    p.open()

    p.read_composer()

    p.read_subtitle()

    p.read_lyricist()

    assert p.score.composer == 'This is the composwer'

    assert p.score.subtitle == 'This is the Subtitle'

    assert p.score.lyricist == 'This is the lyricist'


# ---------------------------------------------------------
# End-to-end -- all three metadata elements present, correct
# text, correct relative order, no interference with each other
# ---------------------------------------------------------

def test_metadata_elements_present_in_generated_output():

    root, _ = _generate_reference_output()

    texts = _vbox_texts(root)

    # A plain {style: text} dict would silently collapse the
    # two, real, separate "subtitle"-styled entries (the real
    # source subtitle, and the pre-existing tuning-info line) --
    # use the first subtitle-styled entry specifically instead,
    # which is the real source subtitle (inserted right after
    # title, before the tuning-info line that's appended later).
    first_by_style = {}

    for style, text in texts:

        if style not in first_by_style:

            first_by_style[style] = text

    assert first_by_style.get('subtitle') == (
        'This is the Subtitle'
    ), (
        f"Expected the real subtitle text in the generated "
        f"VBox, got {first_by_style.get('subtitle')!r}."
    )

    assert first_by_style.get('composer') == (
        'This is the composwer'
    ), (
        f"Expected the real composer text (metaTag-sourced, "
        f"matching read_composer()'s own established pattern) "
        f"in the generated VBox, got "
        f"{first_by_style.get('composer')!r}."
    )

    assert first_by_style.get('poet') == (
        'This is the lyricist'
    ), (
        f"Expected the real lyricist text (MuseScore's own "
        f"'poet' style) in the generated VBox, got "
        f"{first_by_style.get('poet')!r}."
    )

    # Metadata elements don't interfere with each other: subtitle
    # comes before composer (matching the real, confirmed
    # MuseScore ordering), and the pre-existing "subtitle"-styled
    # tuning-info line (added separately by _add_tuning_text())
    # still appears too, without being overwritten or removed.
    styles_in_order = [style for style, _ in texts]

    assert styles_in_order.index(
        'subtitle'
    ) < styles_in_order.index('composer'), (
        "Expected subtitle to appear before composer, matching "
        "the real, confirmed MuseScore ordering."
    )

    assert styles_in_order.count('subtitle') == 2, (
        "Expected TWO 'subtitle'-styled <Text> elements: the "
        "real source subtitle, and the pre-existing tuning-info "
        "line -- confirming they coexist rather than one "
        "overwriting the other."
    )


def test_metadata_metatags_present_in_generated_output():

    root, _ = _generate_reference_output()

    values = {}

    for el in root.iter():

        if el.tag.split('}')[-1] == 'metaTag':

            values[el.get('name')] = el.text

    assert values.get('subtitle') == 'This is the Subtitle'

    assert values.get('composer') == 'This is the composwer'

    assert values.get('lyricist') == 'This is the lyricist'


# ---------------------------------------------------------
# Musical/navigation elements -- correct MuseScore-specific
# element type, not plain text; correct text/label/subtype
# ---------------------------------------------------------

def test_fine_marker_present_as_genuine_marker_element():

    root, _ = _generate_reference_output()

    markers = _measure_children(root, 'Marker')

    fine_markers = [
        m for m in markers
        if m.find('{*}label') is not None
        and m.find('{*}label').text == 'fine'
    ]

    assert len(fine_markers) == 1, (
        f"Expected exactly one genuine <Marker label='fine'>, "
        f"found {len(fine_markers)}."
    )

    text_el = fine_markers[0].find('{*}text')

    assert text_el is not None and text_el.text == 'Fine'


def test_coda_marker_present_as_genuine_marker_element():

    root, _ = _generate_reference_output()

    markers = _measure_children(root, 'Marker')

    coda_markers = [
        m for m in markers
        if m.find('{*}label') is not None
        and m.find('{*}label').text == 'codab'
    ]

    assert len(coda_markers) == 1, (
        f"Expected exactly one genuine <Marker label='codab'>, "
        f"found {len(coda_markers)}."
    )

    marker_type_el = coda_markers[0].find('{*}markerType')

    assert (
        marker_type_el is not None
        and marker_type_el.text == 'codab'
    ), "Expected the real MuseScore markerType, not plain text."


def test_segno_marker_present_as_genuine_marker_element():

    root, _ = _generate_reference_output()

    markers = _measure_children(root, 'Marker')

    segno_markers = [
        m for m in markers
        if m.find('{*}label') is not None
        and m.find('{*}label').text == 'segno'
    ]

    assert len(segno_markers) == 1, (
        f"Expected exactly one genuine <Marker label='segno'>, "
        f"found {len(segno_markers)}."
    )


def test_dc_al_fine_present_as_genuine_jump_element():

    root, _ = _generate_reference_output()

    jumps = _measure_children(root, 'Jump')

    matches = [
        j for j in jumps
        if j.find('{*}text') is not None
        and j.find('{*}text').text == 'D.C. al Fine'
    ]

    assert len(matches) == 1

    jump_to_el = matches[0].find('{*}jumpTo')

    play_until_el = matches[0].find('{*}playUntil')

    assert jump_to_el is not None and jump_to_el.text == 'start'

    assert (
        play_until_el is not None
        and play_until_el.text == 'fine'
    )


def test_ds_al_fine_present_as_genuine_jump_element():

    root, _ = _generate_reference_output()

    jumps = _measure_children(root, 'Jump')

    matches = [
        j for j in jumps
        if j.find('{*}text') is not None
        and j.find('{*}text').text == 'D.S. al Fine'
    ]

    assert len(matches) == 1

    jump_to_el = matches[0].find('{*}jumpTo')

    assert jump_to_el is not None and jump_to_el.text == 'segno'


def test_dc_al_coda_present_as_genuine_jump_element():

    root, _ = _generate_reference_output()

    jumps = _measure_children(root, 'Jump')

    matches = [
        j for j in jumps
        if j.find('{*}text') is not None
        and j.find('{*}text').text == 'D.C. al Coda'
    ]

    assert len(matches) == 1

    play_until_el = matches[0].find('{*}playUntil')

    continue_at_el = matches[0].find('{*}continueAt')

    assert (
        play_until_el is not None
        and play_until_el.text == 'coda'
    )

    assert (
        continue_at_el is not None
        and continue_at_el.text == 'codab'
    )


def test_fermata_above_present_as_genuine_fermata_element():

    root, _ = _generate_reference_output()

    fermatas = []

    for measure in root.iter():

        if measure.tag.split('}')[-1] == 'Measure':

            for voice in measure.findall('{*}voice'):

                for child in voice:

                    if child.tag.split('}')[-1] == 'Fermata':

                        fermatas.append(child)

    assert len(fermatas) == 1, (
        f"Expected exactly one genuine <Fermata>, found "
        f"{len(fermatas)}."
    )

    subtype_el = fermatas[0].find('{*}subtype')

    assert (
        subtype_el is not None
        and subtype_el.text == 'fermataAbove'
    ), "Expected the real MuseScore fermataAbove subtype."


def test_all_navigation_elements_have_regenerated_eids():

    # Marker/Jump/Fermata elements DO have their own real eid
    # (unlike startRepeat/endRepeat) -- confirmed directly
    # against the input; each must be regenerated on output, not
    # copied verbatim (which would create a duplicate/colliding
    # eid with the source score).
    root, p = _generate_reference_output()

    with zipfile.ZipFile(REFERENCE_PATH) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        input_root = ET.fromstring(z.read(mscx_name))

    input_eids = set()

    for tag in ('Marker', 'Jump', 'Fermata'):

        for el in input_root.iter():

            if el.tag.split('}')[-1] == tag:

                eid_el = el.find('{*}eid')

                if eid_el is not None:

                    input_eids.add(eid_el.text)

    output_eids = set()

    for tag in ('Marker', 'Jump', 'Fermata'):

        for el in root.iter():

            if el.tag.split('}')[-1] == tag:

                eid_el = el.find('{*}eid')

                if eid_el is not None:

                    output_eids.add(eid_el.text)

    assert output_eids.isdisjoint(input_eids), (
        "Expected every Marker/Jump/Fermata eid to be "
        "regenerated on output, not copied verbatim from input."
    )


# ---------------------------------------------------------
# Absent elements are never invented
# ---------------------------------------------------------

def test_absent_lyricist_not_invented():

    # A score with no lyricist metaTag value at all shouldn't
    # get an invented <Text style="poet"> in its own output.
    p = MuseScoreFile(
        'scores/White Christmas (G (gCGBD)).mscz'
    )

    p.open()

    p.read_title()

    p.read_composer()

    p.read_subtitle()

    p.read_lyricist()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    assert p.score.lyricist == '', (
        f"Expected no real lyricist value on this fixture, got "
        f"{p.score.lyricist!r} -- if this fails, pick a "
        f"different real fixture confirmed to have none."
    )

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, _, _, _ = generate_tab_from_template(
        p, tuning, staff_used,
        'templates/TAB_linked_Treble_Example.mscz', 'output',
        service, filename='bo143_test_no_lyricist.mscz'
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    texts = _vbox_texts(root)

    styles = [style for style, _ in texts]

    assert 'poet' not in styles, (
        "Expected no invented lyricist <Text> when the source "
        "score has no real lyricist value at all."
    )


def test_absent_navigation_elements_not_invented():

    # This same fixture also has no Marker/Jump/Fermata at all
    # -- confirming none is invented in their absence either.
    p = MuseScoreFile(
        'scores/White Christmas (G (gCGBD)).mscz'
    )

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, _, _, _ = generate_tab_from_template(
        p, tuning, staff_used,
        'templates/TAB_linked_Treble_Example.mscz', 'output',
        service, filename='bo143_test_no_navigation.mscz'
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    for tag in ('Marker', 'Jump'):

        assert len(_measure_children(root, tag)) == 0, (
            f"Expected no invented <{tag}> elements on a score "
            f"with none in its own input."
        )
