from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from models import Score, Note


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

        print(f"\nOpening {self.filename.name}")


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


            print(
                "Reading",
                score_filename
            )


            xml_text = archive.read(
                score_filename
            )


            self.tree = ET.ElementTree(
                ET.fromstring(xml_text)
            )


            self.root = self.tree.getroot()


            print(
                "XML successfully loaded."
            )



    # -----------------------------------------------------

    def read_title(self):

        print(
            "\nSearching for title..."
        )


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


                        print(
                            "Title found:",
                            self.title
                        )


                        self.score.title = self.title

                        return



    # -----------------------------------------------------

    def read_time_signature(self):

        print(
            "\nSearching for time signature..."
        )


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


                    print(
                        "Time signature found:",
                        self.time_signature
                    )


                    self.score.time_signature = (
                        self.time_signature
                    )

                    return



    # -----------------------------------------------------

    def read_staff_notes(self, staff_number):

        print(
            f"\nReading notes from Staff {staff_number}..."
        )


        self.notes = []

        self.score.notes = []

        current_staff = 0

        measure = 0


        for element in self.root.iter():

            tag = element.tag.split("}")[-1]


            if tag == "Staff":

                current_staff += 1


            if current_staff != staff_number:

                continue


            if tag == "Measure":

                measure += 1


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
                            measure=measure
                        )
                    )


        print(
            "Notes found:",
            len(self.notes)
        )



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

        print(
            "\nEstimating key..."
        )


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


        print(
            "Possible keys:",
            [
                major_name,
                minor_name
            ]
        )


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


        print(
            "Major score:",
            major_score
        )

        print(
            "Minor score:",
            minor_score
        )



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


        print(
            "Confidence:",
            self.key_confidence,
            "%"
        )