from tunings import get_tunings

from music import get_key_profile

from models import TuningResult, Score

from fretboard import (
    find_positions,
    best_position as choose_best_position,
    set_capo, get_capo
)

from playing_model import (
    analyze_tuning_playing_model, _chord_working_fret,
    analyze_chord_shape_playability
)

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import _select_chord_shape_for_harmony

from fretboard import parse_shape


# ---------------------------------------------------------
# Reason classification
# ---------------------------------------------------------
#
# score_tuning() still builds one flat list of explanation
# strings exactly as before -- this step only sorts that
# existing text into advantages vs. tradeoffs afterward. It
# doesn't change what gets said or how the score is computed,
# only how the explanation is categorized for the report.
#
# Only one reason string is negative today ("N notes require
# difficult positions"); everything else is a positive/
# informational statement. Extend TRADEOFF_MARKERS if future
# heuristics add more negative reasons.

TRADEOFF_MARKERS = [
    "require difficult positions"
]


def classify_reasons(reasons):
    """
    Split a flat reasons list into (advantages, tradeoffs)
    based on known negative-reason phrasing.
    """

    advantages = []
    tradeoffs = []

    for reason in reasons:

        is_tradeoff = any(
            marker in reason
            for marker in TRADEOFF_MARKERS
        )

        if is_tradeoff:

            tradeoffs.append(reason)

        else:

            advantages.append(reason)

    return advantages, tradeoffs


