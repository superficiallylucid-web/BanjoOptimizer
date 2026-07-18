from tunings import get_tunings

from music import get_key_profile


class TuningAnalyzer:
    """
    Analyzes banjo tunings against a melody.

    Focus:
    - note playability
    - hand movement
    - 5th string transition support
    """


    def __init__(self, notes, key="Unknown"):

        self.notes = notes

        self.key = key



    # -------------------------------------------------

    def analyze(self):

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



        modern.sort(
            key=lambda x: x["score"],
            reverse=True
        )


        historical.sort(
            key=lambda x: x["score"],
            reverse=True
        )


        return {

            "modern": modern,

            "historical": historical

        }



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


            possible = self.find_positions(
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



            best_position = self.best_position(
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

        score += self.special_key_tuning_bonus(
            tuning,
            reasons
        )

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



        return {

            "name": tuning.name,

            "symbol": tuning.symbol,

            "category": tuning.category,

            "score": round(
                score,
                2
            ),

            "reasons": reasons

        }



    # -------------------------------------------------
    # Find possible fret positions
    # -------------------------------------------------

    def find_positions(self, midi, open_notes):

        positions = []


        for string_number, open_note in enumerate(open_notes):

            fret = midi - open_note


            if 0 <= fret <= 22:

                positions.append(
                    {
                        "string": string_number,
                        "fret": fret,
                        "score": 0
                    }
                )


        return positions



    # -------------------------------------------------
    # Choose best fingering position
    # -------------------------------------------------

    def best_position(self, positions):

        best = None


        best_score = -999



        for position in positions:


            fret = position["fret"]

            string = position["string"]


            value = 0



            if fret == 0:

                value += 10


            elif fret <= 4:

                value += 8


            elif fret <= 7:

                value += 5


            elif fret <= 12:

                value += 2


            else:

                value -= 3



            # Favor middle melody strings

            if string == 1:

                value += 6


            elif string == 2:

                value += 4


            elif string == 3:

                value += 2



            position["score"] = value



            if value > best_score:

                best_score = value

                best = position



        return best



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


        return bonus



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