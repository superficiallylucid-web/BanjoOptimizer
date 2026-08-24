"""
tests/test_bo56_template_robustness_and_notation.py

Regression tests for BO-56: robust template staff detection, and
the new additive independent-notation generation path.

Part 1/2 (robustness): the prior implementation unconditionally
indexed staff_defs[1] to find and remove the template's own
treble staff. Confirmed real, direct failure this caused: a
template with only a TAB staff crashed with a bare IndexError.
Root cause (BO-23/BO-55 investigation): Part-level <Staff>
definitions have no "id" attribute at all -- they're only
distinguishable by StaffType's own group ("tablature" vs
"pitched"), never by position. Fixed by detecting the TAB staff
via that real, confirmed feature instead of a hardcoded index,
with a clear ValueError (not IndexError) when it's genuinely
missing.

Part 3 (notation): a new include_notation=False parameter
(default preserves this function's own exact prior behavior
unchanged). When True, the treble staff is populated with
genuine, independent standard notation (pitch/tpc/rhythm/lyrics/
ties) built from the exact same parsed source events the TAB
staff itself already uses -- NOT a live link (already established
as unreconstructable offline). Confirmed real, directly: every
pitch/tpc value and the full rhythm sequence (Chord/Rest,
durationType, dots) match exactly between the TAB and treble
staves across two different real songs.

No BO-54 musical logic, chord selection, melody selection,
Playing Model, HP logic, or tuning selection is touched anywhere
in this file or in the implementation it tests.
"""

import sys

sys.path.insert(0, '.')

import os

import tempfile

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

OPEN_C = get_tunings()["Open C"]

DOUBLE_D = get_tunings()["Double D"]


def _make_tab_only_template(dst_path):
    """
    Real, direct template surgery (not a mock): removes the
    template's own second staff definition and content, exactly
    matching what a user manually stripping the treble staff in
    MuseScore would produce, so this test exercises the same
    real structure the original bug report was built on.
    """

    with zipfile.ZipFile(TEMPLATE_PATH) as z:
        infos = z.infolist()
        contents = {info.filename: z.read(info.filename) for info in infos}

    mscx_name = [n for n in contents if n.endswith(".mscx")][0]
    root = ET.fromstring(contents[mscx_name])

    score_el = root.find(".//{*}Score")
    part_el = root.find(".//{*}Part")

    staff_defs = part_el.findall("{*}Staff")
    treble_def = next(
        s for s in staff_defs
        if s.find("{*}StaffType") is not None
        and s.find("{*}StaffType").attrib.get("group") == "pitched"
    )
    part_el.remove(treble_def)

    instrument_el = root.find(".//{*}Instrument")
    for clef_el in list(instrument_el.findall("{*}clef")):
        if clef_el.attrib.get("staff") == "2":
            instrument_el.remove(clef_el)

    staves = [c for c in score_el if c.tag.split("}")[-1] == "Staff"]
    treble_staff = next(s for s in staves if s.attrib.get("id") == "2")
    score_el.remove(treble_staff)

    contents[mscx_name] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )

    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in infos:
            dst.writestr(info, contents[info.filename])


def _make_no_staff_template(dst_path):
    """
    A genuinely invalid template -- no staves at all, either
    level. Used to confirm the explicit-error path (category 3).
    """

    with zipfile.ZipFile(TEMPLATE_PATH) as z:
        infos = z.infolist()
        contents = {info.filename: z.read(info.filename) for info in infos}

    mscx_name = [n for n in contents if n.endswith(".mscx")][0]
    root = ET.fromstring(contents[mscx_name])

    score_el = root.find(".//{*}Score")
    part_el = root.find(".//{*}Part")

    for staff_def in list(part_el.findall("{*}Staff")):
        part_el.remove(staff_def)

    for staff in [c for c in score_el if c.tag.split("}")[-1] == "Staff"]:
        score_el.remove(staff)

    contents[mscx_name] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )

    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in infos:
            dst.writestr(info, contents[info.filename])


def _load_source(path):

    p = MuseScoreFile(path)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    return p, staff_used


def _find_all_notes(element):
    """
    Namespace-agnostic Note-finder: {*}TAG's own wildcard match
    requires SOME namespace URI to match against, and does not
    match a namespace-less tag -- confirmed real: the .mscx
    re-parsed from a saved-and-reloaded .mscz file here carries
    no namespace at all, so {*}Note silently finds nothing.
    """

    return [
        el for el in element.iter()
        if el.tag.split("}")[-1] == "Note"
    ]