class TuningAnalyzer:
    """
    Analyzes banjo tunings against a melody.

    Focus:
    - note playability
    - hand movement
    - 5th string transition support
    """

    # How much weight to give a tuning's authored "sounds right
    # for this key" strength. Kept low on purpose: liking how a
    # tuning resonates in a key is a real but overrated signal —
    # people (and this optimizer) tend to overweight it relative
    # to actual playability.
    KEY_BONUS_WEIGHT = 0.5

    # Hand-movement score, normalized per note transition
    # (see score_tuning) rather than summed raw. Summed raw,
    # it scaled with song length and could run into the
    # hundreds for a long piece — silently overpowering every
    # other component, including key_bonus, open_string_bonus,
    # and coverage, all of which are fixed-range (roughly
    # 0-40). This weight brings the *average* per-transition
    # score (range roughly -4 to +3) up to a comparable scale.
    MOVEMENT_SCORE_WEIGHT = 8

    # Playing Model integration (see playing_model.py /
    # DESIGN.md). analyze_tuning_playing_model()'s total_score
    # sums one term per melody phrase, so like movement_score
    # above, it scales with song length -- normalized here to
    # an average per-phrase score before this weight is applied,
    # for the same reason: an unweighted per-song total would
    # silently swamp every other component on a long piece.
    # Deliberately small and conservative for this first
    # integration step -- not tuned against real scores beyond
    # confirming it stays a modest, subordinate contribution
    # (see DESIGN.md).
    PLAYING_MODEL_WEIGHT = 0.05

    # BO-48 -- Chord/FD quality's influence on tuning selection,
    # kept STRICTLY SEPARATE from PLAYING_MODEL_WEIGHT above
    # (that weight governs an unrelated existing contribution;
    # this one governs how much the new Chord/FD component
    # affects the melody/Chord-FD blend -- see analyze()'s own
    # docstring for the full combination formula). Range 0.0-1.0:
    # 0.0 = no Chord/FD influence at all (melody-only, today's
    # existing behavior); 1.0 = the melody/Chord-FD blend is
    # determined by Chord/FD quality alone (melody remains
    # available separately for tie-breaking/diagnostics
    # regardless of this value -- see TuningResult.score).
    # PROVISIONAL: BO-46/47's investigation (4 real, independent
    # scores) found the evidence supports a range, not a single
    # proven value -- rankings only changed at influence>=0.5 in
    # that dataset using this exact fixed-reference normalization
    # (see MAX_AWKWARDNESS_REFERENCE below), and one of BO-47's
    # own intended validation scenarios (similar melody quality,
    # substantially different Chord/FD quality) had no real
    # example in that 4-score dataset at all. 0.30 is chosen as a
    # conservative starting default within BO-47's own recommended
    # 0.25-0.4 range, not a calibrated final answer. Revisit if a
    # genuinely new, independent real score becomes available, or
    # if real generated output at this value doesn't look right in
    # practice.
    CHORD_FD_INFLUENCE = 0.30

    # BO-48 -- the WORKING_FRET_COMFORT_CEILING is the exact
    # BO-43/44/46 comfort threshold (avg_awkwardness = mean of
    # max(0, working_fret - comfort_ceiling) across real chord
    # onsets); MAX_AWKWARDNESS_REFERENCE is the fixed upper bound
    # avg_awkwardness is normalized against, chosen SPECIFICALLY
    # to be independent of whichever other tunings happen to be
    # in a given candidate set (BO-47's own central requirement --
    # the exact defect BO-47 found in simple per-song min-max
    # normalization, where a candidate's own normalized score
    # could shift purely because an unrelated third candidate was
    # added or removed). The instrument's own true physical
    # maximum (find_positions()'s own hard 22-fret ceiling) gives
    # a fully principled but far too WIDE a bound in practice --
    # tested directly and confirmed it compresses every real
    # observed avg_awkwardness value (0 to ~3.28 across all real
    # BO-43/44/46/46 data) into the top ~20% of the scale, so
    # weak that no ranking in the real 4-song dataset ever changed
    # below influence=1.0. MAX_AWKWARDNESS_REFERENCE=4.0 is
    # instead a documented, PROVISIONAL reference derived from
    # that same observed real data (max observed: 3.28, in White
    # Christmas/G Modal Sawmill) -- fixed regardless of candidate
    # set, but calibrated to the scale BO has actually produced on
    # real scores so far, per BO-47's own explicit fallback
    # ("use a clearly documented provisional reference range
    # derived from the observed BO-43/44/46 data") for exactly
    # this situation. Revisit if a real score ever produces
    # avg_awkwardness meaningfully above 4.0 -- values would
    # simply saturate toward 0 quality rather than reading
    # incorrectly, but the discrimination this constant is meant
    # to provide would weaken for that song.
    WORKING_FRET_COMFORT_CEILING = 7

    MAX_AWKWARDNESS_REFERENCE = 4.0

    # BO-176 -- replaces the old PLAYING_MODEL_QUALITY_REFERENCE-
    # based chord_fd_quality entirely (found, on real data, to be
    # permanently saturated at 1.0 -- every real tuning's own
    # average-phrase score already exceeded 50 on every song
    # tested, including tunings the user rated unplayable, so the
    # term contributed zero discrimination to tuning ranking).
    #
    # chord_fd_quality is now a worst-N-average of a per-chord
    # score (see chord_fd_quality_bonus()'s own docstring for the
    # full per-chord formula: intrinsic shape playability minus
    # an isolation-aware "high position, was it worth it" cost),
    # not an average-phrase Playing Model score. Confirmed via
    # direct user validation against real per-tuning ratings on
    # Aureolin (G Modal Sawmill rated 0/unplayable for one
    # catastrophic chord among an otherwise fine song -- worst-N
    # correctly collapses its score far below every other
    # candidate, where the old full-average buried it mid-pack;
    # A Modal Sawmill rated 8/best -- worst-N correctly ranks it
    # highest).
    #
    # This per-chord score is NOT bounded the way the old Playing
    # Model phrase score was (the position-cost term can drive it
    # negative for a genuinely bad, isolated high chord), so it's
    # normalized against a fixed [MIN, MAX] reference range rather
    # than divided by a single upper bound. PROVISIONAL, derived
    # from real worst-2-average values observed across 4 real
    # songs' own top-6 candidates each (Aureolin, Christmas Song,
    # My Favorite Things, White Christmas): observed range was
    # -6.50 (Aureolin/G Modal Sawmill, the confirmed catastrophic
    # case) to 7.12 (Aureolin/A Modal Sawmill, the confirmed best
    # case). -8/9 gives roughly 1.5-2 points of headroom on each
    # side beyond the observed extremes -- revisit if a future
    # real song's own worst-2-average falls outside this range;
    # values would saturate toward 0/1 rather than reading
    # incorrectly, but discrimination would weaken for that song.
    CHORD_FD_QUALITY_MIN_REFERENCE = -8.0

    CHORD_FD_QUALITY_MAX_REFERENCE = 9.0

    # BO-176 -- how many of a tuning's own worst chords (by the
    # per-chord score above) are averaged together, rather than
    # averaging every chord in the song or using only the single
    # worst one. Confirmed against direct user judgment: a single
    # bad chord the user would work around by re-spelling that
    # one chord in the input score should NOT be able to zero out
    # an otherwise-great tuning (rules out worst-1 alone); a
    # tuning with a genuine PATTERN of poor chords (the real G
    # Modal Sawmill/Aureolin case -- 4420 and 2214 were already
    # awkward before its one catastrophic chord) should stay
    # low across the board, which a full-song average was found
    # to wash out entirely (G Modal Sawmill's own full average on
    # Aureolin was 5.77, unremarkable next to every other
    # candidate -- see chord_fd_quality_bonus()'s own docstring).
    # 2 is the smallest N that distinguishes those two real cases
    # -- not independently swept against a wider N, since this
    # value was fixed BEFORE turning to the weight/normalization
    # work that follows it.
    CHORD_FD_WORST_N = 2

    # BO-176 -- excess working_fret beyond WORKING_FRET_COMFORT_
    # CEILING is only charged its FULL cost when the chord is
    # genuinely isolated (the user's own "for one chord and a few
    # tabs" complaint about Aureolin's G Modal Sawmill 17-18-16-19
    # shape) -- a high chord that's part of a real passage (its
    # immediate neighbor chord onsets are also high, and close
    # enough on the neck to be the same hand position) costs much
    # less, since the position is already justified by more than
    # one chord. Multiplier keyed by how many of the two immediate
    # neighbors (preceding, following) qualify as "high and
    # close": 0 neighbors = full cost (genuinely isolated), 1 =
    # substantially discounted, 2 = a real passage, minimal cost.
    # 0.4/0.15 are provisional -- not independently derived,
    # chosen to give a clear, visible gap between the three tiers
    # while confirmed not to fully zero out a passage's own real
    # neck-position cost. NOTE (flagged to user, not yet
    # resolved): being part of a passage does not mean the
    # position is within a given player's own physical fret
    # range -- this multiplier can still discount a chord that
    # exceeds a user's own instrument (see the pending, separate
    # fret-ceiling task). Confirmed via real data this can let a
    # tuning built around a sustained high-fret passage (fret 17,
    # beyond the user's own stated 15-fret instrument) rank #1
    # regardless of chord_fd_quality's own influence weight (real
    # White Christmas/G Modal Sawmill case) -- CHORD_FD_INFLUENCE
    # is deliberately being held at its current value rather than
    # raised until fret-ceiling filtering exists to remove such
    # candidates before this scoring ever sees them.
    CHORD_FD_ISOLATION_MULTIPLIER = {0: 1.0, 1: 0.4, 2: 0.15}

    # BO-176 -- how close two chords' own working_fret values
    # need to be, in raw fret count, to count as "the same hand
    # position" for the isolation check above. Sanity-checked
    # against real banjo fretboard geometry (12th-root-of-2 fret
    # spacing, 26.5in scale) rather than picked arbitrarily: this
    # value is only ever evaluated between two chords that are
    # BOTH already above WORKING_FRET_COMFORT_CEILING (7) -- in
    # that fret-7-and-up range, 3 frets corresponds to roughly
    # 1.7-2.8 physical inches, which lines up with a genuine
    # "no real hand shift" distance. Confirmed this constant does
    # NOT need position-dependent scaling despite fret spacing
    # itself varying substantially across the neck (a 3-fret span
    # near the nut is ~4in, physically a real shift), because the
    # relevant range for this specific check is narrow enough
    # that a single fixed value holds up across it.
    CHORD_FD_CLOSE_POSITION_THRESHOLD = 3

    # BO-176 -- fixed reference range the raw melody `score` is
    # normalized against, replacing the old per-candidate-set
    # min-max normalization in _apply_combined_score(). Found,
    # on real data, that candidate-set-relative min-max was
    # stretching very small real melody-score gaps (as little as
    # ~1.5%, e.g. Aureolin's own top candidates spanning only
    # 83.16 to 84.73) into a full 0-to-1 swing -- giving melody
    # disproportionate leverage over chord_fd_quality even at
    # equal blend weights, since chord_fd_quality was already
    # normalized against a fixed range that doesn't inflate small
    # gaps the same way. This was the direct cause of a real,
    # confirmed case (Aureolin) where A Modal Sawmill -- the
    # user's own highest-rated tuning -- could not reach #1 even
    # at influence=0.50 until this was fixed; fixing normalization
    # alone (no weight change at all) was sufficient. PROVISIONAL,
    # derived from real melody `score` values observed across all
    # 5 real songs' own full modern-category candidate sets (55
    # observations), called with score.estimate_key() beforehand
    # exactly as main.py's own real production path always does
    # (an earlier calibration pass omitted this call and derived
    # a substantially-too-low range from it -- key_bonus() and
    # related open-string/5th-string bonuses add real points once
    # a key is actually detected, confirmed directly: e.g. White
    # Christmas's own real range only becomes 79-112 once
    # estimate_key() runs, not 74-80 without it): observed range
    # was 71.37 to 115.86. 60/125 gives meaningful headroom on
    # both sides beyond the observed extremes. Revisit if a
    # future real song's own melody score falls outside this
    # range; values would saturate toward 0/1 rather than reading
    # incorrectly, but discrimination would weaken for that song
    # -- the same tradeoff every other fixed reference range in
    # this class already documents.
    MELODY_SCORE_MIN_REFERENCE = 60.0

    MELODY_SCORE_MAX_REFERENCE = 125.0

    # BO-48 -- severity of the SEPARATE unplayable-melody-note
    # penalty (see chord_fd_quality_bonus()'s own docstring for
    # why this must never be folded into Chord/FD quality itself,
    # and analyze()'s own docstring for exactly where/how it's
    # applied). NOTE: score_tuning() ALREADY subtracts
    # impossible * 0.5 from the raw melody `score` (existing,
    # pre-BO-48 behavior, confirmed still present and unchanged)
    # -- this constant is an intentional, separate, ADDITIONAL
    # strengthening applied at the combined-score stage, not a
    # duplicate of that existing penalty. BO-47 demonstrated the
    # existing 0.5/note penalty alone is too weak to keep a
    # worse-unplayable-notes tuning from still winning even at
    # full Chord/FD influence (My Favorite Things/Old G, 18
    # unplayable notes, stayed ranked #1 through Chord/FD
    # influence=0.25 using the old candidate-set-dependent
    # normalization). Expressed per unplayable-note PROPORTION
    # (not raw count) so it behaves consistently across songs of
    # different lengths. PROVISIONAL -- chosen to be large enough
    # that My Favorite Things' own real 18-vs-12-unplayable-note
    # gap (9.8% vs 6.6% of melody notes) measurably outweighs that
    # song's own real melody-score gap between those same
    # candidates at every tested influence level; not derived
    # from a larger, independent dataset.
    UNPLAYABLE_NOTE_PENALTY_WEIGHT = 3.0


    def __init__(
        self, notes, key="Unknown", harmonies=None, melody_notes=None
    ):
        """
        harmonies: optional list of Harmony objects (see
        models.py -- already produced by
        parser.read_harmonies(), not re-parsed here) for the
        same score. Stored as-is; used by the Playing Model
        integration (see playing_model_bonus()) when present.
        Defaults to None so every existing caller/test that
        constructs TuningAnalyzer(notes, key) is unaffected.

        melody_notes: optional list of Note objects (see
        models.py) for the same score -- the SAME data
        parser.read_melody_notes() already builds on the
        underlying Score object (accessible as
        MuseScoreFile.score.notes), just also passed here.
        Needed only by the Playing Model, for real beat-level
        melody timing -- `notes` (the existing dict-format
        list used by every pre-existing score component) has
        no beat information at all. Not duplicated or
        re-derived here, only passed through.
        """

        self.notes = notes

        self.key = key

        self.harmonies = harmonies if harmonies is not None else []

        self.melody_notes = (
            melody_notes if melody_notes is not None else []
        )



    # -------------------------------------------------

    def analyze(self):
        """
        BO-48 -- after collecting every tuning's own raw
        score_tuning() result (melody `score` plus the per-
        tuning, candidate-set-independent chord_fd_quality/
        unplayable-note metrics from chord_fd_quality_bonus()),
        this method computes each result's own `combined_score`
        -- the value modern/historical are actually sorted and
        recommended by -- via:

          1. normalized_melody: `score` min-max normalized
             against the OTHER tunings in the SAME group (modern
             vs. historical, matching tuning.category) being
             ranked together here. This is the one place this
             project intentionally uses candidate-set-dependent
             normalization -- melody quality is inherently a
             relative, "how does this compare to other tunings
             for THIS song" question (raw melody scores aren't
             comparable across different songs at all), unlike
             Chord/FD awkwardness, which has a genuine, absolute,
             physical meaning (a fret position is a fret position
             regardless of song) and is normalized separately in
             chord_fd_quality_bonus() against a FIXED reference
             instead, specifically so it does NOT depend on which
             other tunings are present (see MAX_AWKWARDNESS_
             REFERENCE's own comment -- this is the exact defect
             BO-47 found and this method is designed to avoid for
             the Chord/FD side).
          2. combined = (1 - CHORD_FD_INFLUENCE) * normalized_melody
                       + CHORD_FD_INFLUENCE * chord_fd_quality
          3. an explicit, SEPARATE penalty for unplayable_note_
             proportion (UNPLAYABLE_NOTE_PENALTY_WEIGHT), applied
             on top of `combined` -- never diluted by
             CHORD_FD_INFLUENCE, per BO-47's own explicit finding
             that increasing Chord/FD influence does not reliably
             fix a genuinely-unplayable-notes situation on its
             own (My Favorite Things/Old G).

        The existing `score` field is left completely untouched
        throughout -- still the raw melody/Playing-Model score,
        still what every pre-BO-48 caller/test/report reads.
        `combined_score` is the new field this method's own
        sort now uses.

        Gracefully handles a single-result group (normalized_
        melody is simply 1.0 -- nothing to compare against) and
        a song with no harmony data at all (chord_fd_quality_
        bonus() already returns a neutral 1.0/0-penalty in that
        case, so this component contributes nothing, matching
        the existing playing_model_bonus() convention).
        """

        tunings = get_tunings()

        modern = []

        historical = []



        for tuning in tunings.values():

            result = self.score_tuning(
                tuning
            )


            if tuning.category == "modern":

                modern.append(
                    result
                )

            else:

                historical.append(
                    result
                )



        for group in (modern, historical):

            self._apply_combined_score(group)


        modern.sort(
            key=lambda x: x.combined_score,
            reverse=True
        )


        historical.sort(
            key=lambda x: x.combined_score,
            reverse=True
        )


        return {

            "modern": modern,

            "historical": historical

        }



    def _apply_combined_score(self, results):
        """
        BO-48 -- see analyze()'s own docstring for the full
        formula. Mutates each TuningResult in `results` in
        place, setting combined_score; does not reorder the
        list (analyze() sorts afterward).

        BO-176 -- normalized_melody now uses the same FIXED-
        reference approach chord_fd_quality already used (see
        MELODY_SCORE_MIN/MAX_REFERENCE's own comment for why):
        the previous candidate-set-relative min-max was found, on
        real data, to stretch very small real melody-score gaps
        into a full 0-to-1 swing, giving melody disproportionate
        leverage over chord_fd_quality regardless of the blend
        weight used -- confirmed as the direct cause of a real
        case (Aureolin) where the user's own highest-rated tuning
        could not reach #1 even at influence=0.50 until this was
        fixed, with no weight change needed once it was.
        """

        if not results:

            return results

        for result in results:

            normalized_melody = max(0.0, min(
                (
                    result.score - self.MELODY_SCORE_MIN_REFERENCE
                ) / (
                    self.MELODY_SCORE_MAX_REFERENCE
                    - self.MELODY_SCORE_MIN_REFERENCE
                ),
                1.0
            ))

            combined = (
                (1 - self.CHORD_FD_INFLUENCE) * normalized_melody
                + self.CHORD_FD_INFLUENCE * result.chord_fd_quality
            )

            unplayable_penalty = (
                self.UNPLAYABLE_NOTE_PENALTY_WEIGHT
                * result.unplayable_note_proportion
            )

            result.combined_score = combined - unplayable_penalty

        return results



    # -------------------------------------------------

    def get_note_midi(self, note):

        """
        Supports both the original
        dictionary notes and the newer
        Note dataclass.
        """

        if isinstance(note, dict):

            return note["midi"]


        return note.midi



    # -------------------------------------------------

    def score_tuning(self, tuning):
        """
        BO-185 -- thin wrapper around the real implementation
        (renamed _score_tuning_impl below): sets the shared capo
        context (fretboard.set_capo()) to THIS tuning's own capo
        value for the full duration of scoring it, restoring
        whatever capo value was active before regardless of how
        scoring exits (including an exception) -- every one of
        this method's own find_positions() calls (direct or via
        chord_generator.py/_select_chord_shape_for_harmony())
        needs the physical ceiling reduced by this tuning's own
        capo, not the previous tuning's. A thin wrapper here,
        rather than wrapping the ~300-line real method body in
        try/finally directly, avoids re-indenting that entire
        body for this one addition.
        """

        original_capo = get_capo()

        try:

            set_capo(tuning.capo)

            return self._score_tuning_impl(tuning)

        finally:

            set_capo(original_capo)

    def _score_tuning_impl(self, tuning):


        playable = 0

        impossible = 0


        total_position_score = 0


        movement_score = 0

        transition_count = 0



        previous_position = None


        reasons = []



        positions = []



        # ---------------------------------------------
        # Find best position for every melody note
        # ---------------------------------------------


        for note in self.notes:


            midi = self.get_note_midi(
                note
            )


            possible = find_positions(
                midi,
                tuning.notes
            )



            if not possible:

                impossible += 1

                positions.append(
                    None
                )

                previous_position = None

                continue



            playable += 1



            best_position = choose_best_position(
                possible
            )


            positions.append(
                best_position
            )


            total_position_score += (
                best_position["score"]
            )



            # -----------------------------------------
            # Compare hand movement
            # -----------------------------------------


            if previous_position:


                transition_count += 1


                movement = abs(

                    previous_position["fret"]

                    -

                    best_position["fret"]

                )



                if movement <= 3:

                    movement_score += 3



                elif movement <= 6:

                    movement_score += 1



                elif movement > 8:

                    movement_score -= 4



            previous_position = best_position

        # ---------------------------------------------
        # Base scoring
        # ---------------------------------------------


        if self.notes:


            coverage_score = (

                playable /

                len(self.notes)

            ) * 40


        else:

            coverage_score = 0



        if playable:


            fret_score = (

                total_position_score /

                playable

            ) * 2


        else:

            fret_score = 0


        if transition_count:

            movement_score = (

                movement_score /

                transition_count

            ) * self.MOVEMENT_SCORE_WEIGHT

        else:

            movement_score = 0



        score = (

            coverage_score

            +

            fret_score

            +

            movement_score

        )



        score += self.key_bonus(

            tuning,

            reasons

        )

        # Future enhancement:
        # score += self.special_key_tuning_bonus(
        #     tuning,
        #     reasons
        # )

        score += self.open_string_bonus(
            tuning,
            reasons
        )

        score += self.fifth_string_drone_bonus(
            tuning,
            reasons
        )

        score += tuning.popularity * 0.5



        if tuning.popularity >= 8:

            reasons.append(
                "Common modern 5-string tuning"
            )



        if impossible:

            score -= impossible * 0.5

            reasons.append(
                f"{impossible} notes require difficult positions"
            )



        score += self.playing_model_bonus(
            tuning
        )

        (
            avg_awkwardness, chord_fd_quality,
            unplayable_note_count, unplayable_note_proportion,
            avg_generated_chord_playability
        ) = self.chord_fd_quality_bonus(tuning)

        advantages, tradeoffs = classify_reasons(reasons)

        return TuningResult(

            name=tuning.name,

            symbol=tuning.symbol,

            category=tuning.category,

            score=round(
                score,
                2
            ),

            advantages=advantages,

            tradeoffs=tradeoffs,

            # BO-48 -- populated here (per-tuning, candidate-
            # set-independent); combined_score is deliberately
            # NOT set here (0.0 default) -- analyze() computes it
            # afterward, once it has the full candidate group
            # this tuning is being compared/ranked alongside
            # (see analyze()'s own docstring).
            avg_awkwardness=avg_awkwardness,

            chord_fd_quality=chord_fd_quality,

            unplayable_note_count=unplayable_note_count,

            unplayable_note_proportion=unplayable_note_proportion,

            avg_generated_chord_playability=(
                avg_generated_chord_playability
            )

            # shared_features and confidence are left at
            # their defaults ([] and None) -- shared_features
            # is a group-level concept (see
            # recommendations.py), and confidence isn't
            # computed yet.

        )



    # -------------------------------------------------




    # -------------------------------------------------

    def fifth_string_drone_bonus(
        self,
        tuning,
        reasons
    ):


        if len(tuning.notes) < 5:

            return 0



        profile = get_key_profile(
            self.key
        )


        if not profile:

            return 0



        fifth = tuning.notes[4] % 12



        if fifth == profile["tonic"]:

            reasons.append(
                "Useful 5th string drone"
            )

            return 5



        elif fifth in profile["chord"]:

            reasons.append(
                "5th string supports harmony"
            )

            return 3



        return 0



    # -------------------------------------------------

    def key_bonus(self, tuning, reasons):

        strengths = tuning.key_strengths


        if self.key not in strengths:

            return 0



        bonus = strengths[self.key]



        if bonus >= 12:

            reasons.append(
                f"Excellent fit for {self.key}"
            )


        elif bonus >= 8:

            reasons.append(
                f"Good fit for {self.key}"
            )


        else:

            reasons.append(
                f"Playable in {self.key}"
            )


        return bonus * self.KEY_BONUS_WEIGHT



    # -------------------------------------------------

    def open_string_bonus(self, tuning, reasons):

        profile = get_key_profile(
            self.key
        )


        if not profile:

            return 0



        score = 0


        tonic = profile["tonic"]

        chord = profile["chord"]

        scale = profile["scale"]



        tonic_count = 0

        chord_count = 0



        for note in tuning.notes:


            pitch = note % 12



            if pitch == tonic:

                score += 5

                tonic_count += 1



            elif pitch in chord:

                score += 4

                chord_count += 1



            elif pitch in scale:

                score += 1



        if tonic_count:

            reasons.append(
                "Open tonic support"
            )



        if chord_count:

            reasons.append(
                "Open chord-tone support"
            )



        return score



    # -------------------------------------------------

    def playing_model_bonus(self, tuning):
        """
        Small additive contribution from the chord-centered
        Playing Model (see playing_model.py / DESIGN.md) --
        how well this tuning's playable chord shapes and melody
        locations work together, given the score's real
        chord/harmony context.

        Zero when no harmony/melody context is available (every
        existing caller/score without chord symbols is
        unaffected), or if the Playing Model itself can't
        produce a result for any reason -- this integration must
        never break or change scoring for scores it can't help
        with. Any unexpected failure here is treated the same as
        "no contribution," not as a scoring error.

        Normalized to an average per-phrase score (see
        PLAYING_MODEL_WEIGHT's own comment for why) and scaled
        by PLAYING_MODEL_WEIGHT before being added to the
        existing tuning score -- deliberately small relative to
        the ~100-130 range existing scores occupy on real test
        scores.
        """

        if not self.harmonies or not self.melody_notes:

            return 0.0

        try:

            temp_score = Score(
                notes=self.melody_notes,
                harmonies=self.harmonies
            )

            chord_service = ChordService(ChordLibrary())

            playing_model_result = analyze_tuning_playing_model(
                temp_score, tuning, chord_service
            )

            phrase_count = len(playing_model_result.phrases)

            if phrase_count == 0:

                return 0.0

            average_phrase_score = (
                playing_model_result.total_score / phrase_count
            )

            return average_phrase_score * self.PLAYING_MODEL_WEIGHT

        except Exception:

            return 0.0

    # -------------------------------------------------

    def chord_fd_quality_bonus(self, tuning):
        """
        BO-176 -- Chord/playing quality for this tuning.

        Replaces BO-49's own Playing-Model-average-based chord_
        fd_quality entirely. Found, via direct user validation on
        real recommended tunings (Aureolin), that averaging across
        every chord in a song makes a single catastrophic shape
        invisible -- a genuinely unplayable chord (17-18-16-19, on
        a tuning the user rated 0/unplayable) sat mid-pack in the
        old full-average, buried by the song's many otherwise-fine
        chords. What actually drove the user's own judgment, per
        direct confirmation: a single bad chord they'd work around
        by re-spelling that one chord in the input score should
        NOT sink an otherwise-great tuning; a tuning with a
        genuine PATTERN of poor chords should stay low regardless
        of how many fine chords surround them. See CHORD_FD_
        WORST_N's own comment for why worst-N (not worst-1, not a
        full average) is the reconciliation of those two real
        cases.

        Per-chord score (before worst-N averaging): analyze_
        chord_shape_playability().score (intrinsic shape
        difficulty -- finger count, span, hand geometry, UNCHANGED
        from BO-131.4) minus a position cost: max(0, working_fret
        - WORKING_FRET_COMFORT_CEILING) times CHORD_FD_ISOLATION_
        MULTIPLIER, keyed by how many of the chord's own immediate
        neighbor onsets (preceding, following) are ALSO high and
        close enough on the neck to count as the same real
        passage (CHORD_FD_CLOSE_POSITION_THRESHOLD). Directly
        confirmed against the real Aureolin case: the user's own
        stated complaint about 17-18-16-19 was specifically "I
        would not want to jump that high up the neck for one
        chord and a few tabs" -- an isolated high chord costs its
        full excess; a chord that's part of a real passage (both
        neighbors also high and close) costs a small fraction of
        it, since the position is already justified by more than
        one chord.

        The worst CHORD_FD_WORST_N of these per-chord scores
        (lowest N, not the whole song) are averaged, then
        normalized to [0, 1] against a FIXED reference range
        (CHORD_FD_QUALITY_MIN/MAX_REFERENCE -- this per-chord
        score is not bounded the way the old Playing Model phrase
        score was, since the position-cost term can drive it
        negative) -- still deliberately NOT the current candidate
        set's own min/max, preserving BO-47/48's own central
        requirement: this value must not change merely because a
        different tuning is also being compared alongside this
        one. 1.0 = as good as the reference range allows; 0.0 =
        at or beyond its low end.

        Returns (avg_awkwardness, chord_fd_quality,
        unplayable_note_count, unplayable_note_proportion,
        avg_generated_chord_playability).

        avg_generated_chord_playability -- BO-131.4, UNCHANGED.
        Mean analyze_chord_shape_playability().score across this
        same loop's own real chord occurrences (a full-song
        average, not the worst-N used for chord_fd_quality
        above), evaluated on the EXACT shape _select_chord_shape_
        for_harmony() selects. Deliberately not yet part of
        combined_score or any existing weight; see TuningResult.
        avg_generated_chord_playability's own docstring in
        models.py.

        avg_awkwardness (BO-43/44/46 definition, UNCHANGED --
        mean of max(0, working_fret - WORKING_FRET_COMFORT_
        CEILING) across real chord onsets) is still computed and
        returned as a diagnostic/comparison value -- existing
        BO-48 tests and reporting that read it are unaffected --
        chord_fd_quality itself was never derived from it even
        before this change (BO-49 already replaced that
        dependency; this change only replaces what chord_fd_
        quality derives from instead).

        unplayable_note_count/proportion: UNCHANGED from BO-48 --
        still a separate, hard-playability-failure concept,
        computed identically (find_positions() returns empty),
        still returned separately so analyze()'s own explicit
        UNPLAYABLE_NOTE_PENALTY_WEIGHT penalty stays independent
        of this component, per BO-47's own finding that Chord/FD
        quality alone does not reliably fix a genuinely-
        unplayable-notes situation.

        Zero/neutral defaults (0.0 avg_awkwardness, 1.0
        chord_fd_quality, 0 unplayable notes) when no harmony/
        melody context is available, or if the Playing Model
        itself produces zero phrases -- matching playing_model_
        bonus()'s own established "no chord data -> no
        contribution" convention exactly. Any unexpected failure
        is treated the same way, never as a scoring error.
        """

        if not self.melody_notes:

            return 0.0, 1.0, 0, 0.0, 0.0

        # Matches score_tuning()'s own existing `impossible`
        # check exactly: tuning.notes (all 5 strings, including
        # the 5th/drone), not tuning.notes[1:] -- using a
        # different, narrower definition here would silently
        # disagree with the existing, already-established
        # unplayable-note count and could over-count notes that
        # are genuinely reachable via the 5th string.
        open_notes = tuning.notes

        unplayable_note_count = 0

        for note in self.melody_notes:

            positions = find_positions(
                note.midi, open_notes
            )

            if not positions:

                unplayable_note_count += 1

        unplayable_note_proportion = (
            unplayable_note_count / len(self.melody_notes)
        )

        if not self.harmonies:

            return 0.0, 1.0, unplayable_note_count, (
                unplayable_note_proportion
            ), 0.0
        try:

            chord_service = ChordService(ChordLibrary())

            # avg_awkwardness -- unchanged BO-43/44/46
            # definition, still computed for diagnostics/
            # comparison even though chord_fd_quality no longer
            # derives from it directly.

            awkwardness_sum = 0.0

            total_chord_onsets = 0

            # BO-131.4 -- independent chord-quality signal,
            # accumulated in this same loop (not a second
            # traversal) from the exact shape this call already
            # selects for awkwardness above.
            generated_chord_playability_sum = 0.0

            # BO-176 -- in onset order, populated inside the loop
            # below; consumed after the loop for the isolation-
            # aware position-cost pass (needs neighbor access, so
            # cannot be computed within a single forward pass).
            chord_sequence = []

            incoming_shape = None

            for harmony_index, harmony in enumerate(
                self.harmonies
            ):

                next_harmony = (
                    self.harmonies[harmony_index + 1]
                    if harmony_index + 1 < len(self.harmonies)
                    else None
                )

                shape, is_exception, exception_dict = (
                    _select_chord_shape_for_harmony(
                        harmony, tuning, chord_service,
                        melody_notes=self.melody_notes,
                        next_harmony=next_harmony,
                        incoming_shape=incoming_shape
                    )
                )

                if shape is not None:

                    incoming_shape = shape.shape

                if shape is None:

                    continue

                shape_values = parse_shape(shape.shape)

                if any(v is None for v in shape_values):

                    continue

                working_fret = _chord_working_fret(
                    shape_values
                )

                if working_fret is None:

                    continue

                awkwardness = max(
                    0,
                    working_fret
                    - self.WORKING_FRET_COMFORT_CEILING
                )

                awkwardness_sum += awkwardness

                # BO-131.4 -- same shape, same loop, same
                # denominator (total_chord_onsets) as
                # avg_awkwardness -- analyze_chord_shape_
                # playability() takes only the shape string
                # itself, never melody or the Playing Model, so
                # this carries none of chord_fd_quality's own
                # melody-combination contribution.
                generated_chord_playability_sum += (
                    analyze_chord_shape_playability(
                        shape.shape
                    ).score
                )

                total_chord_onsets += 1

                # BO-176 -- per-chord (working_fret, intrinsic
                # playability) pair, in onset order, for the
                # isolation-aware position-cost pass below.
                chord_sequence.append({
                    "working_fret": working_fret,
                    "intrinsic": analyze_chord_shape_playability(
                        shape.shape
                    ).score
                })

            avg_awkwardness = (
                awkwardness_sum / total_chord_onsets
                if total_chord_onsets else 0.0
            )

            avg_generated_chord_playability = (
                generated_chord_playability_sum
                / total_chord_onsets
                if total_chord_onsets else 0.0
            )

            # chord_fd_quality -- BO-176, see this method's own
            # docstring for the full per-chord formula and why
            # worst-N replaced the old Playing-Model-average
            # approach.

            if not chord_sequence:

                return 0.0, 1.0, unplayable_note_count, (
                    unplayable_note_proportion
                ), avg_generated_chord_playability

            def _is_high_and_close(this_chord, neighbor):

                if neighbor is None:

                    return False

                return (
                    neighbor["working_fret"]
                    > self.WORKING_FRET_COMFORT_CEILING
                    and abs(
                        this_chord["working_fret"]
                        - neighbor["working_fret"]
                    ) <= self.CHORD_FD_CLOSE_POSITION_THRESHOLD
                )

            per_chord_scores = []

            for index, chord in enumerate(chord_sequence):

                excess = max(
                    0,
                    chord["working_fret"]
                    - self.WORKING_FRET_COMFORT_CEILING
                )

                preceding = (
                    chord_sequence[index - 1]
                    if index > 0 else None
                )

                following = (
                    chord_sequence[index + 1]
                    if index + 1 < len(chord_sequence) else None
                )

                qualifying_neighbors = sum([
                    _is_high_and_close(chord, preceding),
                    _is_high_and_close(chord, following)
                ])

                multiplier = self.CHORD_FD_ISOLATION_MULTIPLIER[
                    qualifying_neighbors
                ]

                per_chord_scores.append(
                    chord["intrinsic"] - excess * multiplier
                )

            per_chord_scores.sort()

            worst_n = per_chord_scores[
                :self.CHORD_FD_WORST_N
            ]

            worst_n_average = sum(worst_n) / len(worst_n)

            chord_fd_quality = max(0.0, min(
                (
                    worst_n_average
                    - self.CHORD_FD_QUALITY_MIN_REFERENCE
                ) / (
                    self.CHORD_FD_QUALITY_MAX_REFERENCE
                    - self.CHORD_FD_QUALITY_MIN_REFERENCE
                ),
                1.0
            ))

            return (
                avg_awkwardness, chord_fd_quality,
                unplayable_note_count, unplayable_note_proportion,
                avg_generated_chord_playability
            )

        except Exception:

            return 0.0, 1.0, unplayable_note_count, (
                unplayable_note_proportion
            ), 0.0
