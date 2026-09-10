"""
BO-165 -- overhauled capo usage on the GUI: a "Tuning:" dropdown
(all 13 built-in tunings, Double D included) that decomposes into
a "Capo tuning" dropdown (only the 12 non-capo-derived tunings), a
Capo number, and a 5th string, with a live "Sounded tuning" display
computed via main.compute_sounded_tuning() -- the same function
Optimize itself calls, so the display is never a second,
potentially-drifting representation.

Uses the same Qt offscreen-platform, direct-widget-construction
pattern as every other GUI test file in this project (no real
display needed).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from PySide6.QtWidgets import QApplication

import gui
from tunings import get_tunings

# A single shared QApplication -- required once per process for
# any QWidget construction, same convention as this project's
# other GUI tests.
_app = QApplication.instance() or QApplication(sys.argv)


def test_all_tunings_combo_contains_all_13_built_in_tunings():

    window = gui.BanjoOptimizerWindow()

    assert window.all_tunings_combo.count() == 13

    combo_names = {
        window.all_tunings_combo.itemText(i)
        for i in range(window.all_tunings_combo.count())
    }

    assert combo_names == set(get_tunings().keys())


def test_double_d_present_in_all_tunings_combo():

    window = gui.BanjoOptimizerWindow()

    assert window.all_tunings_combo.findText("Double D") != -1


def test_capo_tuning_combo_excludes_capo_derived_tunings():
    """
    Confirms the Capo tuning dropdown excludes every capo-derived
    tuning (base_tuning is not None) -- Double D specifically, and
    generally, not as a single hardcoded name check.
    """

    window = gui.BanjoOptimizerWindow()

    capo_tuning_names = {
        window.capo_tuning_combo.itemText(i)
        for i in range(window.capo_tuning_combo.count())
    }

    capo_derived_names = {
        name
        for name, tuning in get_tunings().items()
        if tuning.base_tuning is not None
    }

    assert "Double D" in capo_derived_names

    for name in capo_derived_names:
        assert not any(
            entry.startswith(name + " (")
            for entry in capo_tuning_names
        )


def test_capo_tuning_combo_contains_ordinary_open_g_family_tunings():
    """
    Representative check (not exhaustive) that ordinary,
    non-capo-derived tunings -- Open G specifically -- are present
    in the Capo tuning dropdown.
    """

    window = gui.BanjoOptimizerWindow()

    assert (
        window.capo_tuning_combo.findText("Open G (gDGBD)") != -1
    )


def test_capo_number_range_is_0_to_5():

    window = gui.BanjoOptimizerWindow()

    assert window.capo_spin.minimum() == 0
    assert window.capo_spin.maximum() == 5


def test_sounded_tuning_display_double_c_capo_2_fifth_a():

    window = gui.BanjoOptimizerWindow()

    idx = window.capo_tuning_combo.findText("Double C (gCGCD)")
    window.capo_tuning_combo.setCurrentIndex(idx)
    window.capo_spin.setValue(2)
    fifth_idx = window.fifth_string_combo.findText("A")
    window.fifth_string_combo.setCurrentIndex(fifth_idx)

    assert window.sounded_tuning_display.text() == "aDADE"


def test_sounded_tuning_display_open_g_capo_3_fifth_f():
    """
    _notes_to_symbol()'s own pre-existing sharp-only convention
    (confirmed during BO-163, unrelated to this feature) means the
    real displayed result is "fFA#DF", not "fFBbDF" -- same pitch
    class, different letter.
    """

    window = gui.BanjoOptimizerWindow()

    idx = window.capo_tuning_combo.findText("Open G (gDGBD)")
    window.capo_tuning_combo.setCurrentIndex(idx)
    window.capo_spin.setValue(3)
    fifth_idx = window.fifth_string_combo.findText("F")
    window.fifth_string_combo.setCurrentIndex(fifth_idx)

    assert window.sounded_tuning_display.text() == "fFA#DF"


def test_unchanged_leaves_capo_tunings_own_fifth_string():

    window = gui.BanjoOptimizerWindow()

    idx = window.capo_tuning_combo.findText("Open G (gDGBD)")
    window.capo_tuning_combo.setCurrentIndex(idx)
    window.capo_spin.setValue(2)
    # fifth_string_combo left at its own default, "Unchanged"

    assert window.fifth_string_combo.currentText() == "Unchanged"
    assert window.sounded_tuning_display.text() == "gEAC#E"


def test_selecting_double_d_in_all_tunings_syncs_correct_decomposition():
    """
    Selecting "Double D" from the all-13 Tuning dropdown must
    decompose it into exactly its own real, known metadata:
    Capo tuning=Double C, Capo=2, 5th string=A -- reusing Double
    D's own base_tuning/capo/fifth_string_note fields directly,
    not a separately-maintained mapping.
    """

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Double D")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert (
        window.capo_tuning_combo.currentText() == "Double C (gCGCD)"
    )
    assert window.capo_spin.value() == 2
    assert window.fifth_string_combo.currentText() == "A"
    assert window.sounded_tuning_display.text() == "aDADE"


def test_selecting_ordinary_tuning_in_all_tunings_syncs_to_itself():
    """
    A tuning with no base_tuning (Open G: not capo-derived) should
    decompose to itself, capo 0, 5th string Unchanged -- it already
    IS its own open base.
    """

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Open G")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert (
        window.capo_tuning_combo.currentText() == "Open G (gDGBD)"
    )
    assert window.capo_spin.value() == 0
    assert window.fifth_string_combo.currentText() == "Unchanged"
    assert window.sounded_tuning_display.text() == "gDGBD"


def test_new_tuning_controls_disabled_under_recommended_tuning():

    window = gui.BanjoOptimizerWindow()

    # recommend_radio is checked by default
    assert window.all_tunings_combo.isEnabled() is False
    assert window.capo_tuning_combo.isEnabled() is False

    window.specific_radio.setChecked(True)

    assert window.all_tunings_combo.isEnabled() is True
    assert window.capo_tuning_combo.isEnabled() is True

    window.recommend_radio.setChecked(True)

    assert window.all_tunings_combo.isEnabled() is False
    assert window.capo_tuning_combo.isEnabled() is False


def test_recommended_tuning_num_tunings_control_unaffected():
    """
    Confirms BO-165 left the Recommended Tuning section's own
    control (num_tunings_spin, from BO-157) completely untouched --
    still enabled by default, still disabled under specific tuning.
    """

    window = gui.BanjoOptimizerWindow()

    assert window.num_tunings_spin.isEnabled() is True

    window.specific_radio.setChecked(True)

    assert window.num_tunings_spin.isEnabled() is False
