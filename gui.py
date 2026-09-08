"""
gui.py

BO-152/153 -- the first, very-basic GUI (per BO-152's own phased
plan: "Very basic dialog: Pick .mscz, choose tuning/options, Run,
see basic result"). Calls main.run_optimizer() directly -- no
subprocess, no CLI simulation, matching the ideal architecture
BO-152's own request diagram called for (GUI and CLI both sitting
on top of the same application pipeline, not the GUI faking a
command-line invocation).

Two deliberate scope decisions for this first pass, agreed before
writing this file:

1. No "Generate TAB" / "Generate fretboard diagrams" checkboxes
   (present in BO-152's own mockup). Neither corresponds to a real
   toggle in run_optimizer() today -- TAB generation is always on,
   and fretboard diagrams are embedded in that TAB output, not a
   separate one. Showing checkboxes that don't do anything would
   be worse than omitting them; wiring real ones is future work
   this file doesn't attempt.
2. No output-location picker. run_optimizer() always writes to the
   application's own real output/ folder (project_folder's own
   "output" subdirectory) -- same as the CLI always has. A real,
   working picker needs run_optimizer() extended with a dedicated
   parameter first; out of scope here.

The "specific tuning" dropdown is deliberately populated with only
the 12 of 13 built-in tunings that have capo=0 -- for those, the
tuning's own .symbol IS the open-tuning symbol run_optimizer()'s
tuning_symbol parameter expects, so no symbol-translation logic is
needed. The 13th (Double D, capo=2, derived from Double C) is left
out of this first GUI rather than guessing at how to surface
capo'd/derived tunings in a dropdown -- deferred to a real Advanced
Options pass, matching BO-152's own phased plan.

No progress/status callback: run_optimizer() is called
synchronously, and the window will appear to hang for however long
optimization takes (confirmed in testing: a few seconds for a
single score). This is the same known limitation flagged in
run_optimizer()'s own docstring -- sys.stdout is redirected inside
that function, so this GUI cannot safely run it on a background
thread without that being addressed first. Fine for a first,
very-basic dialog; a real progress area is future work.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QComboBox, QSpinBox, QTextEdit, QFileDialog,
    QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt

import main
from tunings import get_tunings

PROJECT_FOLDER = Path(__file__).parent
SCORES_FOLDER = PROJECT_FOLDER / "scores"

# Only the open (capo=0) tunings -- see module docstring for why.
OPEN_TUNINGS = {
    name: tuning
    for name, tuning in get_tunings().items()
    if tuning.capo == 0
}


class BanjoOptimizerWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Banjo Optimizer")
        self.setMinimumWidth(520)

        self.selected_score_path = None

        layout = QVBoxLayout(self)

        # --- Input Score ---------------------------------------
        score_group = QGroupBox("Input Score")
        score_layout = QHBoxLayout(score_group)

        self.score_line_edit = QLineEdit()
        self.score_line_edit.setReadOnly(True)
        self.score_line_edit.setPlaceholderText(
            "No score selected"
        )

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_clicked)

        score_layout.addWidget(self.score_line_edit)
        score_layout.addWidget(browse_button)

        layout.addWidget(score_group)

        # --- Tuning ----------------------------------------------
        # BO-157 -- "Number of tunings" replaces the former "Show
        # alternative tunings" checkbox + count entirely, per
        # explicit instruction. This is a genuinely different
        # mechanism from the old one, not just a relabel: it
        # controls run_optimizer()'s own num_tunings parameter
        # (BO-157), which returns exactly that many top-ranked
        # tunings unconditionally, straight off the ranked list --
        # unlike the old alternatives mechanism, there's no
        # separate "does rank 4+ still qualify as strong" test.
        # This GUI no longer calls alternatives at all (still
        # available to CLI callers via --alternatives, untouched).
        # Only meaningful under "Recommended Tuning" -- disabled
        # under "Use specific tuning", which always produces
        # exactly one result regardless.
        tuning_group = QGroupBox("Tuning")
        tuning_layout = QGridLayout(tuning_group)

        self.recommend_radio = QRadioButton("Recommended Tuning")
        self.recommend_radio.setChecked(True)

        # 11 is the real, total number of "modern" tunings the
        # recommender ranks (confirmed directly) -- asking for
        # more would just pad the list with weaker matches for no
        # benefit, so that's the genuinely meaningful cap here.
        self.num_tunings_spin = QSpinBox()
        self.num_tunings_spin.setMinimum(1)
        self.num_tunings_spin.setMaximum(11)
        self.num_tunings_spin.setValue(1)

        self.recommend_radio.toggled.connect(
            self.num_tunings_spin.setEnabled
        )

        self.specific_radio = QRadioButton("Use specific tuning")

        tuning_button_group = QButtonGroup(self)
        tuning_button_group.addButton(self.recommend_radio)
        tuning_button_group.addButton(self.specific_radio)

        self.tuning_combo = QComboBox()
        for name, tuning in sorted(OPEN_TUNINGS.items()):
            self.tuning_combo.addItem(
                f"{name} ({tuning.symbol})", userData=tuning.symbol
            )
        self.tuning_combo.setEnabled(False)

        self.specific_radio.toggled.connect(
            self.tuning_combo.setEnabled
        )

        # BO-154 -- capo support. Only meaningful alongside a
        # specific tuning (matches the CLI's own requirement:
        # --capo without --tuning is rejected by run_optimizer()
        # with "--capo requires --tuning to also be given.").
        # 0 means "no capo" and is passed to run_optimizer() as
        # None, matching --capo's own CLI default; 1-5 is the
        # only other valid range (run_optimizer() itself rejects
        # anything else).
        capo_label = QLabel("Capo:")
        capo_tooltip = (
            "A banjo capo clamps across the neck, raising the "
            "pitch of strings 1-4 only -- never the 5th (short) "
            "string, which stays open regardless. Each capo "
            "position raises those 4 strings by one semitone, so "
            "e.g. Open G (gDGBD) with capo 2 sounds as gEAC#E: "
            "the 5th string is still G, but strings 1-4 are each "
            "two semitones higher than the open tuning shown "
            "above. 0 means no capo."
        )
        capo_label.setToolTip(capo_tooltip)

        self.capo_spin = QSpinBox()
        self.capo_spin.setMinimum(0)
        self.capo_spin.setMaximum(5)
        self.capo_spin.setValue(0)
        self.capo_spin.setEnabled(False)
        self.capo_spin.setToolTip(capo_tooltip)

        self.specific_radio.toggled.connect(
            self.capo_spin.setEnabled
        )

        tuning_layout.addWidget(self.recommend_radio, 0, 0, 1, 2)
        tuning_layout.addWidget(
            QLabel("Number of tunings:"), 1, 1
        )
        tuning_layout.addWidget(self.num_tunings_spin, 1, 2)

        tuning_layout.addWidget(self.specific_radio, 2, 0, 1, 2)
        tuning_layout.addWidget(self.tuning_combo, 3, 1, 1, 2)
        tuning_layout.addWidget(capo_label, 4, 1)
        tuning_layout.addWidget(self.capo_spin, 4, 2)

        layout.addWidget(tuning_group)

        # --- Optimize ----------------------------------------------
        self.optimize_button = QPushButton("Optimize")
        self.optimize_button.clicked.connect(
            self._on_optimize_clicked
        )

        layout.addWidget(
            self.optimize_button, alignment=Qt.AlignHCenter
        )

        # --- Status --------------------------------------------
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)

        # --- Results ---------------------------------------------
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setPlaceholderText(
            "Results will appear here after you click Optimize."
        )
        layout.addWidget(self.results_view)

        # --- Bottom buttons --------------------------------------
        bottom_layout = QHBoxLayout()

        self.open_output_button = QPushButton("Open Output")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(
            self._on_open_output_clicked
        )

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        bottom_layout.addWidget(self.open_output_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_button)

        layout.addLayout(bottom_layout)

        self._last_run_folder = None

    def _on_browse_clicked(self):

        SCORES_FOLDER.mkdir(exist_ok=True)

        # BO-155 -- a real file picker. Defaults to opening in
        # scores/ (convenient if that's where most files already
        # are), but any .mscz file anywhere is now accepted --
        # see run_optimizer()'s own score_path parameter (BO-155),
        # which this now uses instead of score_filename whenever
        # the picked file isn't already inside scores/.
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a MuseScore file",
            str(SCORES_FOLDER),
            "MuseScore files (*.mscz)"
        )

        if not file_path:
            return

        self.selected_score_path = Path(file_path)
        self.score_line_edit.setText(str(self.selected_score_path))

    def _on_optimize_clicked(self):

        if self.selected_score_path is None:
            QMessageBox.warning(
                self, "No score selected",
                "Please choose a score first."
            )
            return

        tuning_symbol = None
        capo = None

        if self.specific_radio.isChecked():
            tuning_symbol = self.tuning_combo.currentData()

            if self.capo_spin.value() > 0:
                capo = self.capo_spin.value()

        # BO-157 -- num_tunings is only meaningful under
        # "Recommended Tuning" -- default to 1 (matching
        # num_tunings_spin's own default) if "specific tuning" is
        # active, since the spinbox itself is disabled in that
        # state and its value shouldn't be trusted either way.
        # "Use specific tuning" always produces exactly one result
        # regardless of this value, so 1 vs. its actual disabled
        # value makes no practical difference here -- this is
        # about not reading a value from a control the user can't
        # currently see as meaningful, not about changing behavior.
        num_tunings = (
            self.num_tunings_spin.value()
            if self.recommend_radio.isChecked()
            else 1
        )

        self.status_label.setText("Status: Optimizing...")
        self.results_view.clear()
        self.optimize_button.setEnabled(False)
        self.open_output_button.setEnabled(False)
        QApplication.processEvents()

        try:
            result = main.run_optimizer(
                score_path=self.selected_score_path,
                tuning_symbol=tuning_symbol,
                capo=capo,
                num_tunings=num_tunings,
            )
        except ValueError as error:
            self.status_label.setText("Status: Error")
            QMessageBox.critical(self, "Could not optimize", str(error))
            self.optimize_button.setEnabled(True)
            return
        except Exception as error:
            self.status_label.setText("Status: Error")
            QMessageBox.critical(
                self, "Unexpected error",
                f"Something went wrong:\n{error}"
            )
            self.optimize_button.setEnabled(True)
            return

        self.optimize_button.setEnabled(True)
        self._last_run_folder = result["run_folder"]
        self.open_output_button.setEnabled(True)
        self.status_label.setText("Status: Done")

        self._display_result(result)

    def _display_result(self, result):

        lines = []

        for score_result in result["scores"]:

            lines.append(f"Title: {score_result['title']}")
            lines.append(f"Key: {score_result['key']}")
            lines.append("")

            requested = score_result["requested_tuning"]

            if requested is not None:
                lines.append(
                    f"Using requested tuning: {requested.symbol}"
                )
            else:
                lines.append("Recommended tunings:")

            lines.append("")

            for i, rec in enumerate(
                score_result["recommendations"], start=1
            ):
                lines.append(f"{i}. {rec.name} ({rec.symbol})")
                for advantage in rec.advantages:
                    lines.append(f"   - {advantage}")

            # BO-157 -- this GUI no longer requests alternatives
            # (see this class's own _on_optimize_clicked), so
            # additional_alternatives is always empty here now.
            # Not displayed -- removed rather than left as an
            # always-false dead branch.

            lines.append("")
            lines.append("Generated files:")

            for gen in score_result["generated_files"]:
                if gen["error"] is None:
                    lines.append(
                        f"   - {gen['tab_path'].name}"
                    )
                else:
                    lines.append(
                        f"   - Could not generate "
                        f"{gen['tuning_name']}: {gen['error']}"
                    )

        self.results_view.setPlainText("\n".join(lines))

    def _on_open_output_clicked(self):

        if self._last_run_folder is None:
            return

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._last_run_folder))
        )


def main_gui():
    app = QApplication(sys.argv)
    window = BanjoOptimizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_gui()
