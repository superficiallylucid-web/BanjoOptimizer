"""
score_generator.py

Generates a playable .mscz file for a candidate tuning, by
directly editing the ORIGINAL score's own MuseScore XML rather
than reconstructing a score from scratch. This is a deliberate
architectural choice, not a shortcut:

- Preserves title, chord symbol text, lyrics, formatting, and
  timing automatically, simply by never touching that XML at
  all -- no dedicated code is needed to "preserve" any of it.
- Reuses fretboard.find_positions() / fretboard.best_position()
  for choosing each melody note's new string/fret -- both
  already existed before the Playing Model work and are
  unrelated to it; nothing here uses or depends on
  playing_model.py.
- Does not duplicate any XML-writing infrastructure; this is
  the first code in the project that WRITES a .mscz, but it
  works by editing the tree parser.py already built for reading
  (MuseScoreFile.root/.tree), not by inventing a parallel
  representation of the file format.

WHAT THIS EDITS:
- Each Instrument's <StringData> (the tuning's open-string
  pitches) is replaced with the target tuning's own notes.
- Every melody <Note> that has <fret>/<string> children (i.e.
  every TAB-notated note) gets a new <fret>/<string> for the
  target tuning, chosen via find_positions()+best_position()
  (unchanged, pre-existing melody-position logic). The note's
  <pitch>/<tpc> are never touched -- it's the same pitch, just
  reached differently.
- A Note using the 5th string (MuseScore <string> value "4" --
  see NOTE ON STRING NUMBERING below) is left untouched
  entirely, consistent with this project's established rule
  that the 5th string is handled separately from the fretted
  melody strings, everywhere else in the codebase.

WHAT THIS DELIBERATELY DOES NOT EDIT (documented limitation,
not an oversight -- see the module's own docstring section
"KNOWN LIMITATION" below):
- <FretDiagram> chord-shape diagrams are left as-is from the
  source tuning. They will visually show the WRONG shape for
  the new tuning after this runs. Regenerating them well needs
  chord_service.py integration (picking a real shape for each
  chord symbol in the new tuning) and chord-symbol-driven
  substitution is explicitly out of scope for this first
  version ("do not attempt automatic chord substitution yet").

NOTE ON STRING NUMBERING -- confirmed by direct inspection of
real files, not assumed:
MuseScore's own per-Note <string> attribute uses the OPPOSITE
convention from this project's internal one. Internally
(tuning.notes[1:], fretboard.find_positions(), etc.), index 0
is the 4th (lowest) melody string. In a MuseScore <Note>
element, <string>0</string> is the 1ST (highest) string, and
<string>3</string> is the 4th -- confirmed against two real
notes (pitch 64 fret 0 string 0 -> the open 1st string; pitch
59 fret 2 string 2 -> the 3rd string at fret 2). <string>4</string>
is the 5th string. Converting between the two is
`muse_string = 3 - internal_index`, applied consistently
wherever this module reads or writes a Note's <string> value.

<StringData>'s own <string> children are NOT affected by this
reversal -- they list open-string PITCHES in the same 5th,
4th..1st order this project's Tuning.notes already uses,
confirmed directly against a real file's StringData matching
tunings.py's own A Modal Sawmill definition exactly.
"""

import copy

import re

import zipfile

import xml.etree.ElementTree as ET

from pathlib import Path

from fretboard import find_positions, best_position


def _sanitize_filename(text):
    """
    Strip characters that aren't safe in a filename on common
    filesystems, collapsing anything else to a space.
    """

    cleaned = re.sub(r'[\\/:*?"<>|]', "", text)

    return cleaned.strip()


def _find_staff_element(root, staff_number):
    """
    Locate the content <Staff> element matching staff_number,
    using the SAME counting convention parser.py's own
    read_melody_notes()/read_harmonies() already use (every
    <Staff> tag encountered in document order counts, including
    Part-definition Staff tags) -- so a staff_number obtained
    from read_melody_notes() refers to the same element here.
    """

    current_staff = 0

    for element in root.iter():

        tag = element.tag.split("}")[-1]

        if tag == "Staff":

            current_staff += 1

            if current_staff == staff_number:

                return element

    return None


def _staff_has_tab_notes(staff_element):
    """
    True if staff_element contains at least one Note with both
    <fret> and <string> -- i.e. it's actually a TAB-notated
    staff with persisted position data, not just a standard-
    notation staff that happens to carry the same melody.
    """

    for note_element in staff_element.iter():

        if note_element.tag.split("}")[-1] != "Note":

            continue

        if (
            note_element.find("{*}fret") is not None
            and note_element.find("{*}string") is not None
        ):

            return True

    return False


def _find_tab_staff_element(root, staff_number):
    """
    Locate the content <Staff> element to retune, starting from
    staff_number (the melody staff read_melody_notes() picked).

    read_melody_notes()'s own "first non-empty staff" heuristic
    is the right choice for extracting melody PITCH (any staff
    carrying the tune works equally well for that), but it can
    pick a standard-notation staff with no persisted <fret>/
    <string> data at all -- confirmed with a real file (White
    Christmas: Part order is Piano-then-Banjo, so the first
    non-empty staff is Piano, which has none). When that
    happens, this searches the OTHER content staves for one
    that actually has TAB data, and uses that instead.

    Returns (staff_element, actual_staff_number_used), or
    (None, None) if no staff with TAB data exists at all.
    """

    given_staff = _find_staff_element(root, staff_number)

    if given_staff is not None and _staff_has_tab_notes(given_staff):

        return given_staff, staff_number

    # Fall back: walk every content <Staff> and use the first
    # one that actually has fret/string data.
    current_staff = 0

    for element in root.iter():

        tag = element.tag.split("}")[-1]

        if tag != "Staff":

            continue

        current_staff += 1

        if _staff_has_tab_notes(element):

            return element, current_staff

    return None, None


