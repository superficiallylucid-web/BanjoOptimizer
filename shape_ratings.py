"""
shape_ratings.py

Human-curated list of chord FD shapes to avoid, based on real
playing experience -- not derived algorithmically.

Why this exists: hand mechanics for a given fret pattern often
depend on things no simple rule can reliably capture -- most
importantly, barre technique. A single finger laid across
several strings at the same fret can make an otherwise-awkward-
looking shape genuinely easy (e.g. "2552" is fine: the index
finger barres the two "2"s on strings 1 and 4, leaving fingers
3/4 free to comfortably reach the two "5"s in the middle) --
while a visually similar shape can be genuinely unplayable for a
different reason (e.g. "2225" is not: barring strings 1-3 at
fret 2 still leaves too great a reach to fret 5 on string 4). An
algorithmic rule tuned to catch one of these cases reliably
mis-judges the other -- confirmed directly during this file's
own design.

This is intentionally a lookup, not a formula: add a shape here
only once you've actually evaluated it by hand as unplayable.
Every shape NOT listed here is entirely unaffected -- it
continues through playability.py's own existing algorithmic
checks exactly as before this file existed. (A shape you've
confirmed IS playable, like "2552", doesn't need to be listed at
all -- it simply isn't added here.)

Key: the exact shape string as chord_service.py/fretboard.py
already produce it (e.g. "2225", "--657" for a muted string).
This is an exact-string match only -- a visually similar shape
(e.g. "5222" vs "4222") is a different entry and must be added
separately if it's also unplayable.
"""

AVOID_SHAPES = {

  
    "5222",

}
