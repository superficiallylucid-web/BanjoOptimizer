from tunings import get_tunings

from music import get_key_profile

from models import TuningResult, Score

from fretboard import (
    find_positions,
    best_position as choose_best_position
)

from playing_model import analyze_tuning_playing_model, _chord_working_fret

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

    # fifth_string_transition_support() sums +3/+6 for every
    # melody leap the 5th string can bridge, with no
    # normalization by song length -- same shape of bug as
    # movement_score, just smaller in practice so far. Capping
    # it (rather than normalizing per-transition, which would
    # shrink it to near-nothing on typical songs) keeps
    # today's known-good scores unchanged while still stopping
    # a long or leap-heavy song from letting this term take
    # over the total.
    FIFTH_TRANSITION_CAP = 20

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

    # BO-49 -- fixed reference PLAYING_MODEL_QUALITY_REFERENCE is
    # normalized against, exactly analogous in spirit to
    # MAX_AWKWARDNESS_REFERENCE above (candidate-set-independent,
    # per BO-47/48's own central requirement) but for the richer
    # Playing Model per-phrase score chord_fd_quality is now
    # derived from (see chord_fd_quality_bonus()'s own docstring
    # for why avg_awkwardness alone was replaced as the source of
    # chord_fd_quality).
    #
    # What it represents: an "excellent" phrase's own average
    # score -- BASE_PLAYABILITY (10.0, playing_model.py's own
    # constant, a fully-comfortable chord shape with no
    # penalties) plus CONTAINED_IN_CHORD_BONUS (6.0, playing_
    # model.py) for a handful of melody notes per phrase that
    # land as genuine chord tones, which real songs' own melody
    # density supports (each real song here averages roughly
    # 3 melody notes per chord phrase).
    #
    # How the initial value was selected: PROVISIONAL, derived
    # from real observed data across all 4 real songs' own top-3
    # candidates (BO-49's own investigation) -- average-per-
    # phrase scores ranged from ~26 to ~46 across every real
    # tuning/song combination measured. 50.0 sits just above that
    # observed maximum, the same "round number with headroom"
    # approach MAX_AWKWARDNESS_REFERENCE itself used.
    #
    # Revisit if a future real song's own average-per-phrase
    # score meaningfully exceeds 50 -- values would saturate
    # toward 1.0 rather than reading incorrectly, but
    # discrimination would weaken for that song, the same
    # tradeoff MAX_AWKWARDNESS_REFERENCE's own comment describes.
    PLAYING_MODEL_QUALITY_REFERENCE = 50.0

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
        """

        if not results:

            return results

        melody_scores = [r.score for r in results]

        m_min, m_max = min(melody_scores), max(melody_scores)

        for result in results:

            if m_max > m_min:

                normalized_melody = (
                    (result.score - m_min) / (m_max - m_min)
                )

            else:

                normalized_melody = 1.0

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


        playable = 0

        impossible = 0


        total_position_score = 0


        movement_score = 0

        transition_count = 0


        fifth_transition_score = 0



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
        # New 5th string transition analysis
        # ---------------------------------------------


        fifth_transition_score, fifth_count = (

            self.fifth_string_transition_support(

                positions,

                tuning

            )

        )



        if fifth_count:


            reasons.append(

                f"5th string bridges {fifth_count} melody transitions"

            )



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

            +

            fifth_transition_score

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
            unplayable_note_count, unplayable_note_proportion
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

            unplayable_note_proportion=unplayable_note_proportion

            # shared_features and confidence are left at
            # their defaults ([] and None) -- shared_features
            # is a group-level concept (see
            # recommendations.py), and confidence isn't
            # computed yet.

        )



    # -------------------------------------------------
    # New feature:
    #
    # Can the 5th string cover the hand movement?
    #
    # -------------------------------------------------

    def fifth_string_transition_support(
        self,
        positions,
        tuning
    ):


        if len(tuning.notes) < 5:

            return 0, 0



        fifth = tuning.notes[4]



        score = 0

        count = 0



        for index in range(
            len(positions) - 1
        ):


            current = positions[index]

            following = positions[index + 1]



            if not current or not following:

                continue



            movement = abs(

                current["fret"]

                -

                following["fret"]

            )



            # Only reward real position changes

            if movement < 7:

                continue



            # Can the fifth string be played
            # as a bridge note?

            fifth_fret = (

                following_note :=

                self.get_note_midi(
                    self.notes[index + 1]
                )

            ) - fifth



            if 0 <= fifth_fret <= 22:


                count += 1



                # Stronger reward when
                # the hand has farther to travel

                if movement >= 10:

                    score += 6


                else:

                    score += 3



        return score, count



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
        BO-49 -- Chord/playing quality for this tuning.

        BO-49's own investigation traced the existing Playing
        Model (playing_model.py, analyze_tuning_playing_model())
        and found it ALREADY does exactly what BO-49 set out to
        build: for each real chord occurrence, it evaluates every
        candidate chord shape's own intrinsic playability (finger
        count, span, hand geometry -- analyze_chord_shape_
        playability()) TOGETHER WITH how well the surrounding
        melody notes can be played from that specific chord's own
        hand position (evaluate_combination() -- contained-in-
        chord bonus, free-finger availability without abandoning
        the chord shape, proximity to the chord's own working
        fret), keeping the single best-scoring COMBINATION per
        phrase (evaluate_phrase()). This is a strictly richer
        measure of "chord/playing quality" than BO-43 through
        BO-48's own avg_awkwardness, which only ever looked at
        working_fret (how high up the neck) and had no way to
        distinguish a comfortable low-fret shape from an awkward
        one, or to know whether the melody can actually be played
        from a chord's own hand position at all. Confirmed with
        real data (White Christmas): Open G has the best raw
        melody score but the WORST Playing Model score of its own
        top 3 real candidates -- exactly the "good melody, poor
        chords" case BO-49 exists to catch, and something
        avg_awkwardness alone could never see.

        Per BO-49's own explicit instruction, this composes the
        EXISTING Playing Model rather than building a second,
        parallel scoring system -- reuses analyze_tuning_playing_
        model() unchanged, no new chord/melody evaluation logic
        of its own.

        Returns (avg_awkwardness, chord_fd_quality,
        unplayable_note_count, unplayable_note_proportion).

        avg_awkwardness (BO-43/44/46 definition, UNCHANGED --
        mean of max(0, working_fret - WORKING_FRET_COMFORT_
        CEILING) across real chord onsets) is still computed and
        returned as a diagnostic/comparison value -- existing
        BO-48 tests and reporting that read it are unaffected --
        but chord_fd_quality itself is no longer derived from it.

        chord_fd_quality is now the Playing Model's own average
        per-phrase score (total_score / phrase count -- the same
        normalization playing_model_bonus() already established,
        reused here rather than duplicated), normalized to [0, 1]
        against a FIXED reference (PLAYING_MODEL_QUALITY_
        REFERENCE, see that constant's own comment) -- still
        deliberately NOT the current candidate set's own min/max,
        preserving BO-47/48's own central requirement: this value
        must not change merely because a different tuning is also
        being compared alongside this one. 1.0 = as good as the
        reference allows; 0.0 = at or beyond it.

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

            return 0.0, 1.0, 0, 0.0

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
            )

        try:

            chord_service = ChordService(ChordLibrary())

            # avg_awkwardness -- unchanged BO-43/44/46
            # definition, still computed for diagnostics/
            # comparison even though chord_fd_quality no longer
            # derives from it directly.

            awkwardness_sum = 0.0

            total_chord_onsets = 0

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

                total_chord_onsets += 1

            avg_awkwardness = (
                awkwardness_sum / total_chord_onsets
                if total_chord_onsets else 0.0
            )

            # chord_fd_quality -- BO-49, derived from the
            # existing Playing Model's own combined chord+melody
            # phrase scoring, reused unchanged.

            temp_score = Score(
                notes=self.melody_notes,
                harmonies=self.harmonies
            )

            playing_model_result = analyze_tuning_playing_model(
                temp_score, tuning, chord_service
            )

            phrase_count = len(playing_model_result.phrases)

            if phrase_count == 0:

                return 0.0, 1.0, unplayable_note_count, (
                    unplayable_note_proportion
                )

            average_phrase_score = (
                playing_model_result.total_score / phrase_count
            )

            chord_fd_quality = max(0.0, min(
                average_phrase_score
                / self.PLAYING_MODEL_QUALITY_REFERENCE,
                1.0
            ))

            return (
                avg_awkwardness, chord_fd_quality,
                unplayable_note_count, unplayable_note_proportion
            )

        except Exception:

            return 0.0, 1.0, unplayable_note_count, (
                unplayable_note_proportion
            )