def _retune_melody_notes(staff_element, tuning):
    """
    Update every TAB-notated <Note> under staff_element to a
    new <fret>/<string> for `tuning`, choosing the position via
    the existing fretboard.find_positions()/best_position()
    (unchanged). Notes without <fret>/<string> (e.g. on a
    linked standard-notation staff) are left alone. A note on
    the 5th string (<string>4</string>) is left alone -- see
    module docstring.

    Returns the number of notes actually retuned, for the
    caller to report/verify.
    """

    open_notes = tuning.notes[1:]

    retuned_count = 0

    for note_element in staff_element.iter():

        if note_element.tag.split("}")[-1] != "Note":

            continue

        pitch_element = note_element.find("{*}pitch")

        fret_element = note_element.find("{*}fret")

        string_element = note_element.find("{*}string")

        if (
            pitch_element is None
            or fret_element is None
            or string_element is None
        ):

            continue

        if string_element.text == "4":

            # 5th string -- handled separately everywhere else
            # in this project; left untouched here too.
            continue

        pitch = int(pitch_element.text)

        positions = find_positions(pitch, open_notes)

        if not positions:

            # No realization exists on the new tuning within
            # find_positions()'s own range -- leave this note's
            # existing fret/string as-is rather than guess.
            # Documented limitation: this can happen for a
            # pitch outside the new tuning's practical range.
            continue

        chosen = best_position(positions)

        fret_element.text = str(chosen["fret"])

        string_element.text = str(3 - chosen["string"])

        retuned_count += 1

    return retuned_count


def _apply_tuning_to_string_data(root, tuning):
    """
    Replace every <StringData>'s open-string pitches with
    tuning.notes -- see module docstring for why the ordering
    already matches with no conversion needed.

    Returns the number of StringData elements updated.
    """

    updated_count = 0

    for element in root.iter():

        if element.tag.split("}")[-1] != "StringData":

            continue

        string_children = [
            child for child in element
            if child.tag.split("}")[-1] == "string"
        ]

        if len(string_children) != len(tuning.notes):

            # Not a 5-string instrument's StringData (or an
            # unexpected shape) -- leave it alone rather than
            # guess at a mismatched mapping.
            continue

        for child, pitch in zip(string_children, tuning.notes):

            child.text = str(pitch)

        updated_count += 1

    return updated_count


def generate_mscz(
    score_file, tuning, staff_number, output_folder, filename=None
):
    """
    Generate a new .mscz for `tuning`, based on the already-
    opened `score_file` (a parser.MuseScoreFile with .open()
    already called -- its .root/.tree are edited in place, on
    an in-memory COPY, never mutating the caller's own parsed
    state).

    staff_number: the melody staff to retune -- pass the same
    value read_melody_notes() returned. If that staff doesn't
    actually have persisted TAB (fret/string) data -- it can be
    a standard-notation staff carrying the same melody (see
    _find_tab_staff_element()'s own docstring for a real
    example) -- the actual staff with TAB data is found and
    used automatically instead.

    filename: optional explicit output filename. Defaults to
    "{title} - {tuning.name}.mscz", matching this project's
    existing output-folder convention (see main.py's
    OUTPUT_FOLDER).

    Returns (output_path, retuned_note_count, string_data_count).
    """

    output_folder = Path(output_folder)

    output_folder.mkdir(exist_ok=True)

    # Work on a deep copy of the tree -- generate_mscz() must
    # never mutate the caller's already-parsed score_file, since
    # main.py's own scoring/reporting may still need it
    # untouched.
    tree_copy = copy.deepcopy(score_file.tree)

    root_copy = tree_copy.getroot()

    staff_element, actual_staff_number = _find_tab_staff_element(
        root_copy, staff_number
    )

    if staff_element is None:

        raise ValueError(
            "No staff with TAB (fret/string) data was found in "
            "this score -- nothing to retune."
        )

    retuned_count = _retune_melody_notes(staff_element, tuning)

    string_data_count = _apply_tuning_to_string_data(
        root_copy, tuning
    )

    if filename is None:

        title = score_file.score.title or "Untitled"

        filename = _sanitize_filename(
            f"{title} - {tuning.name}"
        ) + ".mscz"

    output_path = output_folder / filename

    new_mscx_bytes = ET.tostring(
        root_copy, encoding="UTF-8", xml_declaration=True
    )

    with zipfile.ZipFile(score_file.filename, "r") as source_zip:

        mscx_name = [
            name for name in source_zip.namelist()
            if name.endswith(".mscx")
        ][0]

        with zipfile.ZipFile(
            output_path, "w", zipfile.ZIP_DEFLATED
        ) as output_zip:

            for name in source_zip.namelist():

                if name == mscx_name:

                    output_zip.writestr(name, new_mscx_bytes)

                else:

                    output_zip.writestr(
                        name, source_zip.read(name)
                    )

    return output_path, retuned_count, string_data_count
