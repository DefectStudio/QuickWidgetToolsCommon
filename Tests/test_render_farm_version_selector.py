"""Selector initialization must preserve the widget's configured farm choice."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "Content/Python/render_farm_version_selector.py"
SPEC = importlib.util.spec_from_file_location("farm_version_selector_test", SCRIPT)
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


class CheckStateChanged:
    def __init__(self):
        self.callbacks = []

    def clear(self):
        self.callbacks.clear()

    def add_callable(self, callback):
        self.callbacks.append(callback)

    def broadcast(self, checked):
        for callback in tuple(self.callbacks):
            callback(checked)


class Checkbox:
    def __init__(self, checked):
        self.checked = checked
        self.on_check_state_changed = CheckStateChanged()

    def is_checked(self):
        return self.checked

    def set_is_checked(self, checked):
        self.checked = checked

    def click(self):
        self.checked = not self.checked
        self.on_check_state_changed.broadcast(self.checked)


class FarmVersionSelectorTests(unittest.TestCase):
    def test_initialize_preserves_either_valid_default(self):
        for use_v2 in (False, True):
            with self.subTest(use_v2=use_v2):
                v1, v2 = Checkbox(not use_v2), Checkbox(use_v2)
                selector.initialize(v1, v2)
                self.assertEqual((not use_v2, use_v2), (v1.is_checked(), v2.is_checked()))
                self.assertEqual(use_v2, selector.use_v2(v1, v2))

    def test_clicks_switch_versions_and_keep_the_active_choice_selected(self):
        for use_v2 in (False, True):
            with self.subTest(use_v2=use_v2):
                v1, v2 = Checkbox(not use_v2), Checkbox(use_v2)
                selector.initialize(v1, v2)
                for choice, expected_v2 in ((v1, False), (v1, False), (v2, True), (v2, True)):
                    choice.click()
                    self.assertEqual((not expected_v2, expected_v2), (v1.is_checked(), v2.is_checked()))
                    self.assertEqual(expected_v2, selector.use_v2(v1, v2))

    def test_reinitialize_preserves_the_users_latest_choice(self):
        v1, v2 = Checkbox(True), Checkbox(False)
        selector.initialize(v1, v2)
        v2.click()
        selector.initialize(v1, v2)
        self.assertTrue(selector.use_v2(v1, v2))
        self.assertEqual(1, len(v1.on_check_state_changed.callbacks))
        self.assertEqual(1, len(v2.on_check_state_changed.callbacks))
        v1.click()
        self.assertFalse(selector.use_v2(v1, v2))

    def test_ambiguous_defaults_are_preserved_and_rejected_until_a_choice_is_made(self):
        for checked in (False, True):
            for chosen_v2 in (False, True):
                with self.subTest(checked=checked, chosen_v2=chosen_v2):
                    v1, v2 = Checkbox(checked), Checkbox(checked)
                    selector.initialize(v1, v2)
                    self.assertEqual((checked, checked), (v1.is_checked(), v2.is_checked()))
                    with self.assertRaisesRegex(RuntimeError, "Select exactly one"):
                        selector.use_v2(v1, v2)
                    (v2 if chosen_v2 else v1).click()
                    self.assertEqual(chosen_v2, selector.use_v2(v1, v2))


if __name__ == "__main__":
    unittest.main()