# ---------------------------------------------------------
# 1 -- TAB-only template: BO now generates successfully with a
# template containing only the TAB staff
# ---------------------------------------------------------

def test_tab_only_template_generates_successfully():

    tab_only_path = os.path.join(
        tempfile.gettempdir(), "bo56_tab_only_template.mscz"
    )

    _make_tab_only_template(tab_only_path)

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, OPEN_C, staff_used, tab_only_path, "output",
            service, filename="bo56_test_tab_only.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        # Only ever the TAB staff -- nothing to remove, and
        # nothing crashed trying to find a second staff that was
        # never there.
        assert [s.attrib.get("id") for s in staves] == ["1"]

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)

        if os.path.exists(tab_only_path):

            os.remove(tab_only_path)


# ---------------------------------------------------------
# 2 -- current two-staff template: generation still works,
# unchanged
# ---------------------------------------------------------

def test_two_staff_template_still_generates_tab_only_by_default():

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, OPEN_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="bo56_test_two_staff.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        # Default include_notation=False -- treble staff is
        # still removed exactly as before BO-56.
        assert [s.attrib.get("id") for s in staves] == ["1"]

        assert applied >= 0

        assert exceptions == []

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- missing/invalid required template structure: a clear,
# intentional error, not an IndexError
# ---------------------------------------------------------

def test_invalid_template_raises_clear_error_not_indexerror():

    invalid_path = os.path.join(
        tempfile.gettempdir(), "bo56_no_staff_template.mscz"
    )

    _make_no_staff_template(invalid_path)

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    try:

        try:

            generate_tab_from_template(
                p, OPEN_C, staff_used, invalid_path, "output",
                service, filename="bo56_test_invalid.mscz"
            )

            assert False, (
                "expected a ValueError for a template with no "
                "TAB staff at all"
            )

        except IndexError:

            assert False, (
                "must not be a bare IndexError -- BO-56's own "
                "entire point was to replace this with a clear, "
                "intentional error"
            )

        except ValueError as e:

            # Confirms the error is genuinely informative, not
            # just any ValueError.
            assert "TAB staff" in str(e)

    finally:

        if os.path.exists(invalid_path):

            os.remove(invalid_path)


# ---------------------------------------------------------
# 4 -- TAB + notation generation: real pitch/tpc and rhythm
# match exactly between the two staves
# ---------------------------------------------------------

