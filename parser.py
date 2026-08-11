from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from models import Score, Note, Harmony

from music import tpc_to_name, tpc_to_pitch_class, chord_tones, chord_display_symbol


# ---------------------------------------------------------
# Beat/duration tracking
# ---------------------------------------------------------
#
# Quarter-note-beat value for each MuseScore durationType
# string. Used to accumulate a running beat position through
# a voice (see MuseScoreFile._duration_value below) -- e.g.
# an eighth note is half a quarter-note beat.
#
# "measure" (a whole-bar rest) isn't a fixed value -- it
# depends on the actual time signature -- so it's handled
# separately in _duration_value rather than listed here.

DURATIONS = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "16th": 0.25,
    "32nd": 0.125,
    "64th": 0.0625,
}


class MuseScoreFile:
    """
    Reads a MuseScore .mscz file and extracts musical information.
    """

    def __init__(self, filename):

        self.filename = Path(filename)

        self.tree = None
        self.root = None

        self.title = "Unknown Title"

        self.time_signature = "Unknown"

        self.notes = []

        self.score = Score()

        self.key_signature = None
        self.key = "Unknown"
        self.key_confidence = 0



    # -----------------------------------------------------

    def open(self):

        # print(f"\nOpening {self.filename.name}")


        with zipfile.ZipFile(
            self.filename,
            "r"
        ) as archive:


            score_filename = None


            for name in archive.namelist():

                if name.endswith(".mscx"):

                    score_filename = name
                    break


            if score_filename is None:

                raise Exception(
                    "No MSCX file found."
                )


            # print(
                # "Reading",
                # score_filename
            # )


            xml_text = archive.read(
                score_filename
            )


            self.tree = ET.ElementTree(
                ET.fromstring(xml_text)
            )


            self.root = self.tree.getroot()


            # print(
                # "XML successfully loaded."
            # )



    # -----------------------------------------------------

    def read_title(self):

        # print(
            # "\nSearching for title..."
        # )


        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "metaTag":

                name = element.attrib.get(
                    "name",
                    ""
                )


                if name in (
                    "title",
                    "workTitle"
                ):

                    if element.text:

                        self.title = (
                            element.text.strip()
                        )


                        # print(
                            # "Title found:",
                            # self.title
                        # )


                        self.score.title = self.title

                        return



    # -----------------------------------------------------

    def read_time_signature(self):

        # print(
            # "\nSearching for time signature..."
        # )


        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "TimeSig":

                values = {}


                for child in element:

                    child_tag = (
                        child.tag.split("}")[-1]
                    )

                    values[child_tag] = child.text


                if (
                    "sigN" in values
                    and
                    "sigD" in values
                ):

                    self.time_signature = (
                        f"{values['sigN']}/"
                        f"{values['sigD']}"
                    )


                    # print(
                        # "Time signature found:",
                        # self.time_signature
                    # )


                    self.score.time_signature = (
                        self.time_signature
                    )

                    return



    # -----------------------------------------------------

    def _duration_value(self, element):
        """
        Duration of one Chord or Rest element, in quarter-note
        beats (e.g. an eighth note is 0.5), from its
        durationType + dots.

        A whole-bar rest (durationType "measure") is computed
        from the actual time signature rather than a fixed
        value, so it's correct for whatever meter the score is
        in. Falls back to assuming 4/4 if read_time_signature()
        hasn't been called yet (self.time_signature is still
        "Unknown") -- an honest fallback, not a silent wrong
        answer for scores actually in a different meter, so
        callers should call read_time_signature() first when
        precision matters.

        Does not account for tuplets -- none have been seen in
        any file this project has parsed yet (confirmed by
        inspection of My Favorite Things). A tuplet would cause
        beat positions to drift after it rather than being
        exactly correct; a known, documented limitation, not a
        full solution.

        Returns 0.0 if durationType is missing or unrecognized.
        """

        duration_type_element = element.find(
            "{*}durationType"
        )

        if duration_type_element is None:

            return 0.0

        duration_type = duration_type_element.text

        if duration_type == "measure":

            try:

                numerator, denominator = (
                    self.time_signature.split("/")
                )

                base = int(numerator) * (
                    4 / int(denominator)
                )

            except (ValueError, AttributeError):

                base = 4.0

        else:

            base = DURATIONS.get(duration_type, 0.0)


        dots_element = element.find("{*}dots")

        if dots_element is not None:

            dot_count = int(dots_element.text)

            multiplier = 1.0

            addition = 0.5

            for _ in range(dot_count):

                multiplier += addition

                addition /= 2

            base *= multiplier


        return base



    # -----------------------------------------------------

    def read_staff_notes(self, staff_number):

        # print(
            # f"\nReading notes from Staff {staff_number}..."
        # )


        self.notes = []

        self.score.notes = []

        current_staff = 0

        measure = 0

        beat = 0.0

        current_chord_beat = 0.0


        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "Staff":

                current_staff += 1


            if current_staff != staff_number:

                continue


            if tag == "Measure":

                measure += 1

                beat = 0.0


            if tag == "Chord":

                current_chord_beat = round(beat, 4)

                beat += self._duration_value(element)


            if tag == "Rest":

                beat += self._duration_value(element)


            if tag == "Note":

                pitch = None


                for child in element:

                    child_tag = (
                        child.tag.split("}")[-1]
                    )


                    if child_tag == "pitch":

                        pitch = int(
                            child.text
                        )


                if pitch is not None:


                    # Old format
                    # kept for optimizer compatibility

                    self.notes.append(
                        {
                            "measure": measure,
                            "midi": pitch
                        }
                    )


                    # New v2 format

                    self.score.add_note(
                        Note(
                            midi=pitch,
                            measure=measure,
                            beat=current_chord_beat
                        )
                    )


        # print(
            # "Notes found:",
            # len(self.notes)
        # )



    # -----------------------------------------------------

    def read_melody_notes(self):
        """
        Finds and reads the melody staff automatically,
        instead of assuming any particular staff number.

        Tries staves in order (1, 2, 3, ...), using the same
        <Staff>-tag counting convention as read_staff_notes
        (which also counts staff *definitions* nested inside
        <Part>, not just staves with actual content -- see
        read_staff_notes' docstring). The first staff that
        turns out to contain notes is used.

        This is a "first staff with notes" heuristic. It's
        not guaranteed to find the true melody staff if a
        score has some other staff with notes appearing
        first (e.g. a countoff or percussion staff) -- but
        it's a much safer default than a hardcoded staff
        number, and it matches how these files are actually
        structured today.

        Returns the staff number that was used, and raises
        ValueError if no staff in the file contains any
        notes at all.
        """

        staff_count = sum(
            1
            for element in self.root.iter()
            if element.tag.split("}")[-1] == "Staff"
        )

        for staff_number in range(1, staff_count + 1):

            self.read_staff_notes(staff_number)

            if self.notes:

                return staff_number


        raise ValueError(
            "No staff containing notes was found in this file."
        )



    # -----------------------------------------------------

    def read_harmonies(self, staff_number):
        """
        Reads chord symbols (Harmony elements) from the score,
        in the order they appear.

        Uses the same staff-counting convention as
        read_staff_notes: every <Staff> tag increments the
        counter, including the staff *definitions* nested
        inside <Part>, not just the staves that hold musical
        content. Pass the same staff_number you used for
        read_staff_notes.

        Note: this records each chord symbol's exact beat
        position within the measure (accumulated from note/
        rest durations, same mechanism as read_staff_notes) --
        see Harmony.beat in models.py. Doesn't account for
        tuplets (see MuseScoreFile._duration_value).

        Also captures each Harmony's paired <FretDiagram>, when
        the score has one -- see Harmony.shape in models.py.
        Most chord symbols in a typical score won't have a
        FretDiagram attached at all; that's normal, not an
        error, and shape just stays "" for those.
        """

        self.harmonies = []

        self.score.harmonies = []

        current_staff = 0

        measure = 0

        beat = 0.0

        # A Harmony and its FretDiagram are usually adjacent in
        # document order, but not always in a fixed direction --
        # real data confirms at least one case where FretDiagram
        # comes FIRST. These two track whichever one is "waiting"
        # to be paired with the other, in either order.
        current_harmony = None

        pending_shape = None


        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "Staff":

                current_staff += 1


            if current_staff != staff_number:

                continue


            if tag == "Measure":

                measure += 1

                beat = 0.0


            if tag == "Chord":

                beat += self._duration_value(element)


            if tag == "Rest":

                beat += self._duration_value(element)


            if tag == "Harmony":

                info = None

                for child in element:

                    if child.tag.split("}")[-1] == "harmonyInfo":

                        info = child
                        break


                if info is None:

                    continue


                root_tpc = None
                quality_code = ""

                for child in info:

                    child_tag = child.tag.split("}")[-1]

                    if child_tag == "root":

                        root_tpc = int(child.text)

                    elif child_tag == "name":

                        quality_code = child.text or ""


                if root_tpc is None:

                    continue


                root_name = tpc_to_name(root_tpc)
                root_pc = tpc_to_pitch_class(root_tpc)

                symbol = chord_display_symbol(
                    root_name,
                    quality_code
                )

                tones = chord_tones(
                    root_pc,
                    quality_code
                )

                harmony = Harmony(
                    measure=measure,
                    root_pc=root_pc,
                    quality_code=quality_code,
                    symbol=symbol,
                    tones=tones if tones else [],
                    beat=round(beat, 4)
                )

                self.harmonies.append(harmony)

                self.score.add_harmony(harmony)

                if pending_shape:

                    harmony.shape = pending_shape

                    pending_shape = None

                else:

                    current_harmony = harmony


            if tag == "FretDiagram":

                shape = self._decode_fret_diagram(element)

                if current_harmony is not None:

                    if shape:

                        current_harmony.shape = shape

                    # Only ever attach to the harmony it's
                    # paired with once -- don't let a later,
                    # unrelated FretDiagram silently overwrite
                    # an already-assigned shape.
                    current_harmony = None

                elif shape:

                    # FretDiagram appeared before its Harmony
                    # (confirmed real case) -- hold it for the
                    # next Harmony to claim.
                    pending_shape = shape


        # print(
            # "Chord symbols found:",
            # len(self.harmonies)
        # )



    # -----------------------------------------------------

    def _decode_fret_diagram(self, element):
        """
        Decode one <FretDiagram> element into this project's
        standard shape-string format ("0220", etc.) -- one
        character per string, "0" for open, a digit for a
        fretted position.

        Only handles what's actually been observed in real
        MuseScore data so far: a "circle" marker (open string)
        or a <dot fret="N"> (fretted, single digit). If some
        other marker type is ever encountered (e.g. an "X" for
        a string the player deliberately doesn't play at all --
        not observed in any file this project has read yet),
        that string is left as "?" rather than guessed at, and
        the overall shape is treated as unavailable (returns
        "") rather than silently producing a wrong shape.

        Returns "" if the diagram doesn't have exactly 4
        strings (this project's convention throughout is 4
        melody strings, 5th/drone string not included), or if
        any string couldn't be decoded.
        """

        by_string = {}

        for string_el in element.iter():

            if string_el.tag.split("}")[-1] != "string":

                continue

            string_no = string_el.attrib.get("no")

            if string_no is None:

                continue

            value = None

            for child in string_el:

                child_tag = child.tag.split("}")[-1]

                if child_tag == "dot":

                    value = child.attrib.get("fret")

                elif child_tag == "marker" and child.text == "circle":

                    value = "0"

            if value is not None:

                by_string[int(string_no)] = value


        if len(by_string) != 4:

            return ""

        if any(len(value) != 1 for value in by_string.values()):

            # A 2-digit fret (10+) doesn't fit this project's
            # one-character-per-string shape format. Not seen
            # in any real data yet -- bail out rather than
            # silently produce a malformed shape string.
            return ""

        try:

            return "".join(
                by_string[i] for i in range(4)
            )

        except KeyError:

            return ""



    # -----------------------------------------------------

    def read_key_signature(self):

        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "KeySig":

                for child in element:

                    child_tag = (
                        child.tag.split("}")[-1]
                    )


                    if child_tag == "concertKey":

                        self.key_signature = int(
                            child.text.strip()
                        )

                        return



    # -----------------------------------------------------

    def estimate_key(self):

        # print(
            # "\nEstimating key..."
        # )


        self.read_key_signature()


        if self.key_signature is None:

            print(
                "No key signature found."
            )

            return



        major_keys = {

            -7: ("Cb major", 11),
            -6: ("Gb major", 6),
            -5: ("Db major", 1),
            -4: ("Ab major", 8),
            -3: ("Eb major", 3),
            -2: ("Bb major", 10),
            -1: ("F major", 5),
             0: ("C major", 0),
             1: ("G major", 7),
             2: ("D major", 2),
             3: ("A major", 9),
             4: ("E major", 4),
             5: ("B major", 11),
             6: ("F# major", 6),
             7: ("C# major", 1)

        }


        minor_keys = {

            -7: ("Ab minor", 8),
            -6: ("Eb minor", 3),
            -5: ("Bb minor", 10),
            -4: ("F minor", 5),
            -3: ("C minor", 0),
            -2: ("G minor", 7),
            -1: ("D minor", 2),
             0: ("A minor", 9),
             1: ("E minor", 4),
             2: ("B minor", 11),
             3: ("F# minor", 6),
             4: ("C# minor", 1),
             5: ("G# minor", 8),
             6: ("D# minor", 3),
             7: ("A# minor", 10)

        }


        major_name, major_root = major_keys[
            self.key_signature
        ]

        minor_name, minor_root = minor_keys[
            self.key_signature
        ]


        # print(
            # "Possible keys:",
            # [
                # major_name,
                # minor_name
            # ]
        # )


        if not self.notes:

            self.key = major_name

            return


        pitches = [

            note["midi"] % 12

            for note in self.notes

        ]



        def score_key(root):

            score = 0


            for index, pitch in enumerate(pitches):

                weight = 1


                if index < 5:

                    weight += 2


                if index >= len(pitches)-5:

                    weight += 2


                if pitch == root:

                    score += (
                        5 * weight
                    )


                else:

                    score += 1


            return score



        major_score = score_key(
            major_root
        )

        minor_score = score_key(
            minor_root
        )


        # print(
            # "Major score:",
            # major_score
        # )

        # print(
            # "Minor score:",
            # minor_score
        # )



        if minor_score > major_score:

            self.key = minor_name

        else:

            self.key = major_name



        total = (
            major_score +
            minor_score
        )


        if total:

            if self.key == minor_name:

                self.key_confidence = round(
                    minor_score / total * 100,
                    1
                )

            else:

                self.key_confidence = round(
                    major_score / total * 100,
                    1
                )



        self.score.key = self.key

        self.score.key_confidence = (
            self.key_confidence
        )


        print(
            "Estimated key:",
            self.key
        )


        # print(
            # "Confidence:",
            # self.key_confidence,
            # "%"
        # )