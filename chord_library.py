"""
chord_library.py

Loads chord shape data from CSV files in the chord_library
directory, and provides lookup by tuning/root/quality.

This module is responsible only for loading and lookup. It
does not connect to scoring, recommendations, or the
optimizer -- see ChordShape in models.py for what a loaded
row looks like.

CSV columns expected (matching the real chord library files):
    Tuning, Root, Quality, Shape, Comfort Code,
    Comfort Code Explanation, Comments, Verified

Rows with an empty Shape are placeholders for chord shapes
that haven't been worked out yet (the real library files are
mostly placeholder rows right now, one per root/quality
combination, waiting to be filled in). Those rows are skipped
on load rather than turned into ChordShapes with no actual
shape -- find() should only ever return usable results.
"""

import csv

from pathlib import Path

from models import ChordShape


# CSV files are loaded relative to this module's own location,
# not the current working directory, so load() works the same
# regardless of where the program is run from.
CHORD_LIBRARY_DIR = Path(__file__).parent / "chord_library"


class ChordLibrary:
    """
    A collection of ChordShapes loaded from one or more CSV
    files, with lookup by tuning/root/quality.
    """

    def __init__(self):

        self.shapes = []

        self.loaded_files = []


    def load(self, filename):
        """
        Load chord shapes from a CSV file in the
        chord_library directory, adding them to this
        library. Can be called more than once to load
        multiple files into the same library.
        """

        path = CHORD_LIBRARY_DIR / filename

        with open(path, encoding="utf-8-sig", newline="") as f:

            reader = csv.DictReader(f)

            for row in reader:

                shape_text = (row.get("Shape") or "").strip()

                if not shape_text:

                    # Placeholder row -- no shape worked out
                    # yet, nothing to load.
                    continue


                comfort_raw = (
                    row.get("Comfort Code") or ""
                ).strip()

                comfort_code = (
                    int(comfort_raw)
                    if comfort_raw
                    else None
                )


                verified_raw = (
                    row.get("Verified") or ""
                ).strip().lower()

                if verified_raw == "yes":
                    verified = True
                elif verified_raw == "no":
                    verified = False
                else:
                    verified = None


                self.shapes.append(
                    ChordShape(
                        tuning=(row.get("Tuning") or "").strip(),
                        root=(row.get("Root") or "").strip(),
                        quality=(row.get("Quality") or "").strip(),
                        shape=shape_text,
                        comfort_code=comfort_code,
                        comfort_explanation=(
                            row.get("Comfort Code Explanation")
                            or ""
                        ).strip(),
                        comments=(
                            row.get("Comments") or ""
                        ).strip(),
                        verified=verified
                    )
                )

        self.loaded_files.append(filename)


    def find(self, tuning, root, quality):
        """
        Return every loaded ChordShape matching the given
        tuning, root, and quality.

        Matching is case-insensitive but otherwise exact --
        e.g. root "Bb" and root "A#" are treated as different
        strings right now, matching how the source CSV stores
        them as separate rows. Normalizing enharmonic spellings
        is future work, not part of this first pass.
        """

        tuning = tuning.strip()
        root = root.strip().lower()
        quality = quality.strip().lower()

        return [
            shape
            for shape in self.shapes
            if shape.tuning == tuning
            and shape.root.lower() == root
            and shape.quality.lower() == quality
        ]


    def statistics(self):
        """
        Development/validation summary of the currently
        loaded library -- not used by the optimizer or report
        generator. Meant for checking how complete the library
        is as more tunings and chord shapes get filled in.

        Quality names are whatever's actually in the loaded
        data (by_quality is built from the data, not a fixed
        list), so new qualities show up automatically without
        code changes here.

        Returns:
        {
            "tunings_loaded": <count of files passed to load()>,
            "by_tuning": {
                "<tuning symbol>": {
                    "total": <int>,
                    "verified": <int>,
                    "candidate": <int>,     # Verified == No
                    "unspecified": <int>,   # Verified blank
                    "by_quality": {"<quality>": <int>, ...}
                },
                ...
            },
            "totals": {
                same shape as one tuning's stats, summed
                across every tuning currently loaded
            }
        }
        """

        by_tuning = {}

        for shape in self.shapes:

            tuning_stats = by_tuning.setdefault(
                shape.tuning,
                {
                    "total": 0,
                    "verified": 0,
                    "candidate": 0,
                    "unspecified": 0,
                    "by_quality": {}
                }
            )

            tuning_stats["total"] += 1

            if shape.verified is True:

                tuning_stats["verified"] += 1

            elif shape.verified is False:

                tuning_stats["candidate"] += 1

            else:

                tuning_stats["unspecified"] += 1

            tuning_stats["by_quality"][shape.quality] = (
                tuning_stats["by_quality"].get(
                    shape.quality, 0
                ) + 1
            )


        totals = {
            "total": 0,
            "verified": 0,
            "candidate": 0,
            "unspecified": 0,
            "by_quality": {}
        }

        for tuning_stats in by_tuning.values():

            totals["total"] += tuning_stats["total"]

            totals["verified"] += tuning_stats["verified"]

            totals["candidate"] += tuning_stats["candidate"]

            totals["unspecified"] += (
                tuning_stats["unspecified"]
            )

            for quality, count in (
                tuning_stats["by_quality"].items()
            ):

                totals["by_quality"][quality] = (
                    totals["by_quality"].get(quality, 0)
                    + count
                )


        return {
            "tunings_loaded": len(self.loaded_files),
            "by_tuning": by_tuning,
            "totals": totals
        }
