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

import os

import base64

import zipfile

import xml.etree.ElementTree as ET

from pathlib import Path

from fretboard import (
    find_positions, best_position, parse_shape, sounding_notes
)

from music import (
    quality_code_to_display_name, pitch_name, midi_to_note_name
)

from playing_model import _chord_working_fret


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
    True if the SUBSTANTIAL MAJORITY of staff_element's Notes
    have both <fret> and <string> -- i.e. it's genuinely a TAB-
    notated staff with persisted position data throughout, not
    just a standard-notation staff that happens to carry a few
    stray fret/string values.

    Confirmed real reason this needs a majority threshold, not
    "at least one": a real source file was found with 2 stray
    fret-tagged notes out of 197 on its Piano (standard
    notation) staff -- almost certainly leftover noise from an
    earlier edit, not an actual TAB arrangement. A genuine TAB
    staff has fret/string on essentially all of its notes (100%
    in every real TAB staff this project has inspected); a
    50% threshold cleanly separates the two cases without being
    fragile to a handful of stray values either way.
    """

    total_notes = 0

    fretted_notes = 0

    for note_element in staff_element.iter():

        if note_element.tag.split("}")[-1] != "Note":

            continue

        total_notes += 1

        if (
            note_element.find("{*}fret") is not None
            and note_element.find("{*}string") is not None
        ):

            fretted_notes += 1

    if total_notes == 0:

        return False

    return (fretted_notes / total_notes) >= 0.5


# ---------------------------------------------------------
# Creating a TAB staff from scratch -- BO-15-FIX / BO-16
# ---------------------------------------------------------
#
# Used when the source score has NO existing staff with TAB
# data at all (the normal case -- most real input scores have
# never been arranged for banjo). Reproduces the structure of a
# REAL, known-good banjo-tablature Part -- not invented.
#
# A banjo-tablature Part has exactly ONE definition <Staff>,
# not two. An earlier version of this code created a second,
# "linked companion" pitched-notation staff, based on an
# incorrect generalization from files where a user had
# separately, optionally added one after the fact. Confirmed
# wrong by direct comparison against a real reference file:
# MuseScore's own "add instrument" workflow, with nothing else
# done manually, produces one staff, no linkedTo at all -- and
# the extra, structurally-unexpected second staff was the
# actual cause of MuseScore reporting "Incomplete measure" on
# every generated file (see BO-16 investigation).

_TAB_PART_TEMPLATE = """<Part id="{part_id}">
<Staff>
<eid>{tab_staff_eid}</eid>
<StaffType group="tablature">
<name>tab5StrSimple</name>
<lines>4</lines>
<lineDistance>1.5</lineDistance>
<clef>0</clef>
<stemless>1</stemless>
<timesig>0</timesig>
<color r="148" g="148" b="148" a="255" />
<durations>0</durations>
<durationFontName>MuseScore Tab Modern</durationFontName>
<durationFontSize>15</durationFontSize>
<durationFontY>0</durationFontY>
<fretUseTextStyle>1</fretUseTextStyle>
<fretTextStyle>tab_fret_number</fretTextStyle>
<linesThrough>0</linesThrough>
<minimStyle>0</minimStyle>
<onLines>1</onLines>
<showRests>0</showRests>
<stemsDown>1</stemsDown>
<stemsThrough>0</stemsThrough>
<upsideDown>0</upsideDown>
<useNumbers>1</useNumbers>
</StaffType>
<defaultClef>G8vb</defaultClef>
</Staff>
<trackName>Banjo</trackName>
<preferSharpFlat>none</preferSharpFlat>
<Instrument id="banjo-tablature">
<trackName>Banjo (tablature)</trackName>
<minPitchP>48</minPitchP>
<maxPitchP>87</maxPitchP>
<minPitchA>48</minPitchA>
<maxPitchA>87</maxPitchA>
<instrumentId>pluck.banjo</instrumentId>
<clef>G8vb</clef>
<singleNoteDynamics>0</singleNoteDynamics>
<glissandoStyle>portamento</glissandoStyle>
<StringData>
<frets>24</frets>
<string>{s0}</string>
<string>{s1}</string>
<string>{s2}</string>
<string>{s3}</string>
<string>{s4}</string>
</StringData>
<Channel>
<program value="105" />
<synti>Fluid</synti>
</Channel>
<Channel name="harmony">
<program value="0" />
<synti>Fluid</synti>
</Channel>
</Instrument>
</Part>"""


def _build_tab_part_element(tuning, part_id):
    """
    Build a new <Part> element for a banjo-tablature
    instrument, using tuning.notes for StringData. See module
    notes above for where this structure came from -- a single
    definition Staff, no linked companion (confirmed against a
    real MuseScore-created reference: adding a banjo instrument
    normally creates exactly one staff, not two).
    """

    xml_text = _TAB_PART_TEMPLATE.format(
        part_id=part_id,
        tab_staff_eid=_generate_eid(),
        s0=tuning.notes[0],
        s1=tuning.notes[1],
        s2=tuning.notes[2],
        s3=tuning.notes[3],
        s4=tuning.notes[4]
    )

    return ET.fromstring(xml_text)


def _next_part_id(root):
    """
    A Part id that doesn't collide with any existing one.
    Real Part ids observed are small integers, not necessarily
    matching document order -- this just picks one higher than
    every existing id, which is always safe regardless of what
    order they're in.
    """

    existing_ids = []

    for element in root.iter():

        if element.tag.split("}")[-1] != "Part":

            continue

        try:

            existing_ids.append(int(element.attrib.get("id", 0)))

        except ValueError:

            continue

    return max(existing_ids, default=0) + 1


def _next_staff_ids(root, count):
    """
    `count` content-<Staff> ids that don't collide with any
    existing one, continuing sequentially after the highest
    existing id -- matching the pattern every real file this
    project has inspected uses (ids assigned sequentially,
    without gaps).
    """

    highest = 0

    for element in root.iter():

        if element.tag.split("}")[-1] != "Staff":

            continue

        try:

            highest = max(highest, int(element.attrib.get("id", 0)))

        except (TypeError, ValueError):

            continue

    return [highest + 1 + i for i in range(count)]


def _regenerate_eids(element):
    """
    Replace every <eid> text value found anywhere within
    element's subtree with a freshly generated one (see
    _generate_eid()).

    Root cause this exists for -- confirmed by direct comparison
    against a real, working file: <eid> values must be globally
    unique across the ENTIRE file, with NO exception for linked
    staff pairs (a real TAB staff and its own linked companion
    have zero shared content eids; the linked relationship is
    established purely at the Part-definition level via
    <linkedTo>, never by sharing content-level eids). A deep
    copy of an existing staff's content carries over its
    original eids verbatim, producing duplicates the moment
    that copy exists anywhere else in the file -- MuseScore
    reported this as "Incomplete measure: Found 0/1" on every
    newly created staff, which this fixes.
    """

    for descendant in element.iter():

        if descendant.tag.split("}")[-1] == "eid":

            descendant.text = _generate_eid()


def _find_source_concert_key(source_staff_element):
    """
    The concertKey value to use for the new staff's own first
    measure -- see _normalize_copied_content()'s own docstring
    for why this is needed at all.

    Uses the FIRST explicit <KeySig> found anywhere in the
    source staff, if any (a source that changes key partway
    through would still want its OPENING key here, and this is
    the first one encountered in document order). If the source
    has no explicit KeySig at all -- confirmed real case: it
    then relies on MuseScore's own implicit default, which is
    concertKey 0 (C major/A minor, no sharps or flats) -- that
    default is used here too, since that's genuinely the source
    staff's own (implicit) key, not an invented one.
    """

    for element in source_staff_element.iter():

        if element.tag.split("}")[-1] != "KeySig":

            continue

        concert_key_element = element.find("{*}concertKey")

        if concert_key_element is not None:

            return concert_key_element.text

    return "0"


def _normalize_copied_content(new_staff, concert_key):
    """
    Fix structural differences confirmed (by direct, exhaustive
    comparison against a real MuseScore-created reference file)
    between a staff's own raw content and what a real "paste
    into a new staff" operation actually produces, that a plain
    deep copy doesn't account for:

    - A <Measure>'s own DIRECT children other than <voice> --
      confirmed 100% consistent across every measure in a real
      reference file (34/34 source measures have their own
      <eid>/<stretch>/<LayoutBreak>; 0/34 of the newly-pasted
      staff's measures have any of them). A real paste creates
      fresh Measure wrappers around the pasted voice content,
      not literal clones of the source measure's own metadata.
      This was the actual remaining cause of "Incomplete
      measure" persisting even after every WITHIN-voice fix
      below was already correct -- an earlier structural
      comparison checked voice content only and missed this
      entirely.
    - A new staff's first measure needs its own explicit
      <KeySig> inside its voice, even when the SOURCE staff
      never states one anywhere (relying on the implicit
      default instead). Inserted as the first child of the
      first measure's voice, before <TimeSig>, matching the
      real reference's own child order exactly.
    - <Tempo> is NOT duplicated onto a new staff in a real file
      (it stays on whichever staff originally had it) -- every
      <Tempo> found anywhere in the copied voice content is
      removed.
    - <Segment> elements present in the SOURCE staff's own raw
      voice content are NOT carried over by a real paste
      operation either -- confirmed by direct comparison: the
      real reference file's source (Piano) staff has this
      element in places its own newly-pasted Banjo staff does
      not, even though the actual musical content (Chord/
      Harmony/FretDiagram) at those positions is otherwise
      identical.
    - Frame elements (<VBox> etc) that sit as DIRECT SIBLINGS
      of <Measure> at the STAFF level -- typically a title/
      subtitle frame before the first measure -- are NOT
      carried over either. Confirmed by direct comparison: the
      source (Piano) staff's first direct child is <VBox>, but
      the real pasted Banjo staff's first direct child is
      <Measure> -- straight to musical content, no frame at
      all. This was missed by every earlier structural
      verification here, because those all compared Measure
      elements to each other by position/index, which can never
      reveal an EXTRA sibling element sitting alongside them at
      the staff level.
    """

    for child in list(new_staff):

        if child.tag.split("}")[-1] != "Measure":

            new_staff.remove(child)

    measures = [
        child for child in new_staff
        if child.tag.split("}")[-1] == "Measure"
    ]

    for measure in measures:

        for child in list(measure):

            if child.tag.split("}")[-1] != "voice":

                measure.remove(child)

    parent_map = {
        child: parent
        for parent in new_staff.iter() for child in parent
    }

    for element in list(new_staff.iter()):

        tag = element.tag.split("}")[-1]

        if tag not in ("Tempo", "Segment"):

            continue

        parent = parent_map.get(element)

        if parent is not None:

            parent.remove(element)

    if not measures:

        return

    first_measure = measures[0]

    for voice in first_measure:

        if voice.tag.split("}")[-1] != "voice":

            continue

        has_keysig = any(
            child.tag.split("}")[-1] == "KeySig"
            for child in voice
        )

        if has_keysig:

            continue

        keysig_element = ET.Element("KeySig")

        eid_element = ET.SubElement(keysig_element, "eid")

        eid_element.text = _generate_eid()

        concert_key_element = ET.SubElement(
            keysig_element, "concertKey"
        )

        concert_key_element.text = concert_key

        voice.insert(0, keysig_element)


def _build_tab_content_staff(source_staff_element, new_staff_id):
    """
    Build a new content <Staff id="..."> for the TAB, from a
    deep copy of source_staff_element's own content (Measures,
    Chords, Notes, Rests, Harmony -- whatever it already has).
    Notes keep their existing <pitch>/<tpc> unchanged; no
    <fret>/<string> is added here -- that happens afterward via
    the EXISTING _retune_melody_notes(), reused unmodified, so
    fret/string assignment for a brand-new staff uses the exact
    same logic (find_positions()/best_position()) as re-fretting
    an existing one, not a second, separate mechanism.

    Every <eid> in the copied content is regenerated -- see
    _regenerate_eids()'s own docstring for why this is required,
    not optional. The copied content is also normalized -- see
    _normalize_copied_content()'s own docstring for the real
    structural differences this accounts for.
    """

    concert_key = _find_source_concert_key(source_staff_element)

    new_staff = copy.deepcopy(source_staff_element)

    new_staff.set("id", str(new_staff_id))

    _regenerate_eids(new_staff)

    _normalize_copied_content(new_staff, concert_key)

    return new_staff


def _create_tab_staff(root, source_staff_element, tuning):
    """
    Build and insert a brand-new banjo-tablature Part + a single
    content Staff into `root`, from source_staff_element's own
    melody content (which has no TAB data at all -- see module
    notes). Only one staff -- confirmed against a real
    MuseScore-created reference file (adding a banjo instrument
    the normal way creates exactly one staff, no linked
    companion; an earlier version of this function created a
    second, unnecessary linked staff, which was the actual cause
    of MuseScore's "Incomplete measure" errors on generated
    files).

    Returns the new content-Staff element, ready for the caller
    to run _retune_melody_notes()/_apply_chord_shapes() on
    exactly as it would for an already-existing TAB staff.
    """

    score_element = root.find("{*}Score")

    part_id = _next_part_id(root)

    new_part = _build_tab_part_element(tuning, part_id)

    score_element.append(new_part)

    [new_staff_id] = _next_staff_ids(root, 1)

    content_staff = _build_tab_content_staff(
        source_staff_element, new_staff_id
    )

    score_element.append(content_staff)

    return content_staff


def _find_notation_staff_element(root, staff_number):
    """
    Locate the NOTATION (non-TAB) content <Staff> to use as the
    generation source, starting from staff_number (the melody
    staff read_melody_notes() picked for SCORING purposes --
    unchanged, still used for extracting melody PITCH, which
    works equally well from either a notation or TAB staff, so
    nothing about scoring is affected by this function).

    Existing TAB anywhere in the score -- whether on this exact
    staff or any other -- is NEVER used, modified, or reused as
    a shortcut. This was an earlier, incorrect assumption (an
    existing TAB staff found elsewhere in the document used to
    be retuned in place instead of generating fresh content) --
    corrected per explicit clarification: whether a score
    happens to already contain TAB must not change what BO
    produces or how. The notation is always the source; any
    existing TAB is inert, irrelevant information, ignored
    completely, exactly as if it were never there.

    The only thing this checks for is the rare case where
    staff_number ITSELF happens to already be a TAB staff --
    i.e. read_melody_notes()'s own "first non-empty staff"
    heuristic landed on TAB content rather than the intended
    notation. When that happens, the other content staves are
    searched for the first genuine notation staff (has real
    melodic content, and is NOT majority-fretted) to use
    instead.

    Returns (staff_element, staff_number_used), or (None, None)
    if no notation staff can be found at all.
    """

    given_staff = _find_staff_element(root, staff_number)

    if given_staff is not None and not _staff_has_tab_notes(
        given_staff
    ):

        return given_staff, staff_number

    current_staff_number = 0

    for element in root.iter():

        if element.tag.split("}")[-1] != "Staff":

            continue

        current_staff_number += 1

        if element is given_staff:

            continue

        has_notes = any(
            child.tag.split("}")[-1] == "Note"
            for child in element.iter()
        )

        if has_notes and not _staff_has_tab_notes(element):

            return element, current_staff_number

    return None, None


def _retune_melody_notes(staff_element, tuning):
    """
    Set every melody <Note> under staff_element to a <fret>/
    <string> for `tuning`, choosing the position via the
    existing fretboard.find_positions()/best_position()
    (unchanged) either way. Handles both real cases:

    - The note already has <fret>/<string> (an existing TAB
      staff being re-fretted for a new tuning) -- updated in
      place.
    - The note has neither (content freshly copied from a
      standard-notation staff that's never had TAB data --
      see _create_tab_staff()) -- <fret>/<string> are created
      and appended, in the confirmed real child order (after
      <tpc>, matching every real TAB Note this project has
      inspected).

    A note with only ONE of the two present (malformed/
    unexpected) is left alone rather than guessed at.

    A note already on the 5th string (<string>4</string>) is
    left untouched -- handled separately everywhere else in
    this project. This only applies to the update case; a
    freshly-created note is never assigned to the 5th string --
    there's no existing signal for when a melody note should
    become a drone note, and inventing one is out of scope here
    (documented limitation, not an oversight).

    Returns the number of notes actually set, for the caller to
    report/verify.
    """

    open_notes = tuning.notes[1:]

    retuned_count = 0

    for note_element in staff_element.iter():

        if note_element.tag.split("}")[-1] != "Note":

            continue

        pitch_element = note_element.find("{*}pitch")

        if pitch_element is None:

            continue

        fret_element = note_element.find("{*}fret")

        string_element = note_element.find("{*}string")

        has_fret = fret_element is not None

        has_string = string_element is not None

        if has_fret != has_string:

            # Malformed/unexpected -- exactly one of the pair
            # present. Not seen in any real data; skip rather
            # than guess.
            continue

        if has_fret and string_element.text == "4":

            # 5th string -- handled separately everywhere else
            # in this project; left untouched here too.
            continue

        pitch = int(pitch_element.text)

        positions = find_positions(pitch, open_notes)

        if not positions:

            # No realization exists on the new tuning within
            # find_positions()'s own range -- leave this note's
            # existing fret/string (if any) as-is rather than
            # guess. Documented limitation: this can happen for
            # a pitch outside the new tuning's practical range.
            continue

        chosen = best_position(positions)

        if not has_fret:

            fret_element = ET.SubElement(note_element, "fret")

            string_element = ET.SubElement(note_element, "string")

        fret_element.text = str(chosen["fret"])

        string_element.text = str(3 - chosen["string"])

        retuned_count += 1

    return retuned_count


# ---------------------------------------------------------
# Chord shape (FretDiagram) generation -- BO-15
# ---------------------------------------------------------
#
# NOTE ON STRING NUMBERING (different from Note's <string>!):
# A <FretDiagram>'s <string no="N"> uses this project's OWN
# internal convention directly -- N=0 is the 4th string, N=3
# the 1st -- confirmed directly against a real, known "0220"
# (E5) diagram: no=0/no=3 both marked open (matching E3/E4 open
# strings), no=1/no=2 both fret 2 (matching the two B/E notes
# at fret 2). This is the OPPOSITE of Note's <string> attribute
# (see _retune_melody_notes' own docstring, which IS reversed).
# No conversion is applied here -- do not add one by analogy to
# the Note-writing code above; that would be wrong.
#
# frets/fretOffset/autoplace/offset are all confirmed OPTIONAL
# by direct inspection of real files -- several genuine
# FretDiagrams in production scores omit <frets> entirely, and
# still more omit <autoplace>/<offset>. This code always writes
# shapes as ABSOLUTE frets (no <fretOffset>) and omits <frets>
# entirely, letting MuseScore use its own default display
# window -- the simplest choice that real data confirms is
# valid, not a guess.
#
# eid is confirmed present on every real FretDiagram (23
# characters, matching base64url-encoded 17 random bytes,
# unpadded). A new one is generated in that same format when
# creating a fresh element; an existing element's eid is
# preserved when updating it in place.
#
# KNOWN LIMITATION, not attempted: a chosen shape containing a
# muted string (e.g. "--012") is skipped rather than written --
# no real FretDiagram with a muted-string marker has been found
# in any file this project has inspected, so there's no
# confirmed representation to reuse, and inventing one would
# violate this task's own explicit instruction not to invent a
# new representation.

def _generate_eid():
    """
    A plausible, syntactically-matching eid -- see module notes
    above for how the real format was determined. Only needs to
    be unique within the file; MuseScore's own eid semantics
    beyond that aren't relied on here.
    """

    return base64.urlsafe_b64encode(os.urandom(17)).decode(
        "ascii"
    ).rstrip("=")


def _set_fret_diagram_content(
    fret_diagram_element, values, is_exception=False
):
    """
    (Re)write a <FretDiagram> element's content for `values`
    (parse_shape() output -- one entry per string, int fret,
    0 for open, or None for muted). Clears any existing
    children first, so this works identically whether
    fret_diagram_element is freshly created or being updated in
    place. Preserves an existing <eid> if there was one;
    generates a new one otherwise.

    Writes MuseScore's "Visible frets" (XML <frets>) as 4 for
    every diagram (BO-19 -- confirmed via direct inspection of a
    real example score that this is a SEPARATE property from
    <strings>, easy to confuse since both happened to read 4 in
    that file).

    Also sets MuseScore's "Fret Number" (XML <fretOffset>) so a
    shape doesn't display as an unlabeled block of empty frets
    when it starts above the nut. BO-19, confirmed via the same
    real example score:

    - Open strings (fret 0) are always ignored when finding the
      "lowest fret" -- they display exactly as before regardless
      (an open-string <marker>, never affected by fretOffset).
    - If the lowest FRETTED (non-open) value across the shape is
      1 or there are no fretted strings at all, <fretOffset> is
      left unset -- the normal first-position display.
    - If the lowest fretted value is 2 or higher, <fretOffset>
      is set to (lowest_fret - 1) -- confirmed directly: a real
      example with <fretOffset>2</fretOffset> is the intended
      encoding for a shape whose lowest fret is 3 (MuseScore's
      UI "Fret Number" is fretOffset + 1 -- 1-indexed display of
      a 0-indexed-from-the-nut offset).
    - Critically, once fretOffset is set, each <dot fret="N">
      becomes RELATIVE to it (N = absolute_fret - fretOffset),
      not absolute -- confirmed directly against that same real
      example (fretOffset=2 paired with dot values 1/2/3
      representing absolute frets 3/4/5, not frets 1/2/3). Open
      strings are entirely unaffected by this -- their <marker>
      is written the same way regardless of fretOffset, since
      they were never assigned a fret to make relative.

    Returns False (and leaves the element untouched) if `values`
    contains a muted string -- see module notes on why that's
    not attempted.

    is_exception: BO-21 -- when True, marks the diagram red
    (<color r="255" g="0" b="4" a="255" />, a direct child of
    FretDiagram itself, sitting after <eid> and before the
    inner <fretDiagram> -- confirmed by direct inspection of a
    real MuseScore file with a manually-colored FretDiagram, not
    guessed) to flag that this chord's melody note at its own
    onset could not be included in a practical voicing, and the
    normal best fallback shape was used instead. Never changes
    which shape is written -- `values` is still whatever the
    caller already selected; this only affects the diagram's
    color. False (the default) omits <color> entirely, matching
    every FretDiagram this project generated before BO-21.
    """

    if any(value is None for value in values):

        return False

    existing_eid_element = fret_diagram_element.find("{*}eid")

    eid_text = (
        existing_eid_element.text
        if existing_eid_element is not None
        else _generate_eid()
    )

    fretted_values = [
        fret for fret in values if fret is not None and fret > 0
    ]

    lowest_fretted = min(fretted_values, default=None)

    if lowest_fretted is not None and lowest_fretted >= 2:

        fret_offset_value = lowest_fretted - 1

    else:

        fret_offset_value = 0

    fret_diagram_element.clear()

    if fret_offset_value > 0:

        fret_offset_element = ET.SubElement(
            fret_diagram_element, "fretOffset"
        )

        fret_offset_element.text = str(fret_offset_value)

    frets_element = ET.SubElement(fret_diagram_element, "frets")

    frets_element.text = "4"

    strings_element = ET.SubElement(fret_diagram_element, "strings")

    strings_element.text = str(len(values))

    eid_element = ET.SubElement(fret_diagram_element, "eid")

    eid_element.text = eid_text

    if is_exception:

        # Confirmed by direct inspection of a real MuseScore
        # file with a manually-colored FretDiagram (BO-21) --
        # <color> is a direct child of FretDiagram itself (not
        # of individual strings/dots -- it colors the whole
        # diagram at once), sitting after <eid> and before the
        # inner <fretDiagram>. r=255 g=0 b=4 a=255 is the exact
        # value from that real file -- reproduced verbatim
        # rather than substituting a "pure" red guess. A normal
        # (non-exception) diagram simply omits this element
        # entirely, matching every FretDiagram this project has
        # generated before BO-21 -- confirmed none of them ever
        # had a <color> child.
        color_element = ET.SubElement(
            fret_diagram_element, "color"
        )

        color_element.set("r", "255")

        color_element.set("g", "0")

        color_element.set("b", "4")

        color_element.set("a", "255")

    inner_element = ET.SubElement(fret_diagram_element, "fretDiagram")

    for string_index, fret in enumerate(values):

        string_element = ET.SubElement(inner_element, "string")

        string_element.set("no", str(string_index))

        if fret == 0:

            marker_element = ET.SubElement(
                string_element, "marker"
            )

            marker_element.text = "circle"

        elif fret is not None and fret > 0:

            dot_element = ET.SubElement(string_element, "dot")

            dot_element.set(
                "fret", str(fret - fret_offset_value)
            )

            dot_element.text = "normal"

    return True


def _preferred_melody_fret(onset_notes, tuning):
    """
    BO-22/BO-30-FOLLOWUP: the fret the melody note at a chord's
    onset is likely actually played at, using the EXISTING
    fretboard.find_positions() unmodified -- no new melody-
    position representation introduced, per BO-22's own original
    investigation instruction.

    Uses the LOWEST fret among this note's own playable
    positions, not best_position()'s own general-purpose middle-
    string-biased choice (best_position()/find_positions()
    themselves remain unmodified; only this narrow, purpose-
    specific caller changes). Confirmed via a real, traced
    example (The Christmas Song / Double C, the final "C" chord)
    that best_position()'s static string bonus can pick a
    dramatically higher fret than necessary purely because of
    which string a note happens to fall on -- e.g. choosing fret
    21 (string 1, +6 bonus) over fret 14 (string 3, +2 bonus) for
    the exact same pitch, even though 14 is by far the lower,
    more natural anchor. Since this value exists specifically to
    tell chord-shape ranking "where does this note naturally
    sit," a bias toward artificially high positions pulls chord
    selection toward a needlessly high, less playable shape --
    confirmed this was happening in production before this fix.
    Verified the existing BO-22 Am/aEADE example (5320 vs
    00(10)0) is unaffected by this change.

    onset_notes: the melody Note(s) at this chord's exact onset
    (see _melody_notes_at_harmony_onset()) -- when more than one
    shares the onset, this uses the first, matching this task's
    own singular framing ("the melody note occurring at the
    chord's onset"); a full account of multiple simultaneous
    melody notes is out of scope for this narrow tiebreak.

    Returns an int fret, or None if there's no note to work
    from, or no playable position exists for it in this tuning
    (find_positions() returned nothing) -- callers should treat
    None as "no positional preference," not an error.
    """

    if not onset_notes:

        return None

    open_notes = tuning.notes[1:]

    positions = find_positions(onset_notes[0].midi, open_notes)

    if not positions:

        return None

    return min(position["fret"] for position in positions)


def _melody_notes_at_harmony_onset(harmony, melody_notes):
    """
    Every melody Note (see models.py) occurring at exactly the
    same musical location (measure + beat) as harmony's own
    onset -- BO-20. Matched by (measure, beat), the same units
    both Harmony and Note already use (see Harmony's own
    docstring in models.py: beat is quarter-note position
    within the measure, computed identically for both by
    parser.py's duration-accumulation logic), so no new
    representation is introduced here.

    Returns a (possibly empty) list -- more than one Note can
    legitimately share the exact same onset (e.g. a block chord
    within the melody line itself, or overlapping voices); every
    one of them counts as "the melody note(s) at this chord's
    location," not just an arbitrarily-chosen first match. Empty
    means no melody note exists at this chord's exact onset --
    callers should fall back to the existing, non-melody-aware
    selection for that case, not search nearby.
    """

    matches = []

    for note in melody_notes:

        if note.measure != harmony.measure:

            continue

        if abs(note.beat - harmony.beat) < 0.001:

            matches.append(note)

    return matches


def _select_chord_shape_for_harmony(
    harmony, tuning, chord_service, melody_notes=None
):
    """
    The shape-selection portion of _apply_chord_shapes(),
    factored out so BO-24 can reuse the exact same selection
    (not a re-derived, potentially-diverging copy of it) as a
    read-only query before any FretDiagram is written -- see
    generate_tab_from_template()'s own use of this for melody
    fret/string anchoring.

    Returns (chosen_shape, is_exception, exception_dict) --
    chosen_shape is None (with is_exception False and
    exception_dict None) when this harmony's quality isn't
    recognized or no usable shape exists for this tuning,
    exactly matching _apply_chord_shapes()'s own "skipped"
    case. exception_dict is the BO-21 exception record (or
    None when not an exception), built identically to what
    _apply_chord_shapes() itself would append to its own
    exceptions list.
    """

    root_name = pitch_name(harmony.root_pc)

    quality_display = quality_code_to_display_name(
        harmony.quality_code
    )

    if quality_display is None:

        return None, False, None

    melody_pitches = None

    onset_notes = []

    if melody_notes is not None:

        onset_notes = _melody_notes_at_harmony_onset(
            harmony, melody_notes
        )

        if onset_notes:

            melody_pitches = {
                note.midi for note in onset_notes
            }

    if melody_pitches:

        preferred_melody_fret = _preferred_melody_fret(
            onset_notes, tuning
        )

        shapes = chord_service.get_shapes_for_exact_melody_pitch(
            tuning,
            root_name,
            harmony.root_pc,
            harmony.quality_code,
            quality_display,
            melody_pitches,
            preferred_melody_fret=preferred_melody_fret
        )

    else:

        shapes = chord_service.get_shapes(
            tuning,
            root_name,
            harmony.root_pc,
            harmony.quality_code,
            quality_display
        )

    if not shapes:

        return None, False, None

    chosen_shape = shapes[0]

    values = parse_shape(chosen_shape.shape)

    is_exception = False

    if melody_pitches and not any(
        value is None for value in values
    ):

        sounding = sounding_notes(tuning, chosen_shape.shape)

        is_exception = not any(
            note.midi in melody_pitches for note in sounding
        )

    exception_dict = None

    if is_exception:

        exception_dict = {
            "measure": harmony.measure,
            "beat": harmony.beat,
            "chord_symbol": harmony.symbol,
            "melody_pitch": (
                midi_to_note_name(sorted(melody_pitches)[0])
                if len(melody_pitches) == 1
                else "/".join(
                    midi_to_note_name(p)
                    for p in sorted(melody_pitches)
                )
            ),
            "selected_shape": chosen_shape.shape,
            "tuning_symbol": tuning.symbol
        }

    return chosen_shape, is_exception, exception_dict


def _apply_chord_shapes(
    staff_element, harmonies, tuning, chord_service,
    melody_notes=None
):
    """
    For each chord symbol on staff_element, obtain a playable
    shape for `tuning` via chord_service and write it into the
    corresponding <FretDiagram>, creating one if none exists.

    melody_notes: optional list of melody Note objects (BO-20) --
    when given, each chord's shape selection prefers a voicing
    that contains the exact pitch of whatever melody note(s)
    occur at that chord's own musical onset (see
    _melody_notes_at_harmony_onset() and
    chord_service.get_shapes_for_exact_melody_pitch() for the
    matching/ranking logic itself -- this function only wires
    the two together). Falls back to the existing, non-melody-
    aware chord_service.get_shapes() when melody_notes is None,
    or when no melody note exists at a given chord's exact
    onset -- unchanged behavior for both of those cases,
    matching every prior task's own tests exactly.

    harmonies: the ALREADY-PARSED list of Harmony objects for
    this exact staff (see parser.read_harmonies()) -- root_pc/
    quality_code aren't re-derived from the raw XML here (that
    would duplicate parser.py's own parsing). Matched to the
    raw <Harmony> XML elements by POSITION: both were built by
    walking the same staff in the same document order, so the
    Nth XML <Harmony> corresponds to harmonies[N]. If the counts
    don't match for any reason, this is treated as unsafe to
    proceed and no chord shapes are written at all, rather than
    risk pairing a shape with the wrong chord symbol.

    Returns (applied_count, skipped_count, exceptions) --
    skipped_count covers every case this deliberately doesn't
    attempt: unrecognized quality code, no usable shape for
    this tuning, or a muted-string shape (see module notes).

    exceptions: BO-21 -- a list of dicts, one per chord where a
    melody note existed at the chord's exact onset but no
    practical shape containing that exact pitch existed, so the
    normal fallback shape was used and its FretDiagram was
    marked red (see _set_fret_diagram_content()'s own docstring
    for the red-marking mechanism). Each dict has measure, beat,
    chord_symbol, melody_pitch, selected_shape, tuning_symbol --
    enough to build the report section BO-21 asks for without
    the caller needing to re-derive anything. Always an empty
    list when melody_notes is None (matching the pre-BO-21
    behavior exactly -- no melody awareness means no exceptions
    either).
    """

    xml_harmony_elements = [
        element for element in staff_element.iter()
        if element.tag.split("}")[-1] == "Harmony"
    ]

    if len(xml_harmony_elements) != len(harmonies):

        return 0, len(harmonies), []

    parent_map = {
        child: parent
        for parent in staff_element.iter()
        for child in parent
    }

    applied_count = 0

    skipped_count = 0

    exceptions = []

    for xml_harmony, harmony in zip(xml_harmony_elements, harmonies):

        chosen_shape, is_exception, exception_dict = (
            _select_chord_shape_for_harmony(
                harmony, tuning, chord_service, melody_notes
            )
        )

        if chosen_shape is None:

            skipped_count += 1

            continue

        values = parse_shape(chosen_shape.shape)

        if is_exception:

            exceptions.append(exception_dict)

        parent = parent_map[xml_harmony]

        siblings = list(parent)

        harmony_index = siblings.index(xml_harmony)

        existing_fret_diagram = None

        if (
            harmony_index + 1 < len(siblings)
            and siblings[harmony_index + 1].tag.split("}")[-1]
            == "FretDiagram"
        ):

            existing_fret_diagram = siblings[harmony_index + 1]

        elif (
            harmony_index - 1 >= 0
            and siblings[harmony_index - 1].tag.split("}")[-1]
            == "FretDiagram"
        ):

            # Confirmed real (if rare) case: a FretDiagram can
            # precede its Harmony in document order -- see
            # parser.py's own read_harmonies() docstring, which
            # handles the same bidirectional case when reading.
            existing_fret_diagram = siblings[harmony_index - 1]

        if existing_fret_diagram is not None:

            wrote = _set_fret_diagram_content(
                existing_fret_diagram, values,
                is_exception=is_exception
            )

        else:

            new_element = ET.Element("FretDiagram")

            wrote = _set_fret_diagram_content(
                new_element, values, is_exception=is_exception
            )

            if wrote:

                parent.insert(harmony_index + 1, new_element)

        if wrote:

            applied_count += 1

        else:

            skipped_count += 1

    return applied_count, skipped_count, exceptions


def generate_mscz(
    score_file, tuning, staff_number, output_folder, filename=None,
    chord_service=None
):
    """
    Generate a new .mscz for `tuning`, based on the already-
    opened `score_file` (a parser.MuseScoreFile with .open()
    already called -- its .root/.tree are edited in place, on
    an in-memory COPY, never mutating the caller's own parsed
    state).

    staff_number: the melody staff to use as the generation
    source -- pass the same value read_melody_notes() returned.
    A brand-new banjo-tablature Part and Staff are ALWAYS
    created from that staff's own notation content -- see
    _create_tab_staff()'s own docstring. Any existing TAB
    elsewhere in the score is never used or modified; see
    _find_notation_staff_element()'s own docstring for why.

    filename: optional explicit output filename. Defaults to
    "{title} - {tuning.name}.mscz", matching this project's
    existing output-folder convention (see main.py's
    OUTPUT_FOLDER).

    chord_service: optional chord_service.ChordService. When
    given, a playable chord shape (via its EXISTING
    get_shapes(), top-ranked result, unmodified) is written into
    the corresponding <FretDiagram> for each chord symbol on the
    TAB staff -- see _apply_chord_shapes()'s own docstring.
    When None (the default), chord shapes are left untouched,
    same as before this parameter existed -- fully backward
    compatible with every existing caller/test.

    Returns (output_path, retuned_note_count, string_data_count,
    chord_shapes_applied, chord_shapes_skipped).
    """

    output_folder = Path(output_folder)

    output_folder.mkdir(exist_ok=True)

    # Work on a deep copy of the tree -- generate_mscz() must
    # never mutate the caller's already-parsed score_file, since
    # main.py's own scoring/reporting may still need it
    # untouched.
    tree_copy = copy.deepcopy(score_file.tree)

    root_copy = tree_copy.getroot()

    source_staff_element, source_staff_number = (
        _find_notation_staff_element(root_copy, staff_number)
    )

    if source_staff_element is None:

        raise ValueError(
            "No notation (non-TAB) staff was found in this "
            "score -- nothing to generate a banjo arrangement "
            "from."
        )

    staff_element = _create_tab_staff(
        root_copy, source_staff_element, tuning
    )

    retuned_count = _retune_melody_notes(staff_element, tuning)

    # The new Part's own StringData was already populated
    # correctly with tuning.notes at creation time (see
    # _build_tab_part_element()) -- there is nothing else to
    # update here. Deliberately NOT walking the whole tree for
    # every <StringData> element: any pre-existing TAB elsewhere
    # in the score has its own StringData, and per the explicit
    # clarification that existing TAB must never be modified,
    # that must be left exactly as it was.
    string_data_count = 1

    chord_shapes_applied = 0

    chord_shapes_skipped = 0

    if chord_service is not None:

        # source_staff_number may differ from staff_number (see
        # _find_notation_staff_element()'s own docstring -- the
        # rare case where staff_number itself was accidentally a
        # TAB staff), so harmonies are re-read here specifically
        # for the correct source staff, via the EXISTING
        # read_harmonies() -- not re-derived by hand, which would
        # duplicate parser.py's own parsing. This runs on
        # score_file's ORIGINAL (unmodified) tree, purely for
        # reading; its own .harmonies/.score.harmonies are saved
        # and restored immediately after, so the caller's
        # already-parsed state is left exactly as it was,
        # matching this function's own "never mutate the
        # caller's state" rule above.
        saved_harmonies = score_file.harmonies

        saved_score_harmonies = score_file.score.harmonies

        score_file.read_harmonies(source_staff_number)

        staff_harmonies = list(score_file.harmonies)

        score_file.harmonies = saved_harmonies

        score_file.score.harmonies = saved_score_harmonies

        chord_shapes_applied, chord_shapes_skipped, _ = (
            _apply_chord_shapes(
                staff_element, staff_harmonies, tuning,
                chord_service
            )
        )

    if filename is None:

        title = score_file.score.title or "Untitled"

        filename = _sanitize_filename(
            f"{title} - {tuning.name}"
        ) + ".mscz"

    output_path = _save_score_copy(
        root_copy, score_file, output_folder, filename
    )

    return (
        output_path, retuned_count, string_data_count,
        chord_shapes_applied, chord_shapes_skipped
    )


def _save_score_copy(root_copy, score_file, output_folder, filename):
    """
    Write root_copy (an edited in-memory copy of score_file's
    own tree) to output_folder/filename as a new .mscz -- every
    other file in the original archive (styles, thumbnails,
    settings) is copied through unchanged; only the .mscx is
    replaced with the edited content.

    Returns the output Path.
    """

    output_path = Path(output_folder) / filename

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

    return output_path


# ---------------------------------------------------------
# Chord-diagrams-only generation -- BO-19 (Plan B)
# ---------------------------------------------------------
#
# A deliberately narrower alternative to generate_mscz(): does
# NOT create a TAB staff, does NOT touch melody notes/frets/
# strings/pitches, and never touches Measure/voice content at
# all -- only inserts/updates <FretDiagram> elements next to the
# EXISTING notation staff's own <Harmony> elements, reusing
# _apply_chord_shapes() completely unmodified (the same function
# generate_mscz() already uses). Because nothing about Measure
# structure, duration, or staff creation is touched, this avoids
# the entire class of problems generate_mscz()'s TAB-creation
# path has run into.
#
# Success criterion, explicitly: a valid MuseScore file
# containing useful, tuning-appropriate fretboard diagrams above
# the existing chord symbols -- not sophisticated automatic
# fingering, and not a TAB staff.

def _find_title_frame(staff_element):
    """
    The staff's own <VBox> (title/subtitle frame), if it has
    one -- always a direct child of the staff, before the first
    <Measure> (see _normalize_copied_content()'s own docstring
    for how this was confirmed). Returns None if the staff has
    no such frame.
    """

    for child in staff_element:

        if child.tag.split("}")[-1] == "VBox":

            return child

    return None


def _set_score_title_and_composer(
    score_el, staff_element, title, composer
):
    """
    BO-26: carry over the source score's own Title and
    Composer/arranger (from its Project Properties -- see
    parser.read_title()/read_composer()) into the generated TAB
    template, replacing the template's own placeholder values
    rather than leaving them in place.

    Updates BOTH the Project Properties metaTags (workTitle,
    composer) AND the score's own visible VBox title-frame text
    (confirmed directly against the real template: a <Text
    style="title"> and a <Text style="composer">, both direct
    children of its VBox) -- kept consistent with each other
    rather than updating only one, since a mismatch between the
    two would be confusing (Project Properties showing one title
    while the score itself displays another).

    composer: when empty (the source had no Composer/arranger
    value at all -- see read_composer()'s own default), the
    composer metaTag is cleared and the VBox's own composer
    <Text> element is removed entirely, rather than left showing
    the template's own literal placeholder text ("Composer /
    arranger") as if it were a real value. Never invents one.
    """

    work_title_tag = score_el.find(
        './/{*}metaTag[@name="workTitle"]'
    )

    if work_title_tag is not None and title:

        work_title_tag.text = title

    composer_tag = score_el.find(
        './/{*}metaTag[@name="composer"]'
    )

    if composer_tag is not None:

        composer_tag.text = composer if composer else None

    vbox = _find_title_frame(staff_element)

    if vbox is None:

        return

    for text_element in vbox.findall("{*}Text"):

        style_element = text_element.find("{*}style")

        style = (
            style_element.text if style_element is not None
            else None
        )

        if style == "title" and title:

            content_element = text_element.find("{*}text")

            font_element = content_element.find("{*}font")

            if font_element is not None:

                font_element.tail = title

            else:

                content_element.text = title

        elif style == "composer":

            if composer:

                content_element = text_element.find("{*}text")

                content_element.text = composer

            else:

                vbox.remove(text_element)


def _add_tuning_text(staff_element, tuning):
    """
    Add a clearly-labeled text line stating the actual tuning
    notation (tuning.symbol, e.g. "gDGBD") to the score's own
    title frame -- required so the tuning is visibly present in
    the score itself, not only inferable from the filename or a
    tuning NAME alone (a name like "G Modal Sawmill" doesn't by
    itself tell a player which strings go where).

    Appends a new <Text> to the staff's existing <VBox> if it
    has one, without touching anything already there; creates a
    minimal new VBox (matching the structure confirmed real
    scores actually use) if the staff has none. Set at 8pt
    (explicit <size> element, matching the exact position
    confirmed against a real MuseScore-authored <Text> element:
    eid, style, size, then text) -- smaller than the "subtitle"
    style's own 14pt default, so this line reads as a compact
    label rather than a second subtitle-sized heading.
    """

    vbox = _find_title_frame(staff_element)

    if vbox is None:

        vbox = ET.Element("VBox")

        height_element = ET.SubElement(vbox, "height")

        height_element.text = "4"

        eid_element = ET.SubElement(vbox, "eid")

        eid_element.text = _generate_eid()

        staff_element.insert(0, vbox)

    text_element = ET.SubElement(vbox, "Text")

    eid_element = ET.SubElement(text_element, "eid")

    eid_element.text = _generate_eid()

    style_element = ET.SubElement(text_element, "style")

    style_element.text = "subtitle"

    size_element = ET.SubElement(text_element, "size")

    size_element.text = "8"

    content_element = ET.SubElement(text_element, "text")

    content_element.text = (
        f"Banjo tuning: {tuning.symbol} ({tuning.name})"
    )


def generate_chord_diagrams_only(
    score_file, tuning, staff_number, output_folder,
    chord_service, filename=None
):
    """
    Plan B: add banjo chord shape diagrams for `tuning` above
    the existing chord symbols on the score's own notation
    staff, leaving everything else -- melody notes, frets,
    strings, pitches, lyrics, formatting, and any existing TAB
    staff -- completely untouched. Does not create a TAB staff.

    chord_service is REQUIRED here (unlike generate_mscz(),
    where it's optional) -- producing chord diagrams is this
    function's entire purpose.

    staff_number: the melody staff to use as the chord-symbol
    source -- pass the same value read_melody_notes() returned.
    Any existing TAB elsewhere in the score is ignored, exactly
    as generate_mscz() does (see _find_notation_staff_element()'s
    own docstring) -- this function only ever reads/writes the
    notation staff itself, never any TAB staff, existing or
    otherwise.

    filename: optional explicit output filename. Defaults to
    "{title} - {tuning.name} ({tuning.symbol}).mscz" -- the
    tuning's actual notation (symbol) is always included, not
    only its name, per the explicit requirement that the tuning
    must be visible in the score and/or filename, never only
    inferable from a name alone.

    Returns (output_path, chord_shapes_applied,
    chord_shapes_skipped, exceptions) -- exceptions is BO-21's
    list of dicts, one per chord whose FretDiagram was marked
    red for not being able to include the melody note occurring
    at its own onset (see _apply_chord_shapes()'s own docstring
    for exactly what each dict contains). Always an empty list
    for a chord symbol BO doesn't recognize the quality of, or
    when the source has no melody notes at all.
    """

    output_folder = Path(output_folder)

    output_folder.mkdir(exist_ok=True)

    tree_copy = copy.deepcopy(score_file.tree)

    root_copy = tree_copy.getroot()

    notation_staff_element, notation_staff_number = (
        _find_notation_staff_element(root_copy, staff_number)
    )

    if notation_staff_element is None:

        raise ValueError(
            "No notation (non-TAB) staff was found in this "
            "score -- nothing to add chord diagrams to."
        )

    # Read harmonies specifically for the resolved notation
    # staff (see generate_mscz()'s own docstring for why this
    # can differ from staff_number and must be re-read rather
    # than assumed) via the EXISTING read_harmonies(), saving
    # and restoring score_file's own state so this function
    # never mutates the caller's already-parsed data, matching
    # generate_mscz()'s own rule.
    saved_harmonies = score_file.harmonies

    saved_score_harmonies = score_file.score.harmonies

    score_file.read_harmonies(notation_staff_number)

    staff_harmonies = list(score_file.harmonies)

    score_file.harmonies = saved_harmonies

    score_file.score.harmonies = saved_score_harmonies

    # Same save/restore pattern as harmonies above, and for the
    # same reason: notation_staff_number can differ from
    # whatever staff the caller originally read melody notes
    # for (the rare case where read_melody_notes() itself landed
    # on a TAB staff -- see _find_notation_staff_element()'s own
    # docstring), so melody notes are re-read here specifically
    # for the correct staff via the EXISTING read_staff_notes()
    # -- not re-derived by hand -- with the caller's own
    # already-parsed state saved and restored around it (BO-20).
    saved_notes = score_file.notes

    saved_score_notes = score_file.score.notes

    score_file.read_staff_notes(notation_staff_number)

    staff_melody_notes = list(score_file.score.notes)

    score_file.notes = saved_notes

    score_file.score.notes = saved_score_notes

    chord_shapes_applied, chord_shapes_skipped, exceptions = (
        _apply_chord_shapes(
            notation_staff_element, staff_harmonies, tuning,
            chord_service, melody_notes=staff_melody_notes
        )
    )

    _add_tuning_text(notation_staff_element, tuning)

    if filename is None:

        title = score_file.score.title or "Untitled"

        filename = _sanitize_filename(
            f"{title} - {tuning.name} ({tuning.symbol})"
        ) + ".mscz"

    output_path = _save_score_copy(
        root_copy, score_file, output_folder, filename
    )

    return (
        output_path, chord_shapes_applied, chord_shapes_skipped,
        exceptions
    )


# ===========================================================
# BO-23 -- populate a MuseScore-created TAB template rather
# than constructing TAB staff XML from scratch. See the BO-23
# investigation notes: MuseScore's own linked-staff editing
# mechanism could not be reliably reconstructed by hand-writing
# linkedTo relationships offline (three independently-tested
# approaches all failed to produce genuine live-linked editing,
# confirmed against real MuseScore-created reference files).
# Current scope: BO writes correct, matching, static content to
# BOTH the TAB and treble content staves of the template -- the
# user edits the linked treble clef manually afterward in
# MuseScore when a TAB adjustment is needed, rather than relying
# on live propagation.
#
# This is a genuinely new, separate generation path -- it does
# not modify generate_mscz(), generate_chord_diagrams_only(),
# _apply_chord_shapes(), or anything else above.
# ===========================================================

def _extract_staff_events(score_file, staff_number):
    """
    Walk one content staff's Measures/voice in document order,
    returning a list of measures, each a list of event dicts:

        {"beat": float, "type": "note" or "rest",
         "duration_type": str, "dots": int,
         "pitch": int or None, "tpc": int or None,
         "lyrics_elements": list of raw <Lyrics> XML elements}

    Preserves the source's own exact rhythm notation
    (duration_type + dots) VERBATIM rather than re-deriving it
    from a raw beat-length number -- the source's own notation
    is already valid, so this only ever copies it, never
    reconstructs it. Reuses
    MuseScoreFile._duration_value() unmodified for beat
    tracking (the same mechanism read_staff_notes() already
    uses) -- only Chord/Rest/Note elements on the target staff
    are considered, matching that same established counting
    convention (every <Staff> tag encountered, both
    definitions and content, advances current_staff).

    lyrics_elements: a "note" event's own <Lyrics> children
    (confirmed real structure: <syllabic>/<eid>/<text>, direct
    children of <Chord>, one per verse/syllable at that note) --
    captured here for the caller to copy through verbatim
    (regenerating eids, matching every other copied-element
    pattern in this function), never re-derived or reworded.
    Always empty for a "rest" event.
    """

    measures = []

    current_measure_events = None

    current_staff = 0

    beat = 0.0

    tuplet_scale = 1.0

    pending_tuplet_element = None

    current_event = None

    for element in score_file.root.iter():

        tag = element.tag.split("}")[-1]

        if tag == "Staff":

            current_staff += 1

        if current_staff != staff_number:

            continue

        if tag == "Measure":

            if current_measure_events is not None:

                measures.append(current_measure_events)

            current_measure_events = []

            beat = 0.0

            tuplet_scale = 1.0

            pending_tuplet_element = None

        if tag == "Tuplet":

            normal_notes_element = element.find(
                "{*}normalNotes"
            )

            actual_notes_element = element.find(
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

                pending_tuplet_element = element

        if tag == "endTuplet":

            tuplet_scale = 1.0

            if current_event is not None:

                current_event["tuplet_end"] = True

        if tag in ("Chord", "Rest"):

            duration_type_element = element.find(
                "{*}durationType"
            )

            duration_type = (
                duration_type_element.text
                if duration_type_element is not None
                else "quarter"
            )

            dots_element = element.find("{*}dots")

            dots = (
                int(dots_element.text)
                if dots_element is not None else 0
            )

            lyrics_elements = (
                element.findall("{*}Lyrics")
                if tag == "Chord" else []
            )

            current_event = {
                "beat": round(beat, 4),
                "type": "note" if tag == "Chord" else "rest",
                "duration_type": duration_type,
                "dots": dots,
                "pitch": None,
                "tpc": None,
                "harmony_element": None,
                "tuplet_start_element": pending_tuplet_element,
                "tuplet_end": False,
                "lyrics_elements": lyrics_elements
            }

            current_measure_events.append(current_event)

            pending_tuplet_element = None

            beat += (
                score_file._duration_value(element)
                * tuplet_scale
            )

        if tag == "Harmony" and current_measure_events is not None:

            # A Harmony always precedes the Chord/Rest it
            # applies to in document order (confirmed by direct
            # inspection of the real source file) -- attach it
            # to the NEXT event about to be appended, by
            # stashing it until that event exists.
            pending_harmony = element

            current_measure_events.append({
                "beat": round(beat, 4),
                "type": "harmony",
                "duration_type": None,
                "dots": 0,
                "pitch": None,
                "tpc": None,
                "harmony_element": pending_harmony
            })

        if tag == "Note" and current_event is not None:

            pitch_element = element.find("{*}pitch")

            tpc_element = element.find("{*}tpc")

            if pitch_element is not None:

                current_event["pitch"] = int(
                    pitch_element.text
                )

            if tpc_element is not None:

                current_event["tpc"] = int(tpc_element.text)

    if current_measure_events is not None:

        measures.append(current_measure_events)

    return measures


def _save_template_copy(root, template_path, output_folder, filename):
    """
    Like _save_score_copy(), but sources every OTHER archive
    member (style, thumbnail, settings) from the TEMPLATE's own
    archive, not the input score's -- the output is fundamentally
    a populated copy of the template, not an edited copy of the
    source score, so its formatting/style should come from the
    template, matching BO-23's own confirmed validation (every
    non-.mscx member byte-identical to the template).
    """

    output_path = Path(output_folder) / filename

    new_mscx_bytes = ET.tostring(
        root, encoding="UTF-8", xml_declaration=True
    )

    with zipfile.ZipFile(template_path, "r") as template_zip:

        mscx_name = [
            name for name in template_zip.namelist()
            if name.endswith(".mscx")
        ][0]

        with zipfile.ZipFile(
            output_path, "w", zipfile.ZIP_DEFLATED
        ) as output_zip:

            for name in template_zip.namelist():

                if name == mscx_name:

                    output_zip.writestr(name, new_mscx_bytes)

                else:

                    output_zip.writestr(
                        name, template_zip.read(name)
                    )

    return output_path


MELODY_ANCHOR_DISTANCE_CAP = 5  # frets; matches
# playing_model.py's own CONTINUITY_MOVE_DAMPENING_START and
# chord_service.py's own POSITION_DISTANCE_CAP, reused for
# consistency rather than inventing a new number -- BO-24. Caps
# how much a melody position's distance from a nearby chord's
# working fret can influence the choice, so it can only ever
# break ties among find_positions()'s own candidates, never
# force an otherwise-unreasonable position.

STRING_ANCHOR_DISTANCE_CAP = 3  # strings -- BO-25. The domain
# itself is already small (fretboard string_index only ever
# spans 0-3, so 3 is already the maximum possible distance --
# this cap is written explicitly for the same reason every other
# distance measure in this project has one, not because it
# changes behavior here). String continuity is deliberately a
# TIEBREAK ONLY: see _choose_melody_position()'s own sort key --
# it is compared strictly after fret_distance in a lexicographic
# tuple, so it can only ever decide between candidates already
# tied on fret-position continuity, never override a fret-
# position difference of any size.


def _fd_positions_for_pitch(shape_values, open_notes, target_midi):
    """
    Every (fretboard string_index, fret) position within an
    already-selected chord shape (parse_shape() output) that
    sounds target_midi exactly -- BO-24. Reuses the shape's own
    values directly; no new position representation. Usually
    0 or 1 matches, but a shape can legitimately double the same
    pitch on more than one string.
    """

    matches = []

    for string_index, fret in enumerate(shape_values):

        if fret is None:

            continue

        if open_notes[string_index] + fret == target_midi:

            matches.append((string_index, fret))

    return matches


def _choose_melody_position(
    midi, open_notes, fd_shape_values=None, working_fret_anchor=None,
    following_working_fret_anchor=None, previous_position=None
):
    """
    BO-24/BO-25/BO-30: choose a string/fret position for one
    melody note, optionally anchored to a nearby chord's own
    already-selected shape (BO-24, and now BO-30's second,
    following-chord anchor), the immediately preceding melody
    note's own actually-chosen position (BO-25), or both -- reuses
    fretboard.find_positions()/best_position() unmodified as the
    actual candidate source/scorer; this only adds priority
    layers on top, matching every one of these investigations'
    own finding that no second, independent fretboard-position
    system was needed.

    fd_shape_values: parse_shape() output of the chord AT this
    exact melody note's own onset, if any. When the exact pitch
    is genuinely one of that shape's own positions, that position
    is STRONGLY preferred -- returned directly, without even
    consulting best_position() or any anchor below -- matching
    BO-24's own priority #1/#2 for a melody note occurring
    exactly at a chord. Neither string continuity nor the BO-30
    two-sided anchor below ever applies here; this is the
    absolute top of the priority order, unchanged by either (see
    the BO-25 investigation's own Example 2, and the BO-30
    investigation's own confirmation that a chord-onset note is
    untouched by this task -- an FD with only one valid position
    for a pitch leaves nothing for any tiebreak to act on).

    working_fret_anchor: a nearby PRECEDING chord's own
    playing_model._chord_working_fret() (reused unmodified) --
    BO-24, unchanged.

    following_working_fret_anchor: a nearby FOLLOWING chord's own
    working fret (BO-30) -- for a melody note that sits
    immediately between TWO chord onsets (both this and
    working_fret_anchor set), the two are combined as a capped
    MAX, not a sum or a "nearest wins": fret_distance = max(
    capped_distance_to_preceding, capped_distance_to_following).
    Confirmed against every real occurrence of this exact
    situation in The Christmas Song (5 total) that max is the
    only one of the three obvious combination rules (sum, max,
    nearest/min) that behaves correctly in every case: it lets a
    genuinely good transition point (close to BOTH anchors) win
    even over a candidate that's excellent for one side and poor
    for the other, which sum and min both fail to do (sum lets a
    bad side "average out" against a great one; min ignores the
    bad side entirely) -- neither represents an actual transition
    between two chord positions. When ONLY one of the two anchors
    is set (the ordinary, far more common case -- a note adjacent
    to just one nearby chord onset), the max collapses to that
    single distance, reproducing BO-24's own original single-
    anchor behavior exactly, unchanged.

    previous_position: the ACTUAL {"string":..., "fret":...}
    dict _choose_melody_position() itself returned for the
    immediately preceding melody note (BO-25) -- never a
    recomputed or assumed position; the caller is responsible
    for threading the real, sequential chain
    (note 1's result -> note 2's own previous_position -> ...).
    Its "string" is used as a CAPPED distance tiebreak (see
    STRING_ANCHOR_DISTANCE_CAP) -- applied strictly AFTER fret_
    distance (now the BO-30 two-sided fret_distance above, when
    both anchors apply) in a single lexicographic sort key, so it
    can only ever decide between candidates already tied on fret-
    position continuity. A fret-distance difference of any size,
    however small, is never overridden by string continuity --
    see this project's own BO-25 investigation notes (Examples
    3/4) for why an unconditional tie-only rule, rather than a
    "close enough" band, is the correct, minimal extension:
    introducing a separate closeness threshold would be exactly
    the kind of independent, arbitrary scoring parameter every
    one of these tasks explicitly avoids. Applies even when
    neither working_fret_anchor nor following_working_fret_anchor
    is set (fret_distance is then 0 for every candidate, so
    string continuity becomes the first real differentiator,
    ahead of best_position()'s own static score) -- BO-25's own
    Example 5 (no chord anchor nearby) is exactly this case,
    deliberately not special-cased.

    Returns None only when find_positions() itself finds nothing
    -- callers should treat that exactly as before any of these
    tasks (no playable position exists for this pitch in this
    tuning). Falls back to plain best_position(find_positions(
    ...)), completely unchanged, when no anchor of any kind
    applies at all (e.g. the very first melody note in a piece)
    -- every existing melody position choice this project already
    makes for a note with nothing nearby to anchor to is
    untouched.
    """

    positions = find_positions(midi, open_notes)

    if not positions:

        return None

    if fd_shape_values is not None:

        fd_matches = _fd_positions_for_pitch(
            fd_shape_values, open_notes, midi
        )

        if fd_matches:

            string_index, fret = fd_matches[0]

            return {"string": string_index, "fret": fret}

    # best_position() also populates each position's own
    # ["score"] as a side effect -- reused directly below rather
    # than recomputed.
    default_choice = best_position(positions)

    if (
        working_fret_anchor is None
        and following_working_fret_anchor is None
        and previous_position is None
    ):

        return default_choice

    previous_string = (
        previous_position["string"]
        if previous_position is not None else None
    )

    def _sort_key(position):

        # BO-30: when both a preceding and a following anchor
        # apply, use the capped MAX of the two distances -- see
        # this function's own docstring for why (confirmed
        # against every real occurrence of this situation).
        # When only one anchor is set (the ordinary case), this
        # collapses to exactly that single distance, unchanged.
        distances = []

        if working_fret_anchor is not None:

            distances.append(
                min(
                    abs(position["fret"] - working_fret_anchor),
                    MELODY_ANCHOR_DISTANCE_CAP
                )
            )

        if following_working_fret_anchor is not None:

            distances.append(
                min(
                    abs(
                        position["fret"]
                        - following_working_fret_anchor
                    ),
                    MELODY_ANCHOR_DISTANCE_CAP
                )
            )

        fret_distance = max(distances) if distances else 0

        if previous_string is not None:

            string_distance = min(
                abs(position["string"] - previous_string),
                STRING_ANCHOR_DISTANCE_CAP
            )

        else:

            string_distance = 0

        return (fret_distance, string_distance, -position["score"])

    return sorted(positions, key=_sort_key)[0]


def generate_tab_from_template(
    score_file, tuning, staff_number, template_path,
    output_folder, chord_service, filename=None
):
    """
    BO-23: populate a MuseScore-created TAB template (see this
    module's own BO-23 section notes above) with the source
    score's melody and chord symbols, rather than constructing
    TAB staff XML from scratch.

    Output is TAB-ONLY -- the template's own linked treble staff
    (Staff-definition and content) is removed entirely before
    saving. This matches the settled design: BO does not attempt
    or rely on genuine live-linked editing (three independently-
    tested approaches at reconstructing that were unsuccessful --
    see BO-23's own investigation notes); the user adds a linked
    treble staff manually via MuseScore's own "Add Linked Staff"
    feature afterward, only if/when they actually want one.

    Chord symbols (Harmony) and FretDiagrams both go directly on
    the TAB staff, since it's the only staff in the output.
    FretDiagram generation reuses _apply_chord_shapes()
    UNMODIFIED -- the same melody-aware, position-aware, BO-18
    through BO-22 chord-shape selection already used by
    generate_chord_diagrams_only(), not a separate or simplified
    version of it.

    Uses fretboard.find_positions()/best_position() (unmodified)
    for each melody note's own TAB fret/string choice -- not
    attempting perfect placement, matching this whole
    investigation's own established scope. String numbering
    follows the confirmed-reversed MuseScore convention
    (3 - fretboard string_index).

    score_file: an opened MuseScoreFile with read_time_signature()
        and read_melody_notes() (or an equivalent staff_number)
        already called.
    staff_number: the notation staff to read melody/harmonies
        from (this project's own "every <Staff> tag" counting
        convention -- the same value read_melody_notes() itself
        returns).
    template_path: path to the TAB-linked-treble .mscz template.
    chord_service: a ChordService instance, passed straight
        through to _apply_chord_shapes().

    Returns (output_path, chord_shapes_applied,
    chord_shapes_skipped, exceptions) -- exceptions is BO-21's
    list of melody/chord exceptions, exactly as
    generate_chord_diagrams_only() already returns it.
    """

    measures = _extract_staff_events(score_file, staff_number)

    # ---- BO-24: read harmonies and pre-select each chord's own
    # shape BEFORE writing any melody note's fret/string, so
    # those choices can be anchored to the shapes BO-20/21/22
    # will actually select -- reuses _select_chord_shape_for_
    # harmony() (the exact same selection _apply_chord_shapes()
    # itself uses below, factored out for this reason) as a
    # read-only query; nothing is written to the output yet.

    saved_harmonies = score_file.harmonies

    saved_score_harmonies = score_file.score.harmonies

    score_file.read_harmonies(staff_number)

    staff_harmonies = list(score_file.harmonies)

    score_file.harmonies = saved_harmonies

    score_file.score.harmonies = saved_score_harmonies

    chord_shape_by_position = {}

    for harmony in staff_harmonies:

        chosen_shape, _, _ = _select_chord_shape_for_harmony(
            harmony, tuning, chord_service,
            melody_notes=score_file.score.notes
        )

        if chosen_shape is not None:

            chord_shape_by_position[
                (harmony.measure, harmony.beat)
            ] = parse_shape(chosen_shape.shape)

    # A flat, document-ordered list of every melody note event
    # (across all measures) so "the note immediately before/
    # after this one" is a simple, local lookup -- no separate
    # position-tracking system, just this project's own existing
    # event list read a second way.
    flat_note_events = [
        (measure_index + 1, event)
        for measure_index, measure_events in enumerate(measures)
        for event in measure_events
        if event["type"] == "note"
    ]

    # For each note event, precompute its own FD anchor (when
    # it's exactly at a chord's onset) and/or a nearby chord's
    # working fret (when the immediately adjacent note event is
    # at a chord's onset) -- keyed by object identity, since
    # these are the exact same event dicts referenced in
    # `measures` below.
    fd_anchor_by_event_id = {}

    # BO-30: preceding and following are now tracked separately
    # and independently (neither check stops the other), so a
    # note sandwiched between two chord onsets can pick up BOTH
    # anchors; a note adjacent to only one chord onset gets
    # exactly that one -- identical to BO-24's own original
    # single-anchor behavior, since only one of these two dicts
    # ever gets an entry for it.
    preceding_working_fret_anchor_by_event_id = {}

    following_working_fret_anchor_by_event_id = {}

    for index, (measure_number, event) in enumerate(
        flat_note_events
    ):

        position_key = (measure_number, event["beat"])

        if position_key in chord_shape_by_position:

            fd_anchor_by_event_id[id(event)] = (
                chord_shape_by_position[position_key]
            )

            continue

        if index - 1 >= 0:

            prev_measure, prev_event = flat_note_events[
                index - 1
            ]

            prev_key = (prev_measure, prev_event["beat"])

            if prev_key in chord_shape_by_position:

                preceding_working_fret_anchor_by_event_id[
                    id(event)
                ] = _chord_working_fret(
                    chord_shape_by_position[prev_key]
                )

        if index + 1 < len(flat_note_events):

            next_measure, next_event = flat_note_events[
                index + 1
            ]

            next_key = (next_measure, next_event["beat"])

            if next_key in chord_shape_by_position:

                following_working_fret_anchor_by_event_id[
                    id(event)
                ] = _chord_working_fret(
                    chord_shape_by_position[next_key]
                )

    with zipfile.ZipFile(template_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith(".mscx")
        ][0]

        xml_bytes = z.read(mscx_name)

    root = ET.fromstring(xml_bytes)

    score_el = root.find(".//{*}Score")

    # ---- Set StringData to the target tuning ----

    instrument_el = score_el.find(".//{*}Instrument")

    string_data_el = instrument_el.find("{*}StringData")

    string_els = string_data_el.findall("{*}string")

    for string_el, midi in zip(string_els, tuning.notes):

        string_el.text = str(midi)

    # ---- Remove the template's linked treble staff entirely --
    # TAB-only output (see this function's own docstring for
    # why: no genuine live-link is being attempted or relied on,
    # so there's no reason to carry a staff BO itself never
    # populates with anything meaningful).

    part_el = root.find(".//{*}Part")

    staff_defs = part_el.findall("{*}Staff")

    treble_staff_def = staff_defs[1]

    part_el.remove(treble_staff_def)

    for clef_el in list(instrument_el.findall("{*}clef")):

        if clef_el.attrib.get("staff") == "2":

            instrument_el.remove(clef_el)

    staves = [
        c for c in score_el if c.tag.split("}")[-1] == "Staff"
    ]

    tab_staff = next(
        s for s in staves if s.attrib.get("id") == "1"
    )

    treble_staff = next(
        s for s in staves if s.attrib.get("id") == "2"
    )

    score_el.remove(treble_staff)

    # ---- BO-26: carry over the source's own Title and
    # Composer/arranger, replacing the template's own
    # placeholder values (both the Project Properties metaTags
    # and the TAB staff's own visible VBox title-frame text, so
    # the two stay consistent with each other) ----

    _set_score_title_and_composer(
        score_el, tab_staff, score_file.score.title,
        score_file.score.composer
    )

    _add_tuning_text(tab_staff, tuning)

    # ---- Rebuild the TAB staff's Measures from the source's
    # own events ----

    for old_measure in tab_staff.findall("{*}Measure"):

        tab_staff.remove(old_measure)

    open_notes = tuning.notes[1:]  # 4th to 1st

    sig_parts = score_file.score.time_signature.split("/")

    sig_n, sig_d = sig_parts[0], sig_parts[1]

    # BO-25: threaded across the whole loop below (not reset per
    # measure) -- always the actual position _choose_melody_
    # position() itself returned for the immediately preceding
    # melody note, never a recomputed or assumed one.
    previous_melody_position = None

    for measure_index, measure_events in enumerate(measures):

        is_first_measure = (measure_index == 0)

        tab_measure = ET.SubElement(tab_staff, "Measure")

        if is_first_measure:

            ET.SubElement(
                tab_measure, "eid"
            ).text = _generate_eid()

        tab_voice = ET.SubElement(tab_measure, "voice")

        if is_first_measure:

            tab_keysig = ET.SubElement(tab_voice, "KeySig")

            ET.SubElement(
                tab_keysig, "eid"
            ).text = _generate_eid()

            ET.SubElement(tab_keysig, "concertKey").text = "0"

            tab_timesig = ET.SubElement(tab_voice, "TimeSig")

            ET.SubElement(
                tab_timesig, "eid"
            ).text = _generate_eid()

            ET.SubElement(tab_timesig, "sigN").text = sig_n

            ET.SubElement(tab_timesig, "sigD").text = sig_d

        for event in measure_events:

            if event["type"] == "harmony":

                # Only staff left, so chord symbols go directly
                # on it.
                harmony_copy = copy.deepcopy(
                    event["harmony_element"]
                )

                eid_el = harmony_copy.find("{*}eid")

                if eid_el is not None:

                    eid_el.text = _generate_eid()

                tab_voice.append(harmony_copy)

                continue

            if event["type"] == "rest":

                if event["tuplet_start_element"] is not None:

                    tuplet_copy = copy.deepcopy(
                        event["tuplet_start_element"]
                    )

                    eid_el = tuplet_copy.find("{*}eid")

                    if eid_el is not None:

                        eid_el.text = _generate_eid()

                    tab_voice.append(tuplet_copy)

                tab_rest = ET.SubElement(tab_voice, "Rest")

                ET.SubElement(
                    tab_rest, "eid"
                ).text = _generate_eid()

                if event["dots"]:

                    ET.SubElement(
                        tab_rest, "dots"
                    ).text = str(event["dots"])

                ET.SubElement(
                    tab_rest, "durationType"
                ).text = event["duration_type"]

                if event["tuplet_end"]:

                    ET.SubElement(tab_voice, "endTuplet")

                continue

            # event["type"] == "note"

            midi = event["pitch"]

            tpc = event["tpc"]

            # BO-24: anchor this note's position to a nearby
            # chord's own already-selected shape when one
            # applies -- see the pre-computed lookups built
            # earlier in this function, before this loop, from
            # the exact same shape selection _apply_chord_
            # shapes() itself uses below.
            # BO-30: when a note sits immediately between TWO
            # chord onsets, both anchors are passed -- see
            # _choose_melody_position()'s own docstring for how
            # they combine (capped max, not sum or nearest-wins).
            # A note adjacent to only one chord onset gets only
            # that one, identical to BO-24's own original single-
            # anchor behavior.
            # BO-25: also anchor to the ACTUAL position chosen
            # for the immediately preceding melody note (never
            # recomputed) as a string-continuity tiebreak. Falls
            # back to plain, unmodified best_position(find_
            # positions(...)) for the very first melody note in
            # the piece, when no anchor of either kind applies.
            chosen = _choose_melody_position(
                midi, open_notes,
                fd_shape_values=fd_anchor_by_event_id.get(
                    id(event)
                ),
                working_fret_anchor=(
                    preceding_working_fret_anchor_by_event_id.get(
                        id(event)
                    )
                ),
                following_working_fret_anchor=(
                    following_working_fret_anchor_by_event_id.get(
                        id(event)
                    )
                ),
                previous_position=previous_melody_position
            )

            previous_melody_position = chosen

            chosen_fret = chosen["fret"]

            # Confirmed-reversed MuseScore <string> numbering
            # relative to fretboard.py's own string_index (see
            # BO-23-FOLLOWUP's own investigation notes).
            chosen_string = 3 - chosen["string"]

            if event["tuplet_start_element"] is not None:

                tuplet_copy = copy.deepcopy(
                    event["tuplet_start_element"]
                )

                eid_el = tuplet_copy.find("{*}eid")

                if eid_el is not None:

                    eid_el.text = _generate_eid()

                tab_voice.append(tuplet_copy)

            tab_chord = ET.SubElement(tab_voice, "Chord")

            ET.SubElement(
                tab_chord, "eid"
            ).text = _generate_eid()

            if event["dots"]:

                ET.SubElement(
                    tab_chord, "dots"
                ).text = str(event["dots"])

            ET.SubElement(
                tab_chord, "durationType"
            ).text = event["duration_type"]

            for lyrics_element in event["lyrics_elements"]:

                lyrics_copy = copy.deepcopy(lyrics_element)

                eid_el = lyrics_copy.find("{*}eid")

                if eid_el is not None:

                    eid_el.text = _generate_eid()

                tab_chord.append(lyrics_copy)

            tab_note = ET.SubElement(tab_chord, "Note")

            ET.SubElement(
                tab_note, "eid"
            ).text = _generate_eid()

            ET.SubElement(tab_note, "pitch").text = str(midi)

            ET.SubElement(tab_note, "tpc").text = str(tpc)

            ET.SubElement(
                tab_note, "fret"
            ).text = str(chosen_fret)

            ET.SubElement(
                tab_note, "string"
            ).text = str(chosen_string)

            if event["tuplet_end"]:

                ET.SubElement(tab_voice, "endTuplet")

    # ---- FretDiagrams: reuse the existing, unmodified BO-18
    # through BO-22 chord-shape selection (staff_harmonies was
    # already read earlier in this function, before the melody-
    # writing loop, so BO-24's own anchoring could use it too --
    # not re-read a second time here) ----

    chord_shapes_applied, chord_shapes_skipped, exceptions = (
        _apply_chord_shapes(
            tab_staff, staff_harmonies, tuning, chord_service,
            melody_notes=score_file.score.notes
        )
    )

    if filename is None:

        title = score_file.score.title or "Untitled"

        filename = _sanitize_filename(
            f"{title} - {tuning.name} ({tuning.symbol}) - TAB"
        ) + ".mscz"

    output_path = _save_template_copy(
        root, template_path, output_folder, filename
    )

    return (
        output_path, chord_shapes_applied, chord_shapes_skipped,
        exceptions
    )


