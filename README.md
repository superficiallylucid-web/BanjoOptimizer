# Banjo Optimizer

Banjo Optimizer analyzes MuseScore banjo arrangements and recommends practical banjo tunings and fingering approaches.

The goal of the project is to help banjo players find playable arrangements by considering:

* the musical key and notes in a score,
* available banjo tunings,
* fretboard position,
* practical playing considerations.

## Current Capabilities

* Reads MuseScore `.mscz` files
* Extracts score information and melody notes
* Performs basic music theory analysis
* Evaluates possible banjo tunings
* Recommends suitable tuning options
* Produces analysis output explaining results

## Project Structure

```
main.py          Application entry point
parser.py        MuseScore file parsing
optimizer.py     Tuning and fingering analysis engine
music.py         Music theory utilities
models.py        Shared data structures
tunings.py       Banjo tuning definitions
score.py         Score representation
output.py        Report generation
```

## Development Status

The project is under active development.

Completed:

* MuseScore file parsing foundation
* Music theory utilities
* Tuning definitions
* Initial optimization framework
* Executable packaging

Future improvements:

* More intelligent fingering selection
* Phrase-aware position changes
* Chord-aware optimization
* Improved explanations of recommendations
* Enhanced musician-facing reports

## Running the Program

The program is designed to analyze MuseScore files placed in the appropriate score directory and generate optimization results.

For development:

```
python main.py
```

## Testing

Tests are located in the `tests` directory and can be run with:

```
pytest
```