def test_notation_pitch_tpc_match_tab_exactly():

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, OPEN_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="bo56_test_notation.mscz",
            include_notation=True
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert [s.attrib.get("id") for s in staves] == ["1", "2"]

        tab_staff = next(
            s for s in staves if s.attrib.get("id") == "1"
        )

        treble_staff = next(
            s for s in staves if s.attrib.get("id") == "2"
        )

        tab_measures = tab_staff.findall("{*}Measure")

        treble_measures = treble_staff.findall("{*}Measure")

        assert len(tab_measures) == len(treble_measures)

        assert len(tab_measures) > 0

        for tab_measure, treble_measure in zip(
            tab_measures, treble_measures
        ):

            tab_notes = [
                (n.find("{*}pitch").text, n.find("{*}tpc").text)
                for n in _find_all_notes(tab_measure)
            ]

            treble_notes = [
                (n.find("{*}pitch").text, n.find("{*}tpc").text)
                for n in _find_all_notes(treble_measure)
            ]

            assert tab_notes == treble_notes

        # Real, confirmed: at least one measure has real notes
        # (not just an all-rest, all-silent song) -- a passing
        # empty-vs-empty comparison everywhere would not actually
        # prove anything.
        total_notes = sum(
            len(_find_all_notes(m)) for m in treble_measures
        )

        assert total_notes > 0

        # A treble Note must never carry fret/string -- that's a
        # TAB-specific concept.
        for note in _find_all_notes(treble_staff):

            assert note.find("{*}fret") is None

            assert note.find("{*}string") is None

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_notation_rhythm_matches_tab_exactly():

    p, staff_used = _load_source("scores/The Christmas Song.mscz")

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_D, staff_used, TEMPLATE_PATH, "output",
            service, filename="bo56_test_rhythm.mscz",
            include_notation=True
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        tab_staff = next(
            s for s in staves if s.attrib.get("id") == "1"
        )

        treble_staff = next(
            s for s in staves if s.attrib.get("id") == "2"
        )

        def event_sequence(staff):

            sequence = []

            for element in staff.iter():

                tag = element.tag.split("}")[-1]

                if tag in ("Chord", "Rest"):

                    duration_el = element.find(
                        "{*}durationType"
                    )

                    dots_el = element.find("{*}dots")

                    sequence.append((
                        tag,
                        duration_el.text
                        if duration_el is not None else None,
                        dots_el.text
                        if dots_el is not None else None
                    ))

            return sequence

        tab_sequence = event_sequence(tab_staff)

        treble_sequence = event_sequence(treble_staff)

        assert len(tab_sequence) > 0

        assert tab_sequence == treble_sequence

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_include_notation_false_by_default_unaffected():

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    # Called WITHOUT include_notation at all -- confirms the
    # parameter's own default preserves this function's exact
    # prior signature-compatible behavior.
    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, OPEN_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="bo56_test_default.mscz"
        )
    )

    try:

        with zipfile.ZipFile(output_path) as z:

            mscx_name = [
                n for n in z.namelist() if n.endswith(".mscx")
            ][0]

            content = z.read(mscx_name)

        root = ET.fromstring(content)

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert [s.attrib.get("id") for s in staves] == ["1"]

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_include_notation_true_requires_treble_staff_in_template():

    tab_only_path = os.path.join(
        tempfile.gettempdir(),
        "bo56_tab_only_for_notation_error.mscz"
    )

    _make_tab_only_template(tab_only_path)

    p, staff_used = _load_source("scores/Cousin Sally Brown.mscz")

    service = ChordService(ChordLibrary())

    try:

        try:

            generate_tab_from_template(
                p, OPEN_C, staff_used, tab_only_path, "output",
                service, filename="bo56_test_notation_error.mscz",
                include_notation=True
            )

            assert False, (
                "expected a clear ValueError requesting notation "
                "with no treble staff available to populate"
            )

        except ValueError as e:

            assert "include_notation" in str(e)

    finally:

        if os.path.exists(tab_only_path):

            os.remove(tab_only_path)


# ---------------------------------------------------------
# 5 -- no regression: BO-54 chord-shape selection is completely
# unaffected by include_notation
# ---------------------------------------------------------

def test_chord_shapes_identical_with_and_without_notation():

    p1, staff_used1 = _load_source(
        "scores/The Christmas Song.mscz"
    )

    p2, staff_used2 = _load_source(
        "scores/The Christmas Song.mscz"
    )

    service = ChordService(ChordLibrary())

    output_tab_only, _, _, _ = generate_tab_from_template(
        p1, DOUBLE_D, staff_used1, TEMPLATE_PATH, "output",
        service, filename="bo56_test_shapes_tabonly.mscz"
    )

    output_with_notation, _, _, _ = generate_tab_from_template(
        p2, DOUBLE_D, staff_used2, TEMPLATE_PATH, "output",
        service, filename="bo56_test_shapes_notation.mscz",
        include_notation=True
    )

    try:

        def fret_diagrams(path):

            with zipfile.ZipFile(path) as z:

                mscx_name = [
                    n for n in z.namelist()
                    if n.endswith(".mscx")
                ][0]

                content = z.read(mscx_name)

            root = ET.fromstring(content)

            fds = []

            for fd in root.iter():

                if fd.tag.split("}")[-1] == "FretDiagram":

                    fo = fd.find("{*}fretOffset")

                    fds.append(
                        fo.text if fo is not None else None
                    )

            return fds

        fds_tab_only = fret_diagrams(output_tab_only)

        fds_with_notation = fret_diagrams(output_with_notation)

        # Real, confirmed: BO-54's own chord-shape selection
        # (fretOffset per FD, in document order) is byte-for-byte
        # identical regardless of include_notation -- this is a
        # score-generation/template concern only, never touching
        # chord-shape selection at all.
        assert fds_tab_only == fds_with_notation

        assert len(fds_tab_only) > 0

    finally:

        for path in (output_tab_only, output_with_notation):

            if os.path.exists(path):

                os.remove(path)
