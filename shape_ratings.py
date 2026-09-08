"""
shape_ratings.py

Human-curated list of chord FD shapes to avoid, based on real
playing experience -- not derived algorithmically.

IMPORTANT -- string numbering convention: a shape string here
(e.g. "2225") is written left to right as the LOWEST-pitched to
HIGHEST-pitched of the 4 main strings -- confirmed directly
against tunings.py's own real symbols (e.g. "gCGBD": the "C"
right after the 5th, "g", is notes[1], the lowest-pitched main
string; the final "D" is notes[4], the highest). This is BO's
own internal numbering (ascending pitch), and it is the OPPOSITE
of traditional banjo string numbering (where string 1 is the
highest-pitched string and string 4 is the lowest) -- the two
schemes describe the same physical left-to-right layout, just
with opposite number labels. When translating a real player's
own "string N, fret F" description into a shape string here,
remember that description's own "string 1" is this file's own
LAST character, and its own "string 4" is this file's own FIRST
character.

Why this exists: hand mechanics for a given fret pattern often
depend on things no simple rule can reliably capture -- most
importantly, barre technique. A single finger laid across
several strings at the same fret can make an otherwise-awkward-
looking shape genuinely easy, while a visually similar shape can
be genuinely unplayable for a different reason. An algorithmic
rule tuned to catch one of these reliably mis-judges the other --
confirmed directly during this file's own design.

This is intentionally a lookup, not a formula: add a shape here
only once you've actually evaluated it by hand as unplayable.
Every shape NOT listed here is entirely unaffected -- it
continues through playability.py's own existing algorithmic
checks exactly as before this file existed.

Key: the exact shape string as chord_service.py/fretboard.py
already produce it (e.g. "2225", "--657" for a muted string).
This is an exact-string match only -- a visually similar shape
(e.g. "5222" vs "4222") is a different entry and must be added
separately if it's also unplayable.
"""

AVOID_SHAPES = {

    # Confirmed directly against the player's own explicit
    # string-by-string description: (player string 4, fret 5),
    # (string 3, fret 2), (string 2, fret 2), (string 1, fret 2)
    # -- i.e. this file's own first character (lowest-pitched
    # main string) is fret 5, the rest are fret 2. Reported as
    # "possible, but very difficult": the little finger has to
    # reach past three strings it can't touch (or they'd be
    # muted) from the high-string side of the hand.
    "5222",

}
